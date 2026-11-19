"""Clean, non-polluting plan and project synchronization.

Guarantees:
1. 00_plan/project-plan.md always stays a single, readable Markdown plan synced
   with the current experiment route — no draft files, no raw JSON dumps, and
   no collapsed <details> history corpses inside the active plan.
2. Prior plan versions are archived into _archive/<date>_plan_v<N>/ (or
   <study>/plans/history/ for standalone studies) before replacement.
3. No byte-hash lockout: authors and sibling skills can freely edit
   00_plan/project-plan.md or PROJECT.md without ever blocking the controller.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import shutil

from .common import atomic_text, require, safe_path


def find_project_root(study_root: Path, configured_root: str | None = None) -> Path | None:
    if configured_root:
        root = safe_path(configured_root)
        if (root / 'PROJECT.md').is_file():
            return root
    for parent in safe_path(study_root).parents:
        if (parent / 'PROJECT.md').is_file():
            return parent
    return None


def _next_archive_dir(base_archive: Path, prefix: str) -> Path:
    base_archive.mkdir(parents=True, exist_ok=True)
    cand = base_archive / prefix
    idx = 1
    while cand.exists():
        idx += 1
        cand = base_archive / f'{prefix}_{idx}'
    cand.mkdir(parents=True, exist_ok=True)
    return cand


def archive_and_update_plan(study_root: Path, project_root: Path | None,
                            new_plan_file: Path, route_revision: int) -> dict:
    src = safe_path(new_plan_file)
    require(src.is_file(), f'新计划书文件不存在: {src}')
    content = src.read_text(encoding='utf-8-sig')
    require(content.strip(), '新计划书内容不能为空')

    today = datetime.now().astimezone().date().isoformat()
    archived_to = None

    if project_root is not None:
        target = safe_path(project_root) / '00_plan' / 'project-plan.md'
        if target.is_file():
            arch_dir = _next_archive_dir(safe_path(project_root) / '_archive', f'{today}_plan_v{route_revision - 1}')
            arch_file = arch_dir / '00_plan' / 'project-plan.md'
            arch_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, arch_file)
            archived_to = str(arch_file)
        if src != target:
            atomic_text(target, content)
        # Also keep a clean snapshot in study/plans/history for self-contained study provenance.
        hist = safe_path(study_root) / 'plans' / 'history' / f'plan-v{route_revision:02d}.md'
        atomic_text(hist, content)
        return {'plan_path': str(target), 'archived_previous': archived_to, 'study_snapshot': str(hist)}

    # Standalone study mode (no PROJECT.md)
    hist_dir = safe_path(study_root) / 'plans' / 'history'
    hist_dir.mkdir(parents=True, exist_ok=True)
    active = safe_path(study_root) / 'plans' / 'current-plan.md'
    if active.is_file():
        arch_file = hist_dir / f'plan-v{route_revision - 1:02d}_{today}.md'
        shutil.copy2(active, arch_file)
        archived_to = str(arch_file)
    if src != active:
        atomic_text(active, content)
    return {'plan_path': str(active), 'archived_previous': archived_to, 'study_snapshot': str(active)}


def _replace_block(text: str, marker_key: str, block_body: str) -> str:
    start = f'<!-- medexp:{marker_key}:begin -->'
    end = f'<!-- medexp:{marker_key}:end -->'
    wrapped = f'{start}\n{block_body.rstrip()}\n{end}'
    if start in text and end in text:
        pattern = re.escape(start) + r'.*?' + re.escape(end)
        return re.sub(pattern, lambda _: wrapped, text, count=1, flags=re.S)
    return text.rstrip() + '\n\n' + wrapped + '\n'


def _mark_downstream_rework(project_md: str) -> str:
    lines = project_md.splitlines(keepends=True)
    cols = None
    for idx, line in enumerate(lines):
        if not line.lstrip().startswith('|'):
            cols = None
            continue
        cells = [c.strip() for c in line.strip().split('|')[1:-1]]
        if '阶段' in cells and '状态' in cells:
            cols = (cells.index('阶段'), cells.index('状态'), cells.index('#') if '#' in cells else None)
            continue
        if cols is None or len(cells) <= max(x for x in cols if x is not None):
            continue
        stage_i, status_i, num_i = cols
        num = cells[num_i] if num_i is not None else ''
        stage = cells[stage_i]
        if num == '0' or stage in ('入口检查', '项目入口检查', '课题规划', '开题规划'):
            continue
        if cells[status_i] in ('已确认', '待确认', '完成'):
            cells[status_i] = '需返工'
            lines[idx] = '| ' + ' | '.join(cells) + ' |\n'
    return ''.join(lines)


def sync_project_index(study_root: Path, project_root: Path | None, state: dict,
                       cfg: dict, summary_note: str, mark_rework: bool = False) -> dict:
    if project_root is None:
        return {'synced': False, 'reason': 'standalone study (no PROJECT.md)'}

    proj = safe_path(project_root)
    study = safe_path(study_root)
    rel_study = study.relative_to(proj).as_posix() if study.is_relative_to(proj) else str(study)
    pm_name = cfg['primary_metric']['name']

    # 1. Clean Markdown summary in 01_analysis/README.md
    index_path = proj / '01_analysis' / 'README.md'
    index_text = index_path.read_text(encoding='utf-8-sig') if index_path.is_file() else '# 实验代码与结果总索引\n'

    lines = [
        f'### {cfg["study_id"]}',
        f'- **受管目录**：`{rel_study}`（报告：`{rel_study}/report.md`）',
        f'- **当前状态**：`{state["status"]}` ｜ 路线版本：`v{state["route_revision"]}` ｜ 主指标：`{pm_name}`（{cfg["primary_metric"]["direction"]}）',
        f'- **最新说明**：{summary_note}',
        f'- **测试集状态**：查看次数 `{state.get("test_looks", 0)}`；冻结方案：`{", ".join((state.get("frozen") or {}).get("entries", [])) or "未冻结"}`',
        '',
        f'| 条目 | 角色 | 有效 Seed 数 | 验证集 {pm_name}（均值 ± SD） | 来源路线 |',
        '|---|---|---:|---|---|',
    ]
    valid = state.get('valid_entries', {})
    for entry in cfg['entries']:
        eid = entry['id']
        info = valid.get(eid)
        if info:
            mean_s = f'{info["mean"]:.4g}'
            sd_s = f'{info["sd"]:.4g}' if info['n_seeds'] >= 2 else '—'
            lines.append(f'| `{eid}` | {entry["role"]} | {info["n_seeds"]} | {mean_s} ± {sd_s} | v{info["route_revision"]} |')
        else:
            lines.append(f'| `{eid}` | {entry["role"]} | 0 | 待运行 | — |')

    new_index = _replace_block(index_text, f'study-{cfg["study_id"]}', '\n'.join(lines))
    atomic_text(index_path, new_index)

    # 2. Gentle, non-blocking changelog line in PROJECT.md
    proj_md_path = proj / 'PROJECT.md'
    proj_text = proj_md_path.read_text(encoding='utf-8-sig')
    if mark_rework:
        proj_text = _mark_downstream_rework(proj_text)
    today = datetime.now().astimezone().date().isoformat()
    log_line = f'- {today} 实验 `{cfg["study_id"]}`（v{state["route_revision"]} / `{state["status"]}`）：{summary_note}'
    if '## 变更记录' in proj_text:
        proj_text = proj_text.rstrip() + '\n' + log_line + '\n'
    else:
        proj_text = proj_text.rstrip() + '\n\n## 变更记录\n\n' + log_line + '\n'
    atomic_text(proj_md_path, proj_text)

    return {'synced': True, 'index': str(index_path), 'project_md': str(proj_md_path)}
