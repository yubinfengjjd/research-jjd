"""Lightweight schema-v3 study configuration validation.

Locks only the three scientific guardrails (split integrity, locked test set,
and primary metric identity) while allowing methods, entries, architectures,
and ablations to co-evolve cleanly with the research plan.
"""
from __future__ import annotations

from pathlib import Path
import re

from .common import is_windows_store_python, number, parse_utc, require, safe_path

ROLES = ('baseline', 'proposed', 'ablation', 'comparison')
ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def _nonempty_str(obj: dict, key: str, label: str | None = None) -> str:
    val = obj.get(key)
    require(isinstance(val, str) and val.strip(), f'缺少非空字段: {label or key}')
    return val.strip()


def _abs_path(value, label: str) -> Path:
    require(isinstance(value, str) and value.strip() and Path(value).is_absolute(),
            f'{label} 必须是明确的绝对路径')
    return safe_path(value)


def validate_command(command, label: str, required_placeholders: tuple[str, ...] = ()) -> list[str]:
    require(isinstance(command, list) and len(command) >= 1
            and all(isinstance(arg, str) and arg for arg in command),
            f'{label} 必须为非空 argv 字符串数组')
    for token in required_placeholders:
        require(any(token in arg for arg in command), f'{label} 必须包含占位符 {token}')
    return list(command)


def validate_entries(entries, reference: str) -> list[dict]:
    require(isinstance(entries, list) and entries, 'entries 必须至少包含一个实验条目')
    seen = set()
    by_id = {}
    for entry in entries:
        require(isinstance(entry, dict), '每个实验条目必须为对象')
        eid = _nonempty_str(entry, 'id', 'entry.id')
        require(ID_RE.fullmatch(eid) is not None and eid not in seen, f'实验条目 id 无效或重复: {eid}')
        seen.add(eid)
        role = entry.get('role')
        require(role in ROLES, f'条目 {eid} 的 role 必须属于 {ROLES}')
        _nonempty_str(entry, 'description', f'entry[{eid}].description')
        validate_command(entry.get('command'), f'entry[{eid}].command')
        if entry.get('screening_command') is not None:
            validate_command(entry['screening_command'], f'entry[{eid}].screening_command')
        by_id[eid] = entry
    require(reference in by_id and by_id[reference]['role'] == 'baseline',
            'reference 必须指向 entries 中一个 role="baseline" 的条目')
    return entries


