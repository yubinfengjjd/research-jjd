#!/usr/bin/env python3
"""Lightweight, zero-dependency checker for rolling medical research plans.

Checks that project-plan.md is clean, readable, scientifically grounded,
free of leftover template placeholders or raw JSON/details pollution, and
(optionally) aligned with a medimg-experiment v3 study-config.json.

Exit 0: checks pass (warnings may still be reported).
Exit 1: blocking errors found.
Exit 2: invalid CLI arguments or unreadable input file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


CORE_SECTION_PATTERNS = [
    ('problem_and_hypothesis', r'问题|假设|背景|motivation|hypothesis|question'),
    ('data_and_split', r'数据|划分|队列|data|split|cohort'),
    ('baseline_or_literature', r'基线|文献|锚点|baseline|literature|anchor'),
    ('method_and_experiment', r'方法|实验|设计|指标|统计|method|experiment|metric'),
    ('budget_or_handoff', r'预算|算力|交接|实施|budget|handoff|compute|engineering'),
    ('risks_or_limitations', r'风险|限制|待办|审稿|risk|limitation|todo|reviewer'),
]

LEAKAGE_PATTERNS = re.compile(
    r'患者|病例|独立单位|防泄漏|不重叠|patient_id|patient-level|group_unit|split_audit|leakage|disjoint',
    re.I,
)
METRIC_PATTERNS = re.compile(
    r'主指标|主要指标|主要终点|primary[_ ]metric|bacc|auroc|auprc|dice|hd95|macro[_-]?f1|c-index|mae|rmse',
    re.I,
)
BASELINE_PATTERNS = re.compile(
    r'基线|对照|baseline|nnU-Net|comparator|参照',
    re.I,
)
TEMPLATE_PLACEHOLDERS = [
    '{研究标题}',
    '交付前删除本提示行与未填占位',
    '[TODO:',
    '填写当前核心研究假设',
]
POLLUTION_PATTERNS = [
    ('<details>', '正文中混入了 <details> 折叠历史残骸，应归档至 _archive/ 而非堆在活跃计划书中'),
    ('<!-- medexp:current-status:begin -->', '正文中残留旧版机器状态投影块，请清理为纯人类可读 Markdown'),
    ('"scientific_contract":', '正文中混入了裸 JSON 契约块，请改用简洁可读文本/表格'),
]


def _extract_h2(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r'^##\s+(.+)$', text, re.M)]


def validate_plan(plan_path: Path, mode: str = 'rolling',
                  study_config_path: Path | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if not plan_path.is_file():
        raise FileNotFoundError(f'计划书不存在: {plan_path}')
    text = plan_path.read_text(encoding='utf-8-sig')
    if not text.strip():
        errors.append('计划书内容为空')
        return {'valid': False, 'errors': errors, 'warnings': warnings}

    # 1. Check H1 title & clean headings
    if not re.search(r'^#\s+\S+', text, re.M):
        errors.append('缺少一级标题（# 研究标题）')
    h2s = _extract_h2(text)
    if len(h2s) < 4:
        errors.append(f'二级主线章节过少（仅 {len(h2s)} 个），建议覆盖问题假设、数据划分、基线文献、方法实验、预算交接与风险限制')

    # 2. Core domain coverage
    joined_h2 = '\n'.join(h2s)
    for label, pat in CORE_SECTION_PATTERNS:
        if not re.search(pat, joined_h2, re.I) and not re.search(pat, text, re.I):
            errors.append(f'缺少核心内容模块: {label}')

    # 3. Scientific guardrails: anti-leakage, primary metric, baseline
    if not LEAKAGE_PATTERNS.search(text):
        errors.append('未说明患者/独立分组单位或防泄漏划分规则')
    if not METRIC_PATTERNS.search(text):
        errors.append('未明确主指标或主要终点')
    if not BASELINE_PATTERNS.search(text):
        warnings.append('未明显提及强基线或对照组，建议明确参照基线')

    # 4. Template placeholders & directory/prose pollution checks
    for token in TEMPLATE_PLACEHOLDERS:
        if token in text:
            errors.append(f'存在未清理的模板占位符: {token}')
    for token, msg in POLLUTION_PATTERNS:
        if token in text:
            errors.append(msg)

    # 5. Mode-specific checks (rolling vs converged)
    has_branches = bool(re.search(r'延伸分支|候选分支|分支\s*A|条件触发', text, re.I))
    if mode == 'rolling' and not has_branches:
        warnings.append('滚动探索期（rolling）建议保留“下一步延伸分支（条件触发）”，避免第 0 天预设单一僵化终局')
    if mode == 'converged' and re.search(r'^##\s+.*延伸分支', text, re.M):
        errors.append('最终定稿模式（converged）应移除“下一步延伸分支”探索节，只保留唯一最终路线')

    # 6. Check sibling 00_plan/ cleanliness if plan lives in 00_plan/
    if plan_path.parent.name == '00_plan':
        junk = [p.name for p in plan_path.parent.iterdir()
                if p.is_file() and ('draft' in p.name.lower() or p.suffix.lower() == '.json')]
        if junk:
            warnings.append(f'00_plan/ 中存在多余草案或 JSON 文件（建议移出以防目录污染）: {", ".join(sorted(junk))}')

    # 7. Optional cross-check with medimg-experiment v3 study-config.json
    config_checked = False
    if study_config_path is not None:
        if not study_config_path.is_file():
            errors.append(f'指定的 study-config.json 不存在: {study_config_path}')
        else:
            cfg = json.loads(study_config_path.read_text(encoding='utf-8-sig'))
            config_checked = True
            if cfg.get('schema_version') != 3:
                errors.append(f'study-config.json 须为 medimg-experiment v3（schema_version=3），当前为 {cfg.get("schema_version")}')
            pm_name = (cfg.get('primary_metric') or {}).get('name')
            if isinstance(pm_name, str) and pm_name.strip():
                if not re.search(re.escape(pm_name.strip()), text, re.I):
                    errors.append(f'study-config.json 的主指标 "{pm_name}" 未出现在计划书正文中')
            group_unit = (cfg.get('data') or {}).get('group_unit')
            if isinstance(group_unit, str) and group_unit.strip():
                if group_unit.lower() not in text.lower() and '患者' not in text and '病例' not in text:
                    warnings.append(f'建议在计划书中显式写出独立划分单位 "{group_unit}"')
            ref_id = cfg.get('reference')
            if isinstance(ref_id, str) and ref_id.strip() and ref_id.lower() not in text.lower():
                warnings.append(f'study-config.json 的参照基线条目 "{ref_id}" 未在计划书中显式命名')

    return {
        'valid': not errors,
        'plan': str(plan_path.resolve()),
        'mode': mode,
        'h2_count': len(h2s),
        'config_checked': config_checked,
        'errors': errors,
        'warnings': warnings,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='轻量检查医学科研滚动计划书的完整性、防泄漏要素与实验交接对齐')
    parser.add_argument('plan', type=Path, help='计划书 Markdown 路径（如 00_plan/project-plan.md）')
    parser.add_argument('--mode', choices=('rolling', 'converged'), default='rolling',
                        help='rolling=探索滚动期（默认）；converged=实验结束最终定稿')
    parser.add_argument('--study-config', type=Path, default=None,
                        help='可选：配套 medimg-experiment v3 study-config.json，校验口径对齐')
    parser.add_argument('--output', type=Path, default=None, help='可选：将检查报告写入 JSON 文件')
    args = parser.parse_args(argv)

    try:
        report = validate_plan(args.plan, mode=args.mode, study_config_path=args.study_config)
    except Exception as exc:
        print(json.dumps({'valid': False, 'error': str(exc)}, ensure_ascii=False))
        return 2

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
