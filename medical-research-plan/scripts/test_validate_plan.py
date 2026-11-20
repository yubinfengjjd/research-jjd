"""Unit tests for lightweight medical-research-plan validate_plan.py."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_plan as vp


GOOD_ROLLING_PLAN = """# OCT 多分类滚动研究计划

- **阶段模式**：`start（第 1 步定锚）`
- **计划版本**：`v1` ｜ **更新日期**：`2026-11-21`

## 1. 临床问题、核心假设与已确立基础
临床筛查中罕见病种漏诊率高。核心假设：在患者级验证下，先建立强基线并定位错例模式。

## 2. 数据方案、独立划分与伦理
按 `patient_id` 患者级划分 train/val/test，跨划分不重叠。伦理审批：执行前待办。

## 3. 核心基线与文献定位
强基线 `baseline` 采用领域预训练模型微调；已摸底 4 篇核心竞争文献。

## 4. 当前阶段方法与实验设计
主指标 `bacc`（higher），多 seed（0, 1, 2）患者级统计；当前先跑 baseline 与诊断。

## 5. 下一步延伸分支（条件触发）
- 分支 A（若观察到跨域掉点）：引入领域不变特征约束。
- 分支 B（若观察到类别不平衡主导误差）：改用代价敏感损失。

## 6. 当前步骤滚动预算与实验交接
本步单卡预计 2 小时；配置见 `study-config.json`。

## 7. 审稿人风险、执行前待办与限制
最强反方质疑：更强预训练骨干能否直接解释收益。
"""


class TestValidatePlan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='medplan-test-'))
        self.plan_dir = self.tmp / '00_plan'
        self.plan_dir.mkdir()
        self.plan_path = self.plan_dir / 'project-plan.md'

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_valid_rolling_plan_with_study_config(self):
        self.plan_path.write_text(GOOD_ROLLING_PLAN, encoding='utf-8')
        cfg = self.tmp / 'study-config.json'
        cfg.write_text(json.dumps({
            'schema_version': 3,
            'primary_metric': {'name': 'bacc', 'direction': 'higher'},
            'data': {'group_unit': 'patient_id'},
            'reference': 'baseline',
        }), encoding='utf-8')

        rep = vp.validate_plan(self.plan_path, mode='rolling', study_config_path=cfg)
        self.assertTrue(rep['valid'], rep)
        self.assertTrue(rep['config_checked'])
        self.assertEqual(rep['errors'], [])
        self.assertEqual(rep['warnings'], [])

    def test_rejects_template_placeholder_and_pollution(self):
        bad = GOOD_ROLLING_PLAN + '\n<details>old corpse</details>\n[TODO: fill]\n'
        self.plan_path.write_text(bad, encoding='utf-8')
        rep = vp.validate_plan(self.plan_path, mode='rolling')
        self.assertFalse(rep['valid'])
        self.assertTrue(any('<details>' in e for e in rep['errors']))
        self.assertTrue(any('[TODO:' in e for e in rep['errors']))

    def test_converged_mode_rejects_leftover_branches_section(self):
        self.plan_path.write_text(GOOD_ROLLING_PLAN, encoding='utf-8')
        rep = vp.validate_plan(self.plan_path, mode='converged')
        self.assertFalse(rep['valid'])
        self.assertTrue(any('延伸分支' in e for e in rep['errors']))

        converged_text = GOOD_ROLLING_PLAN.replace(
            '## 5. 下一步延伸分支（条件触发）\n- 分支 A（若观察到跨域掉点）：引入领域不变特征约束。\n- 分支 B（若观察到类别不平衡主导误差）：改用代价敏感损失。\n\n',
            '',
        )
        self.plan_path.write_text(converged_text, encoding='utf-8')
        rep2 = vp.validate_plan(self.plan_path, mode='converged')
        self.assertTrue(rep2['valid'], rep2)

    def test_detects_mismatched_primary_metric_in_study_config(self):
        self.plan_path.write_text(GOOD_ROLLING_PLAN, encoding='utf-8')
        cfg = self.tmp / 'study-config.json'
        cfg.write_text(json.dumps({
            'schema_version': 3,
            'primary_metric': {'name': 'hd95', 'direction': 'lower'},
            'data': {'group_unit': 'patient_id'},
            'reference': 'baseline',
        }), encoding='utf-8')
        rep = vp.validate_plan(self.plan_path, mode='rolling', study_config_path=cfg)
        self.assertFalse(rep['valid'])
        self.assertTrue(any('hd95' in e for e in rep['errors']))

    def test_warns_on_draft_or_json_pollution_in_00_plan(self):
        self.plan_path.write_text(GOOD_ROLLING_PLAN, encoding='utf-8')
        (self.plan_dir / 'project-plan.draft.md').write_text('junk', encoding='utf-8')
        rep = vp.validate_plan(self.plan_path, mode='rolling')
        self.assertTrue(rep['valid'])
        self.assertTrue(any('project-plan.draft.md' in w for w in rep['warnings']))


if __name__ == '__main__':
    unittest.main()