def validate_config(cfg: dict) -> dict:
    require(isinstance(cfg, dict), '配置必须为 JSON 对象')
    require(cfg.get('schema_version') == 3, '仅支持 schema_version=3 轻量配置；请参考 assets/study-config-template.json')
    sid = _nonempty_str(cfg, 'study_id')
    require(ID_RE.fullmatch(sid) is not None, 'study_id 须为 1–64 位字母/数字/下划线/连字符')
    _nonempty_str(cfg, 'task', 'task（如 multiclass_classification / 3d_segmentation / regression）')
    _nonempty_str(cfg, 'hypothesis')

    plan_path = _abs_path(cfg.get('plan_path'), 'plan_path')
    require(plan_path.is_file(), f'初始计划书不存在: {plan_path}')

    if cfg.get('project_root') is not None:
        proj = _abs_path(cfg['project_root'], 'project_root')
        require(proj.is_dir(), f'project_root 目录不存在: {proj}')

    code_dir = _abs_path(cfg.get('code_dir'), 'code_dir')
    require(code_dir.is_dir(), f'code_dir 目录不存在: {code_dir}')

    pm = cfg.get('primary_metric')
    require(isinstance(pm, dict), '缺少 primary_metric')
    _nonempty_str(pm, 'name', 'primary_metric.name')
    require(pm.get('direction') in ('higher', 'lower'), 'primary_metric.direction 必须为 higher 或 lower')
    if pm.get('target') is not None:
        number(pm['target'], 'primary_metric.target')

    sec = cfg.get('secondary_metrics', [])
    require(isinstance(sec, list), 'secondary_metrics 必须为列表')
    for item in sec:
        require(isinstance(item, dict), 'secondary_metrics 元素必须为对象')
        _nonempty_str(item, 'name', 'secondary_metrics[].name')
        require(item.get('direction') in ('higher', 'lower'), 'secondary_metrics[].direction 必须为 higher 或 lower')

    data = cfg.get('data')
    require(isinstance(data, dict), '缺少 data 配置')
    paths = data.get('paths')
    require(isinstance(paths, list) and paths, 'data.paths 必须至少提供一个数据路径')
    for p in paths:
        require(_abs_path(p, 'data.paths').exists(), f'数据路径不存在: {p}')
    for key in ('group_unit', 'labels_source', 'split_reference'):
        _nonempty_str(data, key, f'data.{key}')

    audit = cfg.get('split_audit')
    require(isinstance(audit, dict), '缺少 split_audit 配置（划分防泄漏是固定红线）')
    validate_command(audit.get('command'), 'split_audit.command', required_placeholders=('{output}',))
    number(audit.get('timeout_seconds', 120), 'split_audit.timeout_seconds', positive=True)

    test = cfg.get('test')
    require(isinstance(test, dict) and test.get('policy') in ('locked', 'none'),
            'test.policy 必须为 locked 或 none')
    if test['policy'] == 'locked':
        _nonempty_str(test, 'reference', 'test.reference')
        validate_command(test.get('command'), 'test.command', required_placeholders=('{run_dir}', '{output}'))
        number(test.get('timeout_seconds', 600), 'test.timeout_seconds', positive=True)
    else:
        _nonempty_str(test, 'rationale', 'test.rationale（不设锁定测试集时须说明原因）')

    ref = _nonempty_str(cfg, 'reference', 'reference（参照基线条目 id）')
    validate_entries(cfg.get('entries'), ref)

    seeds = cfg.get('seeds')
    require(isinstance(seeds, list) and len(seeds) >= 1 and len(seeds) == len(set(seeds))
            and all(isinstance(x, int) and not isinstance(x, bool) for x in seeds),
            'seeds 必须为非空且不重复的整数列表（正式比较推荐 >=3 个 seed）')

    budgets = cfg.get('budgets')
    require(isinstance(budgets, dict), '缺少 budgets 配置')
    number(budgets.get('max_training_seconds'), 'budgets.max_training_seconds', positive=True)
    number(budgets.get('run_timeout_seconds'), 'budgets.run_timeout_seconds', positive=True)
    max_routes = budgets.get('max_routes')
    require(isinstance(max_routes, int) and not isinstance(max_routes, bool) and max_routes >= 1,
            'budgets.max_routes 必须为 >=1 的整数')
    if budgets.get('deadline_utc') is not None:
        parse_utc(budgets['deadline_utc'])

    env = cfg.get('environment')
    require(isinstance(env, dict), '缺少 environment 配置')
    py = _abs_path(env.get('python'), 'environment.python')
    require(py.is_file(), f'Python 解释器不存在: {py}')
    require(not is_windows_store_python(py), '禁止使用 WindowsApps 的 Python 占位程序，请指定真实解释器绝对路径')
    require(env.get('device') in ('cuda', 'cpu', 'mps'), 'environment.device 必须为 cuda / cpu / mps')
    require(isinstance(env.get('inherit_cache', True), bool), 'environment.inherit_cache 必须为布尔值')

    ci = cfg.get('ci')
    if ci is not None:
        require(isinstance(ci, dict), 'ci 必须为对象或 null')
        require(ci.get('statistic') in ('mean_per_case', 'binary_auroc'),
                '可选 ci.statistic 目前支持 mean_per_case 或 binary_auroc；其他指标可设为 null')
        resamples = ci.get('resamples', 1000)
        require(isinstance(resamples, int) and 200 <= resamples <= 100000, 'ci.resamples 须在 200–100000 之间')
        level = ci.get('level', 0.95)
        require(isinstance(level, (int, float)) and 0.5 < level < 1.0, 'ci.level 须在 (0.5, 1) 之间')
        seed = ci.get('seed', 42)
        require(isinstance(seed, int) and not isinstance(seed, bool), 'ci.seed 必须为整数')

    return cfg
