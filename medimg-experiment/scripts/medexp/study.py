"""Lightweight, co-evolving medical imaging experiment controller (v3).

Enforces the three scientific guardrails:
  1. Disjoint patient/group split audit before any training.
  2. Locked test set isolation (accessible only after independent pre-test
     check and explicit author freeze; test results never feed back into search).
  3. Honest, append-only run & route ledgers with cumulative budget tracking.

Everything else stays lightweight: any task/metric, local pretrained cache
inheritance, flexible route & entry revision with baseline reuse, and clean
plan synchronization with zero directory pollution.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from .common import (
    GateError, atomic_text, digest_json, inside, load_state, locked, number,
    parse_utc, read_json, require, safe_path, save_state, sha256_file,
    timestamp, write_json,
)
from .config import validate_command, validate_config, validate_entries
from .plan_sync import archive_and_update_plan, find_project_root, sync_project_index
from .process import OwnedProcess
from . import stats


def _git_head(code_dir: Path) -> str | None:
    try:
        r = subprocess.run(
            ['git', '-C', str(code_dir), 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000 if os.name == 'nt' else 0,
        )
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except OSError:
        return None


def _check_environment(cfg: dict) -> dict:
    env_cfg = cfg['environment']
    py = str(safe_path(env_cfg['python']))
    r = subprocess.run(
        [py, '-X', 'utf8', '-c', 'import sys; print(sys.executable); print(sys.version.split()[0])'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
        creationflags=0x08000000 if os.name == 'nt' else 0,
    )
    require(r.returncode == 0, f'Python 解释器不可用: {r.stderr[-500:]}')
    lines = [x.strip() for x in r.stdout.splitlines() if x.strip()]
    info = {'python': lines[0] if lines else py, 'python_version': lines[1] if len(lines) > 1 else 'unknown',
            'device': env_cfg['device']}
    if env_cfg['device'] == 'cuda':
        rc = subprocess.run(
            [py, '-X', 'utf8', '-c',
             'import torch; assert torch.cuda.is_available(), "CUDA unavailable"; print(torch.cuda.get_device_name(0))'],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
            creationflags=0x08000000 if os.name == 'nt' else 0,
        )
        require(rc.returncode == 0, f'配置的 CUDA 设备不可用（不静默降级 CPU）: {rc.stderr[-500:]}')
        info['gpu'] = rc.stdout.strip()
    return info


def _remaining_budget(cfg: dict, state: dict) -> tuple[float, float | None]:
    spent = float(state.get('training_spent_seconds', 0.0))
    rem_train = float(cfg['budgets']['max_training_seconds']) - spent
    rem_deadline = None
    if cfg['budgets'].get('deadline_utc'):
        rem_deadline = (parse_utc(cfg['budgets']['deadline_utc']) - datetime.now(timezone.utc)).total_seconds()
    return rem_train, rem_deadline


def _build_env(cfg: dict, extra: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env['PYTHONUTF8'] = '1'
    env['PYTHONUNBUFFERED'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env.setdefault('WANDB_MODE', 'disabled')
    if not cfg['environment'].get('inherit_cache', True):
        cache_dir = extra.get('ME_CACHE_DIR')
        if cache_dir:
            env['TORCH_HOME'] = cache_dir
            env['HF_HOME'] = cache_dir
            env['TIMM_CACHE_DIR'] = cache_dir
    env.update(extra)
    return env


def _expand_argv(template: list[str], mapping: dict[str, str]) -> list[str]:
    out = []
    for token in template:
        val = token
        for k, v in mapping.items():
            val = val.replace(k, v)
        out.append(val)
    return out


def _append_route(root: Path, record: dict) -> None:
    with (root / 'routes.jsonl').open('a', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + '\n')
        fh.flush()
        os.fsync(fh.fileno())


def _load_routes(root: Path) -> list[dict]:
    p = root / 'routes.jsonl'
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]


def _summarize_entry_runs(root: Path, cfg: dict, entry_id: str, route_revision: int) -> dict | None:
    pm = cfg['primary_metric']['name']
    higher = cfg['primary_metric']['direction'] == 'higher'
    completed = []
    for rec_path in sorted((root / 'runs').glob('*/record.json')):
        rec = read_json(rec_path)
        if (rec.get('entry') == entry_id and rec.get('phase') == 'formal'
                and rec.get('status') == 'completed' and not rec.get('invalidated')
                and rec.get('route_revision') == route_revision):
            completed.append(rec)
    if not completed:
        return None
    # Keep latest completed run per seed if retried
    by_seed = {}
    for rec in completed:
        by_seed[rec['seed']] = rec
    ordered = [by_seed[s] for s in sorted(by_seed)]
    vals = [float(r['primary_value']) for r in ordered]
    sec_summary = {}
    for sec in cfg.get('secondary_metrics', []):
        name = sec['name']
        svals = [float(r['metrics'][name]) for r in ordered if name in r.get('metrics', {})]
        if svals:
            sec_summary[name] = {
                'mean': stats.aggregate(svals, 'mean', sec['direction'] == 'higher'),
                'sd': stats.seed_sd(svals),
            }
    return {
        'entry': entry_id,
        'route_revision': route_revision,
        'n_seeds': len(ordered),
        'seeds': [r['seed'] for r in ordered],
        'run_ids': [r['run_id'] for r in ordered],
        'values': vals,
        'mean': stats.aggregate(vals, 'mean', higher),
        'median': stats.aggregate(vals, 'median', higher),
        'sd': stats.seed_sd(vals),
        'secondary': sec_summary,
        'primary_metric': pm,
        'updated_at': timestamp(),
    }


# ---------------------------------------------------------------------------
# 1. init
# ---------------------------------------------------------------------------

def init(root: Path, config_path: Path, authorization: str | None = None) -> dict:
    root = safe_path(root)
    require(not root.exists(), f'实验输出目录已存在，请使用全新目录: {root}')
    cfg = validate_config(read_json(config_path))
    for data_p in cfg['data']['paths']:
        require(not root.is_relative_to(safe_path(data_p)), '实验输出目录不能位于原始数据目录内')

    env_info = _check_environment(cfg)
    proj_root = find_project_root(root, cfg.get('project_root'))

    root.mkdir(parents=True)
    for sub in ('plans/history', 'runs', 'tests', 'evidence'):
        (root / sub).mkdir(parents=True, exist_ok=True)

    plan_src = safe_path(cfg['plan_path'])
    shutil.copy2(plan_src, root / 'plans' / 'initial-plan.md')
    shutil.copy2(plan_src, root / 'plans' / 'history' / 'plan-v01.md')
    write_json(root / 'config.json', cfg)

    state = {
        'schema_version': 3,
        'study_id': cfg['study_id'],
        'status': 'initialized',
        'route_revision': 1,
        'created_at': timestamp(),
        'authorization': (authorization or '').strip() or 'author-initiated',
        'project_root': str(proj_root) if proj_root else None,
        'initial_plan_sha256': sha256_file(root / 'plans' / 'initial-plan.md'),
        'environment': env_info,
        'audit': None,
        'training_spent_seconds': 0.0,
        'valid_entries': {},
        'pretest_check': None,
        'frozen': None,
        'test_looks': 0,
        'tests': [],
    }
    save_state(root, state, 'initialized')
    _append_route(root, {
        'route_revision': 1,
        'time': timestamp(),
        'summary': '初始研究路线（v1）',
        'hypothesis': cfg['hypothesis'],
        'entries': [e['id'] for e in cfg['entries']],
        'reused_entries': [],
        'code_commit': _git_head(safe_path(cfg['code_dir'])),
    })
    sync_project_index(root, proj_root, state, cfg, '初始化实验课题（v1），待执行划分防泄漏审计')
    return state


# ---------------------------------------------------------------------------
# 2. audit
# ---------------------------------------------------------------------------

def audit(root: Path) -> dict:
    root = safe_path(root)
    with locked(root):
        state = load_state(root)
        cfg = read_json(root / 'config.json')
        require(state.get('frozen') is None, '方案已冻结，禁止重新审计划分')
        require(state.get('audit') is None, '划分审计已通过并锁定；更改划分须新建课题以避免混用证据')

        out_path = root / 'evidence' / f'split-audit-{uuid.uuid4().hex[:8]}.json'
        log_path = out_path.with_suffix('.log')
        py = str(safe_path(cfg['environment']['python']))
        argv = _expand_argv(cfg['split_audit']['command'], {'{python}': py, '{output}': str(out_path)})
        env = _build_env(cfg, {'ME_PHASE': 'audit', 'ME_STUDY_ROOT': str(root)})

        proc = OwnedProcess(argv, str(safe_path(cfg['code_dir'])), env, str(log_path))
        try:
            code = proc.wait(timeout=float(cfg['split_audit'].get('timeout_seconds', 120)))
        except subprocess.TimeoutExpired:
            proc.terminate()
            raise GateError(f'划分审计超时，详见日志: {log_path}')
        finally:
            proc.close()

        require(code == 0, f'划分审计脚本退出码 {code}，详见日志: {log_path}')
        require(out_path.is_file(), f'划分审计脚本未生成输出 JSON: {out_path}')
        data = read_json(out_path)
        require(data.get('group_unit') == cfg['data']['group_unit'],
                f'审计 group_unit ({data.get("group_unit")}) 与配置 ({cfg["data"]["group_unit"]}) 不一致')
        splits = data.get('splits')
        needed = ['train', 'val'] + (['test'] if cfg['test']['policy'] == 'locked' else [])
        require(isinstance(splits, dict) and all(k in splits for k in needed),
                f'划分审计缺少必需分集: {", ".join(needed)}')

        seen = {}
        summary = {}
        canonical_ids = {}
        for name, info in splits.items():
            ids = info.get('group_ids')
            require(isinstance(ids, list) and ids and all(isinstance(x, str) and x for x in ids),
                    f'{name} 缺少非空字符串列表 group_ids')
            require(len(ids) == len(set(ids)), f'{name} 内部存在重复 group_id')
            for gid in ids:
                require(gid not in seen, f'检测到跨划分泄漏：分组 {gid} 同时出现在 {seen.get(gid)} 与 {name}')
                seen[gid] = name
            canonical_ids[name] = sorted(ids)
            summary[name] = {
                'n_groups': len(ids),
                'class_counts': info.get('class_counts'),
            }

        audit_rec = {
            'passed': True,
            'time': timestamp(),
            'path': str(out_path),
            'group_unit': data['group_unit'],
            'split_hash': digest_json(canonical_ids),
            'summary': summary,
        }
        state['audit'] = audit_rec
        state['status'] = 'exploring'
        save_state(root, state, 'split_audit_passed')
        proj_root = find_project_root(root, state.get('project_root'))
        sync_project_index(root, proj_root, state, cfg, '划分防泄漏审计通过，已锁定 split_hash，进入探索实验')
        return audit_rec


# ---------------------------------------------------------------------------
# 3. run
# ---------------------------------------------------------------------------

def run_entry(root: Path, entry_id: str, seed: int, phase: str = 'formal',
              command_json: Path | None = None) -> dict:
    root = safe_path(root)
    require(phase in ('screening', 'formal'), 'phase 必须为 screening 或 formal')
    with locked(root):
        state = load_state(root)
        cfg = read_json(root / 'config.json')
        require(state.get('audit') and state['audit'].get('passed'), '请先运行 audit 通过划分防泄漏检查，再开始训练')
        require(state.get('frozen') is None and state.get('status') != 'finalized',
                '当前方案已冻结或定稿，禁止继续探索训练')
        entry = next((e for e in cfg['entries'] if e['id'] == entry_id), None)
        require(entry is not None, f'条目 {entry_id} 不在当前路线配置中')

        rem_train, rem_deadline = _remaining_budget(cfg, state)
        require(rem_train > 0, f'累计训练时长预算已用尽 ({state["training_spent_seconds"]:.1f}s / {cfg["budgets"]["max_training_seconds"]}s)')
        if rem_deadline is not None:
            require(rem_deadline > 0, f'整体截止时间已到 ({cfg["budgets"]["deadline_utc"]})')

        if command_json is not None:
            cmd_template = validate_command(read_json(command_json), 'command_json')
        elif phase == 'screening' and entry.get('screening_command'):
            cmd_template = list(entry['screening_command'])
        else:
            cmd_template = list(entry['command'])

        run_id = f'r-{uuid.uuid4().hex[:10]}'
        run_dir = root / 'runs' / run_id
        run_dir.mkdir(parents=True)
        tmp_dir = run_dir / 'tmp'
        tmp_dir.mkdir()
        cache_dir = run_dir / 'cache'
        if not cfg['environment'].get('inherit_cache', True):
            cache_dir.mkdir()

        py = str(safe_path(cfg['environment']['python']))
        argv = _expand_argv(cmd_template, {
            '{python}': py,
            '{seed}': str(seed),
            '{output_dir}': str(run_dir),
            '{entry}': entry_id,
            '{phase}': phase,
        })
        env = _build_env(cfg, {
            'ME_RUN_ID': run_id,
            'ME_ENTRY': entry_id,
            'ME_PHASE': phase,
            'ME_SEED': str(seed),
            'ME_OUTPUT_DIR': str(run_dir),
            'ME_STUDY_ROOT': str(root),
            'ME_DEVICE': cfg['environment']['device'],
            'ME_SPLIT_HASH': state['audit']['split_hash'],
            'ME_CACHE_DIR': str(cache_dir),
            'TMP': str(tmp_dir),
            'TEMP': str(tmp_dir),
        })

        timeout = min(float(cfg['budgets']['run_timeout_seconds']), rem_train)
        if rem_deadline is not None:
            timeout = min(timeout, rem_deadline)

        record = {
            'run_id': run_id,
            'entry': entry_id,
            'role': entry['role'],
            'phase': phase,
            'seed': seed,
            'route_revision': state['route_revision'],
            'command': argv,
            'code_commit': _git_head(safe_path(cfg['code_dir'])),
            'split_hash': state['audit']['split_hash'],
            'status': 'running',
            'started_at': timestamp(),
            'finished_at': None,
            'elapsed_seconds': 0.0,
            'exit_code': None,
            'primary_metric': cfg['primary_metric']['name'],
            'primary_value': None,
            'metrics': {},
            'artifacts': [],
            'notes': None,
            'error': None,
            'invalidated': False,
        }
        write_json(run_dir / 'record.json', record)

    # Execute outside the short state lock so status inspection stays responsive.
    log_path = run_dir / 'train.log'
    t0 = time.monotonic()
    exit_code = None
    error_msg = None
    proc = OwnedProcess(argv, str(safe_path(cfg['code_dir'])), env, str(log_path))
    try:
        exit_code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.terminate()
        error_msg = f'训练超时（>{timeout:.1f}s），已终止进程树并保留日志'
    except Exception as exc:
        proc.terminate()
        error_msg = f'进程执行异常: {type(exc).__name__}: {exc}'
    finally:
        proc.close()
    elapsed = time.monotonic() - t0

    # Parse result.json cleanly; never hard-crash the study on a failed run!
    metrics = {}
    primary_val = None
    artifacts = []
    notes = None
    cases_file = None

    if error_msg is None and exit_code != 0:
        error_msg = f'训练脚本非零退出（exit_code={exit_code}），详见 train.log'

    if error_msg is None:
        result_path = run_dir / 'result.json'
        if not result_path.is_file():
            error_msg = '训练进程退出码 0，但未在 ME_OUTPUT_DIR 生成 result.json'
        else:
            try:
                res = read_json(result_path)
                raw_metrics = res.get('metrics')
                require(isinstance(raw_metrics, dict), 'result.json 必须包含 metrics 对象')
                pm_name = cfg['primary_metric']['name']
                require(pm_name in raw_metrics, f'result.json 缺少主指标 {pm_name}')
                primary_val = number(raw_metrics[pm_name], f'metrics.{pm_name}')
                for k, v in raw_metrics.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        metrics[k] = float(v)
                if isinstance(res.get('artifacts'), list):
                    artifacts = [str(x) for x in res['artifacts']]
                if isinstance(res.get('notes'), str):
                    notes = res['notes']
                # Optional cases.jsonl presence check (never mandatory for multi-class/global metrics)
                cpath = res.get('cases_path')
                cand_cases = inside(run_dir, cpath) if isinstance(cpath, str) and cpath else (run_dir / 'cases.jsonl')
                if cand_cases.is_file():
                    cases_file = str(cand_cases)
            except Exception as exc:
                error_msg = f'解析 result.json 失败: {exc}'

    status_val = 'completed' if error_msg is None else 'failed'
    record.update(
        status=status_val,
        finished_at=timestamp(),
        elapsed_seconds=round(elapsed, 3),
        exit_code=exit_code,
        primary_value=primary_val,
        metrics=metrics,
        artifacts=artifacts,
        notes=notes,
        cases_file=cases_file,
        error=error_msg,
    )
    write_json(run_dir / 'record.json', record)

    with locked(root):
        state = load_state(root)
        cfg = read_json(root / 'config.json')
        state['training_spent_seconds'] = round(float(state.get('training_spent_seconds', 0.0)) + elapsed, 3)
        if status_val == 'completed' and phase == 'formal':
            summary = _summarize_entry_runs(root, cfg, entry_id, state['route_revision'])
            if summary:
                state['valid_entries'][entry_id] = summary
        save_state(root, state, f'run_{status_val}:{entry_id}:seed={seed}')
        proj_root = find_project_root(root, state.get('project_root'))
        note = (f'完成 `{entry_id}` ({phase}, seed={seed}): {cfg["primary_metric"]["name"]}={primary_val:.4g}'
                if status_val == 'completed'
                else f'`{entry_id}` ({phase}, seed={seed}) 失败：{error_msg}')
        sync_project_index(root, proj_root, state, cfg, note)
    return record


# ---------------------------------------------------------------------------
# 4. revise (Plan <-> Experiment co-evolution)
# ---------------------------------------------------------------------------

def revise_route(root: Path, summary: str, entries_json: Path | None = None,
                 reference: str | None = None, hypothesis: str | None = None,
                 plan_file: Path | None = None,
                 reusable_entries: list[str] | None = None,
                 invalidate_entries: list[str] | None = None) -> dict:
    root = safe_path(root)
    require(isinstance(summary, str) and summary.strip(), '必须写明本次修订路线的诊断原因与变动摘要')
    with locked(root):
        state = load_state(root)
        cfg = read_json(root / 'config.json')
        require(state.get('frozen') is None and state.get('status') != 'finalized',
                '当前方案已冻结或定稿，禁止自动修订路线')
        max_routes = int(cfg['budgets']['max_routes'])
        next_rev = int(state['route_revision']) + 1
        require(next_rev <= max_routes, f'已达到授权路线修订上限（{max_routes} 轮）；请向作者汇报当前结果')

        old_entries = {e['id']: e for e in cfg['entries']}
        new_cfg = copy.deepcopy(cfg)
        if entries_json is not None:
            new_entries = read_json(entries_json)
            new_ref = reference or new_cfg['reference']
            validate_entries(new_entries, new_ref)
            new_cfg['entries'] = new_entries
            new_cfg['reference'] = new_ref
        elif reference is not None:
            validate_entries(new_cfg['entries'], reference)
            new_cfg['reference'] = reference

        if hypothesis and hypothesis.strip():
            new_cfg['hypothesis'] = hypothesis.strip()

        new_entry_map = {e['id']: e for e in new_cfg['entries']}
        inv_set = set(invalidate_entries or [])
        explicit_reuse = set(reusable_entries or [])

        # Preserve unaffected entries (e.g., unchanged baseline/comparison); drop removed or invalidated entries.
        kept_valid = {}
        reused = []
        for eid, info in state.get('valid_entries', {}).items():
            if eid not in new_entry_map or eid in inv_set:
                continue
            same_cmd = old_entries.get(eid, {}).get('command') == new_entry_map[eid].get('command')
            if eid in explicit_reuse or (same_cmd and new_entry_map[eid]['role'] in ('baseline', 'comparison')):
                kept_valid[eid] = {**info, 'reused_in_revision': next_rev}
                reused.append(eid)

        state['route_revision'] = next_rev
        state['valid_entries'] = kept_valid
        state['pretest_check'] = None  # Any route change requires a fresh pre-test check before freezing
        write_json(root / 'config.json', new_cfg)

        proj_root = find_project_root(root, state.get('project_root'))
        plan_sync_res = None
        if plan_file is not None:
            plan_sync_res = archive_and_update_plan(root, proj_root, plan_file, next_rev)

        route_rec = {
            'route_revision': next_rev,
            'time': timestamp(),
            'summary': summary.strip(),
            'hypothesis': new_cfg['hypothesis'],
            'entries': [e['id'] for e in new_cfg['entries']],
            'reused_entries': reused,
            'invalidated_entries': sorted(inv_set),
            'code_commit': _git_head(safe_path(new_cfg['code_dir'])),
            'plan_sync': plan_sync_res,
        }
        _append_route(root, route_rec)
        save_state(root, state, f'route_revised_v{next_rev}')
        sync_project_index(root, proj_root, state, new_cfg,
                           f'修订至路线 v{next_rev}：{summary.strip()}（复用：{", ".join(reused) or "无"}）')
        return {'state': state, 'route': route_rec}


# ---------------------------------------------------------------------------
# 5. status
# ---------------------------------------------------------------------------

def status(root: Path) -> dict:
    root = safe_path(root)
    state = load_state(root)
    cfg = read_json(root / 'config.json')
    rem_train, rem_deadline = _remaining_budget(cfg, state)
    return {
        'study_id': state['study_id'],
        'status': state['status'],
        'route_revision': state['route_revision'],
        'max_routes': cfg['budgets']['max_routes'],
        'audit_passed': bool((state.get('audit') or {}).get('passed')),
        'split_hash': (state.get('audit') or {}).get('split_hash'),
        'primary_metric': cfg['primary_metric'],
        'training_spent_seconds': state['training_spent_seconds'],
        'training_remaining_seconds': round(max(0.0, rem_train), 2),
        'deadline_remaining_seconds': round(rem_deadline, 2) if rem_deadline is not None else None,
        'entries': [e['id'] for e in cfg['entries']],
        'valid_entries': state.get('valid_entries', {}),
        'pretest_check': state.get('pretest_check'),
        'frozen': state.get('frozen'),
        'test_looks': state.get('test_looks', 0),
        'tests': state.get('tests', []),
    }


# ---------------------------------------------------------------------------
# 6. pretest-check (Single independent read-only check before freezing/testing)
# ---------------------------------------------------------------------------

def pretest_check(root: Path, reviewer: str, verdict: str, summary: str,
                  checked_files: list[str] | None = None) -> dict:
    root = safe_path(root)
    require(isinstance(reviewer, str) and reviewer.strip(), '请提供核查者标识（如独立子代理/审阅者名）')
    require(verdict in ('pass', 'block'), 'verdict 必须为 pass 或 block')
    require(isinstance(summary, str) and summary.strip(), '请写明核查结论与依据')
    with locked(root):
        state = load_state(root)
        cfg = read_json(root / 'config.json')
        require(state.get('audit') and state['audit'].get('passed'), '划分审计尚未通过，不能执行测试前核查')
        rec = {
            'reviewer': reviewer.strip(),
            'verdict': verdict,
            'summary': summary.strip(),
            'checked_files': list(checked_files or []),
            'route_revision': state['route_revision'],
            'code_commit': _git_head(safe_path(cfg['code_dir'])),
            'time': timestamp(),
        }
        write_json(root / 'evidence' / f'pretest-check-v{state["route_revision"]:02d}-{uuid.uuid4().hex[:6]}.json', rec)
        state['pretest_check'] = rec
        save_state(root, state, f'pretest_check_{verdict}')
        return rec


# ---------------------------------------------------------------------------
# 7. freeze (Author selects winning route & entries before locked test)
# ---------------------------------------------------------------------------

def freeze(root: Path, entry_ids: list[str], statement: str) -> dict:
    root = safe_path(root)
    require(bool(entry_ids), '请至少指定一个要冻结的条目 id')
    require(isinstance(statement, str) and statement.strip(), '必须记录作者选定最终路线的确认语句')
    with locked(root):
        state = load_state(root)
        cfg = read_json(root / 'config.json')
        require(state.get('frozen') is None, '当前课题已经冻结')
        check = state.get('pretest_check')
        require(check and check.get('verdict') == 'pass' and check.get('route_revision') == state['route_revision'],
                '冻结前必须完成当前路线的独立测试前核查（pretest-check --verdict pass）')

        valid = state.get('valid_entries', {})
        frozen_runs = {}
        for eid in entry_ids:
            require(eid in valid and valid[eid].get('run_ids'), f'条目 {eid} 尚无有效的正式验证运行，不能冻结')
            frozen_runs[eid] = list(valid[eid]['run_ids'])

        frozen_info = {
            'route_revision': state['route_revision'],
            'entries': list(entry_ids),
            'run_ids_by_entry': frozen_runs,
            'statement': statement.strip(),
            'pretest_check': check,
            'code_commit': _git_head(safe_path(cfg['code_dir'])),
            'time': timestamp(),
        }
        state['frozen'] = frozen_info
        state['status'] = 'frozen'
        save_state(root, state, 'route_frozen_for_test')
        proj_root = find_project_root(root, state.get('project_root'))
        sync_project_index(root, proj_root, state, cfg,
                           f'已冻结最终路线 v{state["route_revision"]}（条目：{", ".join(entry_ids)}），待锁定测试')
        return frozen_info


# ---------------------------------------------------------------------------
# 8. test (Locked test set — report only, never feeds back into search)
# ---------------------------------------------------------------------------

def run_test(root: Path, entry_id: str, rationale: str = '冻结最终路线后统一评估锁定测试集') -> dict:
    root = safe_path(root)
    with locked(root):
        state = load_state(root)
        cfg = read_json(root / 'config.json')
        require(cfg['test']['policy'] == 'locked', '当前配置未设锁定测试集（test.policy=none）')
        frozen = state.get('frozen')
        require(frozen is not None, '必须先通过 pretest-check 并 freeze 最终路线后，才允许运行锁定测试集')
        require(entry_id in frozen['entries'], f'条目 {entry_id} 不在已冻结清单中: {frozen["entries"]}')
        already = [t for t in state.get('tests', [])
                   if t.get('entry') == entry_id and t.get('route_revision') == frozen['route_revision'] and not t.get('error')]
        require(not already, f'条目 {entry_id} 在当前冻结路线已完成锁定测试，不重复消耗查看次数')

        run_ids = frozen['run_ids_by_entry'][entry_id]
        state['test_looks'] = int(state.get('test_looks', 0)) + 1
        look_num = state['test_looks']
        test_id = f't-{uuid.uuid4().hex[:8]}'
        test_dir = root / 'tests' / test_id
        test_dir.mkdir(parents=True)
        save_state(root, state, f'locked_test_started:{entry_id}')

    audit_data = read_json(Path(state['audit']['path']))
    expected_test_ids = set(audit_data['splits']['test']['group_ids'])
    py = str(safe_path(cfg['environment']['python']))
    pm_name = cfg['primary_metric']['name']
    higher = cfg['primary_metric']['direction'] == 'higher'

    per_run = []
    error_msg = None
    for rid in run_ids:
        rdir = root / 'runs' / rid
        rrec = read_json(rdir / 'record.json')
        out_dir = test_dir / rid
        out_dir.mkdir(parents=True)
        argv = _expand_argv(cfg['test']['command'], {
            '{python}': py,
            '{run_dir}': str(rdir),
            '{output}': str(out_dir),
            '{entry}': entry_id,
            '{seed}': str(rrec['seed']),
        })
        env = _build_env(cfg, {
            'ME_PHASE': 'test',
            'ME_RUN_ID': rid,
            'ME_RUN_DIR': str(rdir),
            'ME_OUTPUT_DIR': str(out_dir),
            'ME_DEVICE': cfg['environment']['device'],
            'ME_SPLIT_HASH': state['audit']['split_hash'],
        })
        proc = OwnedProcess(argv, str(safe_path(cfg['code_dir'])), env, str(out_dir / 'test.log'))
        try:
            code = proc.wait(timeout=float(cfg['test'].get('timeout_seconds', 600)))
        except subprocess.TimeoutExpired:
            proc.terminate()
            error_msg = f'测试脚本超时（run={rid}）'
            break
        finally:
            proc.close()

        if code != 0:
            error_msg = f'测试脚本非零退出（run={rid}, exit_code={code}）'
            break
        res_path = out_dir / 'result.json'
        if not res_path.is_file():
            error_msg = f'测试脚本未生成 result.json（run={rid}）'
            break
        try:
            res = read_json(res_path)
            raw_metrics = res.get('metrics', {})
            pval = number(raw_metrics.get(pm_name), f'test metrics.{pm_name}')
            cases_p = out_dir / 'cases.jsonl'
            if cases_p.is_file():
                ci_stat = (cfg.get('ci') or {}).get('statistic', 'mean_per_case')
                # Verify case_id coverage matches audited test split whenever cases.jsonl is provided
                seen_ids = set()
                for line in cases_p.read_text(encoding='utf-8').splitlines():
                    if line.strip():
                        seen_ids.add(json.loads(line)['case_id'])
                require(seen_ids == expected_test_ids, '测试 cases.jsonl 的 case_id 与划分审计 test 分组不一致')
            per_run.append({
                'run_id': rid,
                'seed': rrec['seed'],
                'primary_value': pval,
                'metrics': {k: float(v) for k, v in raw_metrics.items() if isinstance(v, (int, float)) and not isinstance(v, bool)},
                'cases_file': str(cases_p) if cases_p.is_file() else None,
            })
        except Exception as exc:
            error_msg = f'测试结果校验失败（run={rid}）: {exc}'
            break

    summary = None
    if error_msg is None and per_run:
        vals = [r['primary_value'] for r in per_run]
        summary = {
            'n_seeds': len(vals),
            'values': vals,
            'mean': stats.aggregate(vals, 'mean', higher),
            'median': stats.aggregate(vals, 'median', higher),
            'sd': stats.seed_sd(vals),
            'per_run': per_run,
        }

    test_rec = {
        'test_id': test_id,
        'entry': entry_id,
        'route_revision': state['frozen']['route_revision'],
        'look_number': look_num,
        'rationale': rationale,
        'time': timestamp(),
        'summary': summary,
        'error': error_msg,
    }
    write_json(test_dir / 'summary.json', test_rec)
    with locked(root):
        state = load_state(root)
        state['tests'].append(test_rec)
        save_state(root, state, f'locked_test_{"failed" if error_msg else "completed"}:{entry_id}')
        proj_root = find_project_root(root, state.get('project_root'))
        note = (f'锁定测试 `{entry_id}`：{pm_name}={summary["mean"]:.4g} ± {summary["sd"]:.4g}（仅报告）'
                if summary else f'锁定测试 `{entry_id}` 失败：{error_msg}')
        sync_project_index(root, proj_root, state, cfg, note)
    return test_rec


# ---------------------------------------------------------------------------
# 9. export & finalize
# ---------------------------------------------------------------------------

def _optional_paired_ci(cfg: dict, runs_a: list[Path], runs_b: list[Path]) -> dict | None:
    ci_cfg = cfg.get('ci')
    if not ci_cfg:
        return None
    if not runs_a or not runs_b or any(not p.is_file() for p in runs_a + runs_b):
        return None
    try:
        st = ci_cfg['statistic']
        a_cases = [stats.read_cases(p, st) for p in runs_a]
        b_cases = [stats.read_cases(p, st) for p in runs_b]
        return stats.paired_bootstrap(
            st, a_cases, b_cases,
            higher=cfg['primary_metric']['direction'] == 'higher',
            resamples=int(ci_cfg.get('resamples', 1000)),
            level=float(ci_cfg.get('level', 0.95)),
            seed=int(ci_cfg.get('seed', 42)),
        )
    except Exception as exc:
        return {'note': f'未计算配对 CI: {exc}'}


def export_report(root: Path) -> dict:
    root = safe_path(root)
    state = load_state(root)
    cfg = read_json(root / 'config.json')
    routes = _load_routes(root)
    all_runs = [read_json(p) for p in sorted((root / 'runs').glob('*/record.json'))]
    pm = cfg['primary_metric']['name']
    ref_id = cfg['reference']
    valid = state.get('valid_entries', {})

    val_comparisons = {}
    if ref_id in valid:
        ref_cases = [root / 'runs' / rid / 'cases.jsonl' for rid in valid[ref_id]['run_ids']]
        for eid, info in valid.items():
            if eid == ref_id:
                continue
            cand_cases = [root / 'runs' / rid / 'cases.jsonl' for rid in info['run_ids']]
            ci = _optional_paired_ci(cfg, cand_cases, ref_cases)
            if ci:
                val_comparisons[eid] = ci

    report_data = {
        'study_id': cfg['study_id'],
        'task': cfg['task'],
        'status': state['status'],
        'route_revision': state['route_revision'],
        'primary_metric': cfg['primary_metric'],
        'audit': state.get('audit'),
        'budgets': {
            'training_spent_seconds': state['training_spent_seconds'],
            'max_training_seconds': cfg['budgets']['max_training_seconds'],
            'route_revision': state['route_revision'],
            'max_routes': cfg['budgets']['max_routes'],
            'deadline_utc': cfg['budgets'].get('deadline_utc'),
        },
        'routes': routes,
        'valid_entries': valid,
        'validation_comparisons': val_comparisons,
        'pretest_check': state.get('pretest_check'),
        'frozen': state.get('frozen'),
        'test_looks': state.get('test_looks', 0),
        'tests': state.get('tests', []),
        'runs': all_runs,
    }
    write_json(root / 'report.json', report_data)

    md = [
        f'# 实验报告：{cfg["study_id"]}',
        '',
        f'- **任务**：{cfg["task"]} ｜ **主指标**：`{pm}`（{cfg["primary_metric"]["direction"]}）',
        f'- **当前状态**：`{state["status"]}` ｜ **当前路线**：`v{state["route_revision"]} / {cfg["budgets"]["max_routes"]}`',
        f'- **累计训练耗时**：`{state["training_spent_seconds"]:.1f}s / {cfg["budgets"]["max_training_seconds"]}s`',
        f'- **划分防泄漏审计**：`{"PASS" if (state.get("audit") or {}).get("passed") else "未运行"}`（split_hash: `{(state.get("audit") or {}).get("split_hash", "—")[:12]}`）',
        '',
        '## 1. 路线演进摘要',
        '',
        '| 路线 | 时间 (UTC) | 修订依据 / 变更说明 | 复用条目 | 包含条目 |',
        '|---|---|---|---|---|',
    ]
    for rt in routes:
        md.append(
            f'| v{rt["route_revision"]} | {rt["time"][:19]} | {rt["summary"]} | '
            f'{", ".join(rt.get("reused_entries") or []) or "—"} | {", ".join(rt.get("entries") or [])} |'
        )

    md += [
        '',
        f'## 2. 当前路线验证集结果（参照基线：`{ref_id}`）',
        '',
        f'| 条目 | 角色 | Seed 数 | {pm}（均值 ± SD） | 来源路线 | 相对基线配对 CI |',
        '|---|---|---:|---|---|---|',
    ]
    for entry in cfg['entries']:
        eid = entry['id']
        info = valid.get(eid)
        if info:
            sd_str = f'{info["sd"]:.4g}' if info['n_seeds'] >= 2 else '—'
            ci = val_comparisons.get(eid)
            ci_str = (f'Δ={ci["effect"]:.4g} [{ci["ci_low"]:.4g}, {ci["ci_high"]:.4g}]'
                      if ci and 'effect' in ci else (ci.get('note', '—') if ci else '—'))
            md.append(f'| `{eid}` | {entry["role"]} | {info["n_seeds"]} | {info["mean"]:.4g} ± {sd_str} | v{info["route_revision"]} | {ci_str} |')
        else:
            md.append(f'| `{eid}` | {entry["role"]} | 0 | 未运行 | — | — |')

    md += [
        '',
        '## 3. 冻结方案与锁定测试集结果',
        '',
        f'- **冻结方案**：`{", ".join((state.get("frozen") or {}).get("entries", [])) or "尚未冻结"}`',
        f'- **测试集累计查看次数**：`{state.get("test_looks", 0)}`',
        '',
    ]
    if state.get('tests'):
        md += [f'| 测试 ID | 条目 | 路线 | 查看次序 | 测试集 {pm}（均值 ± SD） | 状态 |', '|---|---|---|---|---|---|']
        for t in state['tests']:
            s = t.get('summary')
            val_s = f'{s["mean"]:.4g} ± {s["sd"]:.4g}' if s else '—'
            st_s = '完成（仅报告）' if s else f'失败: {t.get("error")}'
            md.append(f'| `{t["test_id"]}` | `{t["entry"]}` | v{t["route_revision"]} | #{t["look_number"]} | {val_s} | {st_s} |')
    else:
        md.append('尚无锁定测试记录（探索阶段严禁触碰测试集）。')

    md += [
        '',
        '## 4. 全部运行明细（含筛选与失败尝试）',
        '',
        f'| Run ID | 条目 | 阶段 | 路线 | Seed | 状态 | 耗时 (s) | {pm} | 备注/错误 |',
        '|---|---|---|---|---:|---|---:|---|---|',
    ]
    for r in all_runs:
        pv = f'{r["primary_value"]:.4g}' if r.get('primary_value') is not None else '—'
        note = r.get('error') or r.get('notes') or ''
        md.append(
            f'| `{r["run_id"]}` | `{r["entry"]}` | {r["phase"]} | v{r["route_revision"]} | '
            f'{r["seed"]} | {r["status"]} | {r.get("elapsed_seconds", 0):.1f} | {pv} | {note} |'
        )

    atomic_text(root / 'report.md', '\n'.join(md) + '\n')
    return {
        'report_json': str(root / 'report.json'),
        'report_md': str(root / 'report.md'),
        'status': state['status'],
    }


def finalize_study(root: Path, plan_file: Path | None = None, mark_rework: bool = True) -> dict:
    root = safe_path(root)
    with locked(root):
        state = load_state(root)
        cfg = read_json(root / 'config.json')
        require(state.get('frozen') is not None, '请先执行 freeze 冻结最终路线后再定稿收口')
        proj_root = find_project_root(root, state.get('project_root'))
        plan_res = None
        if plan_file is not None:
            plan_res = archive_and_update_plan(root, proj_root, plan_file, state['route_revision'])
        state['status'] = 'finalized'
        state['finalized_at'] = timestamp()
        save_state(root, state, 'study_finalized')
        sync_res = sync_project_index(
            root, proj_root, state, cfg,
            f'实验定稿收口（最终路线 v{state["route_revision"]}，条目：{", ".join(state["frozen"]["entries"])}）',
            mark_rework=mark_rework,
        )
    rep = export_report(root)
    return {'status': 'finalized', 'plan_sync': plan_res, 'project_sync': sync_res, 'report': rep}
