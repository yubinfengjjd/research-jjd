"""Comprehensive regression tests for lightweight medimg-experiment (v3)."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / 'scripts'
SYNTH_DIR = SKILL_ROOT / 'assets' / 'synthetic'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_package
from medexp import study
from medexp.common import GateError, read_json, write_json


def _make_config(project_root: Path, code_dir: Path, data_dir: Path, plan_path: Path,
                 inject_leak: bool = False, max_routes: int = 3, max_seconds: int = 600) -> dict:
    audit_cmd = ['{python}', 'audit_split.py', '--output', '{output}']
    if inject_leak:
        audit_cmd.append('--inject-leak')
    return {
        'schema_version': 3,
        'study_id': 'oct-bacc-demo',
        'task': 'multiclass_classification',
        'hypothesis': 'v1: baseline vs proposed_v1 on 3-class BACC',
        'plan_path': str(plan_path),
        'project_root': str(project_root),
        'code_dir': str(code_dir),
        'primary_metric': {'name': 'bacc', 'direction': 'higher', 'target': 0.85},
        'secondary_metrics': [{'name': 'macro_f1', 'direction': 'higher'}],
        'data': {
            'paths': [str(data_dir)],
            'group_unit': 'patient_id',
            'labels_source': 'synthetic clinical reference',
            'split_reference': 'patient-level fixed split 60/20/20',
        },
        'split_audit': {'command': audit_cmd, 'timeout_seconds': 30},
        'test': {
            'policy': 'locked',
            'reference': 'held-out 20 synthetic patients',
            'command': ['{python}', 'evaluate_test.py', '--run-dir', '{run_dir}', '--output', '{output}'],
            'timeout_seconds': 60,
        },
        'reference': 'baseline',
        'entries': [
            {
                'id': 'baseline',
                'role': 'baseline',
                'description': 'Strong reference baseline',
                'command': ['{python}', 'train.py', '--model', 'baseline', '--seed', '{seed}', '--output-dir', '{output_dir}'],
            },
            {
                'id': 'proposed_v1',
                'role': 'proposed',
                'description': 'Initial proposed architecture v1',
                'screening_command': ['{python}', 'train.py', '--model', 'proposed_v1', '--epochs', '3', '--seed', '{seed}', '--output-dir', '{output_dir}'],
                'command': ['{python}', 'train.py', '--model', 'proposed_v1', '--epochs', '10', '--seed', '{seed}', '--output-dir', '{output_dir}'],
            },
        ],
        'seeds': [0, 1, 2],
        'budgets': {
            'max_training_seconds': max_seconds,
            'run_timeout_seconds': 60,
            'max_routes': max_routes,
            'deadline_utc': None,
        },
        'environment': {
            'python': sys.executable,
            'device': 'cpu',
            'inherit_cache': True,
        },
        'ci': None,
    }


class TestMedimgExperimentV3(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='medexp-v3-test-'))
        self.project = self.tmp / 'project'
        self.data = self.tmp / 'readonly_data'
        self.code = self.project / '01_analysis' / 'src'
        self.study_root = self.project / '01_analysis' / 'oct-bacc-demo'
        self.data.mkdir(parents=True)
        (self.data / 'meta.txt').write_text('readonly\n', encoding='utf-8')
        shutil.copytree(SYNTH_DIR, self.code)

        (self.project / '00_plan').mkdir(parents=True)
        self.plan = self.project / '00_plan' / 'project-plan.md'
        self.plan.write_text('# 研究计划 v1\n\n## 3. 方法路线\n\n初始采用 proposed_v1 方案。\n', encoding='utf-8')
        (self.project / 'PROJECT.md').write_text(
            '# Demo Project\n\n'
            '| # | 阶段 | 技能 | 状态 |\n'
            '|---|---|---|---|\n'
            '| 0 | 入口检查 | medpaper-pipeline | 已确认 |\n'
            '| 1 | 图表规划 | medfig-plan | 已确认 |\n\n'
            '## 变更记录\n',
            encoding='utf-8',
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_package_check_passes(self):
        res = check_package.check(SKILL_ROOT)
        self.assertTrue(res['valid'])
        self.assertEqual(res['schema_version'], 3)

    def test_split_leakage_blocks_audit_and_run(self):
        cfg_path = self.tmp / 'cfg_leak.json'
        write_json(cfg_path, _make_config(self.project, self.code, self.data, self.plan, inject_leak=True))
        study.init(self.study_root, cfg_path, authorization='test auth')

        # Cannot train before audit passes
        with self.assertRaises(GateError):
            study.run_entry(self.study_root, 'baseline', 0)

        # Leak must be caught by audit
        with self.assertRaises(GateError) as ctx:
            study.audit(self.study_root)
        self.assertIn('泄漏', str(ctx.exception))

    def test_full_coevolution_workflow_and_clean_plan_convergence(self):
        cfg_path = self.tmp / 'cfg.json'
        write_json(cfg_path, _make_config(self.project, self.code, self.data, self.plan))

        st = study.init(self.study_root, cfg_path, authorization='通宵 3 轮探索，不碰测试集')
        self.assertEqual(st['status'], 'initialized')

        aud = study.audit(self.study_root)
        self.assertTrue(aud['passed'])
        self.assertEqual(aud['summary']['val']['n_groups'], 20)

        # Run baseline across 3 seeds (multi-class BACC, no mean_per_case/binary_auroc block!)
        for seed in (0, 1, 2):
            rec = study.run_entry(self.study_root, 'baseline', seed, phase='formal')
            self.assertEqual(rec['status'], 'completed')
            self.assertIn('bacc', rec['metrics'])
            self.assertIn('macro_f1', rec['metrics'])

        # Run screening on proposed_v1 + simulate one failed run (must NOT deadlock the study)
        scr = study.run_entry(self.study_root, 'proposed_v1', 0, phase='screening')
        self.assertEqual(scr['status'], 'completed')

        fail_cmd = self.tmp / 'fail_cmd.json'
        write_json(fail_cmd, ['{python}', 'train.py', '--model', 'proposed_v1', '--seed', '{seed}', '--fail'])
        failed = study.run_entry(self.study_root, 'proposed_v1', 0, phase='screening', command_json=fail_cmd)
        self.assertEqual(failed['status'], 'failed')
        self.assertIn('非零退出', failed['error'])

        # Simulate external author edit directly on 00_plan/project-plan.md (NO hash lockout!)
        self.plan.write_text('# 研究计划 v1（作者手改补充）\n\n## 3. 方法路线\n\n作者补充备注。\n', encoding='utf-8')

        # Revise route v1 -> v2: replace proposed_v1 with proposed_v2 + add ablation_no_aux
        entries_v2 = self.tmp / 'entries_v2.json'
        write_json(entries_v2, [
            {
                'id': 'baseline',
                'role': 'baseline',
                'description': 'Strong reference baseline',
                'command': ['{python}', 'train.py', '--model', 'baseline', '--seed', '{seed}', '--output-dir', '{output_dir}'],
            },
            {
                'id': 'proposed_v2',
                'role': 'proposed',
                'description': 'Multi-scale fusion route v2',
                'command': ['{python}', 'train.py', '--model', 'proposed_v2', '--seed', '{seed}', '--output-dir', '{output_dir}'],
            },
            {
                'id': 'ablation_no_aux',
                'role': 'ablation',
                'description': 'Ablation removing auxiliary branch',
                'command': ['{python}', 'train.py', '--model', 'ablation_no_aux', '--seed', '{seed}', '--output-dir', '{output_dir}'],
            },
        ])
        plan_v2 = self.tmp / 'plan_v2.md'
        plan_v2.write_text('# 研究计划 v2\n\n## 3. 方法路线\n\n采用 proposed_v2 与 ablation_no_aux。\n', encoding='utf-8')

        rev = study.revise_route(
            self.study_root,
            summary='v1 低于基线，切换为 proposed_v2 并新增消融',
            entries_json=entries_v2,
            hypothesis='v2: multi-scale fusion outperforms baseline on 3-class BACC',
            plan_file=plan_v2,
        )
        self.assertEqual(rev['state']['route_revision'], 2)
        # Baseline automatically reused!
        self.assertIn('baseline', rev['route']['reused_entries'])
        self.assertIn('baseline', rev['state']['valid_entries'])
        self.assertNotIn('proposed_v1', rev['state']['valid_entries'])

        # 00_plan/ must stay completely clean: only project-plan.md, no drafts, no JSON/details junk!
        plan_files = [p.name for p in (self.project / '00_plan').iterdir()]
        self.assertEqual(plan_files, ['project-plan.md'])
        active_plan_text = self.plan.read_text(encoding='utf-8')
        self.assertIn('proposed_v2', active_plan_text)
        self.assertNotIn('<details>', active_plan_text)
        self.assertNotIn('```json', active_plan_text)
        # Previous human-edited v1 plan archived safely!
        archived_prev = Path(rev['route']['plan_sync']['archived_previous'])
        self.assertTrue(archived_prev.is_file())
        self.assertIn('作者手改补充', archived_prev.read_text(encoding='utf-8'))

        # Run proposed_v2 and ablation_no_aux across 3 seeds
        for eid in ('proposed_v2', 'ablation_no_aux'):
            for seed in (0, 1, 2):
                rec = study.run_entry(self.study_root, eid, seed, phase='formal')
                self.assertEqual(rec['status'], 'completed')

        # Locked test MUST be blocked before pretest-check & freeze
        with self.assertRaises(GateError):
            study.run_test(self.study_root, 'proposed_v2')

        # Freeze MUST be blocked before pretest-check pass
        with self.assertRaises(GateError):
            study.freeze(self.study_root, ['baseline', 'proposed_v2'], 'author approves')

        # Block verdict still blocks freeze
        study.pretest_check(self.study_root, 'independent-reviewer', 'block', 'found minor issue')
        with self.assertRaises(GateError):
            study.freeze(self.study_root, ['baseline', 'proposed_v2'], 'author approves')

        # Pass verdict allows freeze
        study.pretest_check(self.study_root, 'independent-reviewer', 'pass',
                            'verified no test leak, split_hash matches, code aligns with v2',
                            ['train.py', 'audit_split.py', 'evaluate_test.py'])
        frz = study.freeze(self.study_root, ['baseline', 'proposed_v2', 'ablation_no_aux'],
                           '作者审阅报告后选定 v2 为最终路线')
        self.assertEqual(frz['route_revision'], 2)

        # Further exploration/revision MUST be blocked after freeze
        with self.assertRaises(GateError):
            study.run_entry(self.study_root, 'proposed_v2', 99)
        with self.assertRaises(GateError):
            study.revise_route(self.study_root, summary='should fail after freeze')

        # Run locked test for frozen entries
        t_base = study.run_test(self.study_root, 'baseline')
        t_prop = study.run_test(self.study_root, 'proposed_v2')
        self.assertIsNone(t_base['error'])
        self.assertIsNone(t_prop['error'])
        self.assertGreater(t_prop['summary']['mean'], t_base['summary']['mean'])

        # Duplicate test on same entry blocked
        with self.assertRaises(GateError):
            study.run_test(self.study_root, 'proposed_v2')

        # Finalize with clean single-route final plan
        final_plan = self.tmp / 'final_plan.md'
        final_plan.write_text('# 最终定稿研究计划（v2 唯一路线）\n\n仅保留最终选定的 proposed_v2 方案与冻结实证结果。\n', encoding='utf-8')
        fin = study.finalize_study(self.study_root, plan_file=final_plan)
        self.assertEqual(fin['status'], 'finalized')
        self.assertEqual([p.name for p in (self.project / '00_plan').iterdir()], ['project-plan.md'])
        self.assertIn('v2 唯一路线', self.plan.read_text(encoding='utf-8'))

        # Downstream previously completed stage marked 需返工, stage 0 untouched
        proj_md = (self.project / 'PROJECT.md').read_text(encoding='utf-8')
        self.assertIn('| 0 | 入口检查 | medpaper-pipeline | 已确认 |', proj_md)
        self.assertIn('| 1 | 图表规划 | medfig-plan | 需返工 |', proj_md)

        # Report generated cleanly
        rep_md = Path(fin['report']['report_md']).read_text(encoding='utf-8')
        self.assertIn('proposed_v2', rep_md)
        self.assertIn('锁定测试集结果', rep_md)
        rep_json = read_json(Path(fin['report']['report_json']))
        self.assertEqual(rep_json['test_looks'], 2)

    def test_max_routes_ceiling_and_cli_smoke(self):
        cfg_path = self.tmp / 'cfg_limit.json'
        write_json(cfg_path, _make_config(self.project, self.code, self.data, self.plan, max_routes=2))
        ctrl = SCRIPTS_DIR / 'controller.py'
        r = subprocess.run(
            [sys.executable, '-X', 'utf8', str(ctrl), 'init', '--root', str(self.study_root), '--config', str(cfg_path)],
            capture_output=True, text=True, encoding='utf-8',
        )
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        study.audit(self.study_root)
        study.revise_route(self.study_root, summary='route 2')
        with self.assertRaises(GateError) as ctx:
            study.revise_route(self.study_root, summary='route 3 exceeds ceiling')
        self.assertIn('上限', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
