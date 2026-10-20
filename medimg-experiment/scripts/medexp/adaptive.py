"""Bounded, explicitly delegated adaptive experiments over the v2 owned worker.

The controller is an operational gate, not an OS security sandbox. The proposer
and reviewer are separate real CLI sessions; neither executes proposals.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

from .common import (GateError, require, number, safe_path, inside, read_json,
                     write_json, locked, load_state, save_state, timestamp,adaptive_state_locked)
from . import engine, project

_INTERNAL = ContextVar('adaptive_controller_call', default=False)
TERMINAL = ('stopped', 'completed', 'awaiting_human', 'paused')


def _state_serialized(function):
    from functools import wraps
    @wraps(function)
    def serialized(root,*args,**kwargs):
        if not (root/'adaptive'/'state.json').is_file():return function(root,*args,**kwargs)
        with adaptive_state_locked(root):return function(root,*args,**kwargs)
    return serialized


@contextmanager
def internal():
    token = _INTERNAL.set(True)
    try:
        yield
    finally:
        _INTERNAL.reset(token)


def guard(root, action):
    if (root/'adaptive'/'state.json').exists():
        require(_INTERNAL.get(), '活动自适应授权禁止手动绕过；使用 adaptive-* 入口: '+action)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode('utf-8')).hexdigest()


def delegation(root):
    return read_json(root/'adaptive'/'delegation.json')


def utc(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(dt.tzinfo is not None, '截止时间必须含时区')
    return dt.astimezone(timezone.utc)


def deadline_timeout(root,requested):
    if not (root/'adaptive'/'state.json').is_file():return requested
    a=read_json(root/'adaptive'/'state.json')
    remaining=(utc(a['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()
    require(remaining>0,'整体截止时间已到，禁止新的子进程步骤')
    return min(requested,remaining)


def validate_delegation(c, d):
    require(d.get('schema_version') == 1 and isinstance(d.get('authorization'), str)
            and d['authorization'].strip(), '缺少 AdaptiveDelegation@1 及真实首次授权记录')
    require(c['mode'] == 'matrix', '自适应首版使用显式 baseline/proposed/ablation/comparison 矩阵')
    require(utc(d['deadline_utc']) > datetime.now(timezone.utc), '整体截止时间已过')
    b = d['budgets']
    for key in ('training_seconds', 'formal_reserve_seconds', 'step_timeout_seconds', 'poll_seconds'):
        number(b.get(key), key, positive=True)
    for key in ('max_method_revisions', 'max_fault_retries'):
        require(isinstance(b.get(key), int) and not isinstance(b[key], bool) and b[key] >= 0,
                key+'必须为非负整数')
    require(b['training_seconds'] <= c['budget']['total_seconds'], '委托训练上限不能超过确认契约')
    require(b['formal_reserve_seconds'] <= b['training_seconds'], '正式预留超过总预算')
    require(b['step_timeout_seconds'] <= 3600 and 0.1 <= b['poll_seconds'] <= 60,
            '步骤超时或调度轮询不在有界范围内')
    rules = d['rules']
    for key in ('baseline_floor', 'target', 'min_effect', 'ci_lower_bound', 'screening_floor'):
        number(rules.get(key), key)
    require(rules['min_effect'] >= 0, '效应下限不得为负')
    entries = {e['id']:e for e in c['matrix']['entries']}
    require(len([e for e in entries.values() if e['role'] == 'proposed']) == 1,
            '必须有唯一 proposed 主方法')
    require(isinstance(rules.get('required_contributions'), list), '必须明确贡献目标列表，可为空')
    for rule in rules['required_contributions']:
        require(rule.get('id') and rule.get('ablation') in entries and
                entries[rule['ablation']]['role'] == 'ablation', '贡献目标必须指向消融条目')
        for key in ('min_effect', 'ci_lower_bound'):number(rule.get(key), key)
        for key in ('claim','falsification','boundary'):
            require(isinstance(rule.get(key),str) and rule[key].strip(),'贡献目标必须明确不可删改的科学语义: '+key)
    require(len({r['id'] for r in rules['required_contributions']}) == len(rules['required_contributions']),
            '贡献目标标识重复')
    require(isinstance(rules.get('comparisons'), list), '必须明确正式比较列表')
    for rule in rules['comparisons']:
        require(rule.get('entry') in entries and entries[rule['entry']]['role'] == 'comparison', '比较条目无效')
        for key in ('min_effect', 'ci_lower_bound'):number(rule.get(key), key)
    deps = d.get('entry_dependencies')
    require(isinstance(deps, dict) and set(deps) == set(entries), '每个矩阵条目必须确认完整依赖文件清单')
    for names in deps.values():
        require(isinstance(names, list) and names, '条目依赖不可为空')
        for name in names:
            require(isinstance(name, str) and '..' not in Path(name).parts and
                    not Path(name).is_absolute() and ':' not in name, '依赖路径必须为受管相对路径')
    from .agent_backends import validate_backend
    validate_backend(d)
    if d.get('project_root') is not None:
        require(Path(d['project_root']).is_absolute() and safe_path(d['project_root']).is_dir(), 'project_root必须为现有绝对目录')
    policy=d.get('recovery')
    if policy:
        from .contract import frozen_command
        frozen_command(policy.get('validator_command'),c['scope']['frozen_paths'],('{checkpoint}','{output}'),'恢复状态核验')
        require(policy['validator_command'].count('{checkpoint}')==1 and policy['validator_command'].count('{output}')==1,
                '恢复核验命令必须包含checkpoint和output各一次')
        require(isinstance(policy.get('checkpoint'),str) and not Path(policy['checkpoint']).is_absolute() and '..' not in Path(policy['checkpoint']).parts,
                'checkpoint必须为run内相对路径')
        number(policy.get('timeout_seconds'),'恢复核验超时',positive=True)
    for name in d.get('evaluator_implementation_paths',[]):
        require(name in c['scope']['frozen_paths'] and name!=c['split_audit']['command'][1], '评价纠错范围不可包含划分审计或未冻结文件')
    if d.get('downstream_stages') is not None:
        require(isinstance(d['downstream_stages'],list) and all(isinstance(x,str) and x.strip() for x in d['downstream_stages']),
                'downstream_stages必须为首次确认的下游阶段名列表')
    return d


def init(root, contract_path, delegation_path, statement):
    require(isinstance(statement, str) and statement.strip(), '必须记录首次用户明确授权')
    from .contract import validate
    c = validate(read_json(contract_path));d = validate_delegation(c, read_json(delegation_path))
    engine.init(root, contract_path)
    engine.approve(root, statement)
    a = {'schema_version':1, 'status':'ready', 'created_at':timestamp(), 'deadline_utc':d['deadline_utc'],
         'method_revisions':0, 'fault_retries':0, 'training_spent_seconds':0, 'charged_runs':{},
         'current_proposal':None, 'current_candidate':None, 'current_entry':None,
         'evidence_level':None, 'final_selection':None, 'scheduler':None, 'last_event':None,
         'method_plan':None, 'diagnosis':None,
         'bound_project_root':d.get('project_root') or next((str(p) for p in root.parents if (p/'PROJECT.md').exists()),None),
         'affected_stages':[],
         'scientific_identity':digest({k:c[k] for k in ('task','data','primary_metric','guard_metrics','verification','matrix')}),
         'delegation_hash':digest(d), 'approval':{'statement':statement, 'identity_assurance':'caller-recorded'},
         'contract_hash':digest(c),
         'invalidations':[], 'reuse':[], 'tested_candidates':[], 'proposal_history':[]}
    write_json(root/'adaptive'/'delegation.json',d)
    with adaptive_state_locked(root):write_json(root/'adaptive'/'state.json',a)
    persist(root,a,'delegation_initialized')
    return a


@_state_serialized
def persist(root, a, event):
    previous=read_json(root/'adaptive'/'state.json')
    require(previous['status']!='paused' or a['status']=='paused' or event=='user_resumed',
            '用户暂停优先于尚未提交的后台操作，须明确恢复')
    if event=='early_convergence_final_frozen':deadline_timeout(root,1)
    if a.get('pending_projection_event'):sync_projection(root,a)
    a['last_event'] = uuid.uuid4().hex
    a['updated_at'] = timestamp()
    a['pending_projection_event'] = a['last_event']
    write_json(root/'adaptive'/'state.json', a)
    with (root/'adaptive'/'events.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps({'event_id':a['last_event'],'event':event,'time':timestamp(),
                            'status':a['status'],'method_revisions':a['method_revisions']},ensure_ascii=False)+'\n')
    # Durable event first. A failed projection is retried before the next action.
    sync_projection(root,a)


@_state_serialized
def sync_projection(root, a):
    if not a.get('pending_projection_event'):return
    latest=read_json(root/'adaptive'/'state.json')
    require(latest['status']!='paused' or a['status']=='paused','用户暂停阻止旧投影提交覆盖状态')
    if a['pending_projection_event']!=latest.get('pending_projection_event'):
        require(latest.get('pending_projection_event') is None,'投影事件已改变，禁止旧状态覆盖')
        a.update(latest);return
    from .projection import sync_project
    s = load_state(root);d = delegation(root)
    c=engine.current_contract(root,s)
    snapshot = {'project_root':a.get('bound_project_root'), 'event_id':a['pending_projection_event'],
        'method_revision':s['revision'], 'status':a['status'], 'stage':a.get('evidence_level') or s['stage'],
        'current_method':a.get('current_proposal'), 'method_plan':a['method_plan'],
        'diagnosis':a.get('diagnosis'), 'next_steps':next_action(root,a,s,c),
        'latest_attempt':{'candidate':a.get('current_candidate'),'active_run':s.get('active_run'),'status':s['status']},
        'valid_results':[{**v,'entry':k} for k,v in s.get('matrix_done',{}).items()],
        'final_selection':a.get('final_selection'),
        'budgets':{'spent_seconds':a['training_spent_seconds'], 'limits':d['budgets'],
                   'method_revisions':a['method_revisions'],'fault_retries':a['fault_retries'],'deadline_utc':a['deadline_utc']},
        'test_state':{'looks':s.get('test_looks',0),'tests':s.get('tests',[]),'frozen':bool(a.get('final_selection'))},
        'affected_stages':a.get('affected_stages',[]), 'confirmed_contract':c,'confirmed_rules':d['rules'],
        'current_commands':read_json(root/'adaptive'/'proposals'/(a['current_proposal']+'.json'))['proposal']['entries'] if a.get('current_proposal') else []}
    pending=root/'adaptive'/'projection-snapshots'/(a['pending_projection_event']+'.json')
    if pending.exists():snapshot=read_json(pending)
    else:write_json(pending,snapshot)
    # Standalone studies have no paper project to project into.
    discover = a.get('bound_project_root')
    if discover:
        snapshot['project_root']=discover;sync_project(root,snapshot)
    else:
        write_json(root/'evidence'/'projections'/(a['pending_projection_event']+'.json'),
                   {'event_id':a['pending_projection_event'],'status':'standalone-study','snapshot':snapshot})
    a['pending_projection_event']=None
    a['affected_stages']=[]
    write_json(root/'adaptive'/'state.json',a)


def next_action(root,a,s,c):
    if a['status'] in TERMINAL:return ['等待/停止 '+a['status']+'：'+str(a.get('stop_reason') or a.get('pause_statement') or '须明确用户方向')]
    if s.get('active_run'):return ['等待归属worker完成 run='+s['active_run']+'；核验原始指标和耗时']
    if s.get('active_test'):return ['等待冻结test完成 '+s['active_test']['id']+'；只报告，不回流方法选择']
    if a.get('final_selection'):
        pending=[x['candidate_id'] for x in a['final_selection']['entries'].values() if x['candidate_id'] not in a['tested_candidates']]
        return ['finaltest '+(','.join(pending) if pending and c['test']['policy']=='locked' else '汇总冻结证据并完成交付')]
    if s['status']=='awaiting_report':return ['诊断并保全incident '+str((s.get('pending_incident') or {}).get('incident_id'))+'，在重试上限内恢复或修复']
    if a.get('pending_correction'):return ['review 原评价实现纠错；独立新上下文审查，通过后失效相关证据并重训']
    if a.get('bootstrap_pending'):return ['bootstrap '+('proposal 修复初始实现' if a.get('repair_pending') else 'review 全部初始源码和冻结评价实现')+'；首次audit前须独立审查通过']
    if not s.get('audit'):
        needed=set(c['scope']['frozen_paths'])|{name for names in delegation(root)['entry_dependencies'].values() for name in names}
        if bootstrap_allowed(root) and any(not inside(root/'worktree',name).is_file() for name in needed):
            return ['bootstrap proposal 创建缺失的受管训练及固定评价实现；独立新上下文review通过后才audit']
        return ['audit 冻结划分和分组泄漏审计；通过后才建立候选']
    if not a.get('current_proposal') or a.get('repair_pending') or a.get('revision_pending'):
        return ['proposal 新上下文生成'+('故障修复' if a.get('repair_pending') else '方法修订' if a.get('revision_pending') else '初始方法')+'，保持固定科学目标、正式预留与总预算']
    ordered=[c['matrix']['reference']]+[e['id'] for e in c['matrix']['entries'] if e['id']!=c['matrix']['reference']]
    if len(s['matrix_done'])==len(ordered):return ['formal_gate 检查基线可信性、目标、配对比较和全部贡献命题；全部达标即冻结']
    entry=next(e for e in ordered if e not in s['matrix_done'])
    level='formal' if entry==c['matrix']['reference'] else 'screening'
    if not a.get('current_candidate') or a.get('current_entry')!=entry:return ['candidate entry='+entry+' phase='+level+'；快照后新上下文review']
    cand=read_json(root/'candidates'/(a['current_candidate']+'.json'))
    if not cand.get('review'):return ['review candidate='+cand['id']+' commit='+cand['commit']+'；通过后才训练']
    records=[read_json(root/'runs'/r/'record.json') for r in cand['runs']]
    if cand.get('evidence_level')=='screening' and any(r['status']=='completed' for r in records):
        return ['screening_gate entry='+entry+'；晋级后新建formal候选并运行全部确认seed，或保留筛选淘汰证据']
    used={r['seed'] for r in records};seed=next((x for x in c['verification']['seeds'] if x not in used),None)
    return ['run candidate='+cand['id']+' entry='+entry+' phase='+cand.get('evidence_level','formal')+' seed='+str(seed)+'；仅由controller-owned worker执行']


def reconcile(root,a):
    # Each run ID has one monotonically increasing charge; failed/partial runs count.
    charges = a.setdefault('charged_runs',{})
    for p in (root/'runs').glob('*/record.json'):
        r=read_json(p);elapsed=number(r.get('elapsed_seconds',0),'run elapsed')
        require(elapsed >= 0, '运行耗时不可为负')
        charges[r['run_id']]=max(charges.get(r['run_id'],0),elapsed)
    a['training_spent_seconds']=max(a.get('training_spent_seconds',0),sum(charges.values()))
    return a


def status(root):
    engine.status(root)
    with locked(root),adaptive_state_locked(root):
        a=reconcile(root,read_json(root/'adaptive'/'state.json'))
        write_json(root/'adaptive'/'state.json',a)
        return a


def admit_training(root,a,level,requested):
    b=delegation(root)['budgets']
    remaining=b['training_seconds']-a['training_spent_seconds']
    seconds_left=(utc(a['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()
    cap=min(remaining,requested,seconds_left)
    if level=='screening':cap=min(cap,remaining-b['formal_reserve_seconds'])
    require(cap>0, '正式资源预留、训练总账或整体截止时间阻止新训练')
    return cap


@_state_serialized
def effective_run_contract(root,c,cand):
    if not (root/'adaptive'/'state.json').exists():return c
    a=reconcile(root,read_json(root/'adaptive'/'state.json'))
    require(digest(c)==a['contract_hash'],'确认的契约内容已改变，禁止训练')
    require(a['status'] not in TERMINAL and not a.get('final_selection'), '自适应当前禁止训练')
    require(not a.get('pending_method_classification'),'修复的独立语义分类尚未登记，禁止训练')
    level=cand.get('evidence_level','formal')
    limit=admit_training(root,a,level,c['budget']['run_timeout_seconds'])
    out=copy.deepcopy(c)
    out['budget']['run_timeout_seconds']=limit
    # Worker uses this run-local copy for its hard time limit.
    out['budget']['total_seconds']=load_state(root)['spent_seconds']+limit
    write_json(root/'adaptive'/'state.json',a)
    return out


def pause(root,statement):
    require(statement.strip(), '必须记录用户暂停指令')
    with locked(root),adaptive_state_locked(root):
        a=read_json(root/'adaptive'/'state.json');a.update(status='paused',pause_statement=statement,
                paused_run=load_state(root).get('active_run'))
        persist(root,a,'user_paused')
    return a


def resume(root,statement):
    require(statement.strip(), '必须记录用户明确恢复指令')
    with locked(root),adaptive_state_locked(root):
        a=read_json(root/'adaptive'/'state.json')
        require(a['status']=='paused', '只有主动暂停可恢复；人工关口不能用通用恢复绕过')
        require(utc(a['deadline_utc'])>datetime.now(timezone.utc),'原整体截止时间已过，须新授权')
        a.update(status='ready',resume_statement=statement);persist(root,a,'user_resumed')
    return a


def condition_fingerprint(root,entry,command):
    d=delegation(root);s=load_state(root);c=engine.current_contract(root,s)
    files={name:hashlib.sha256(inside(root/'worktree',name).read_bytes()).hexdigest()
           for name in set(d['entry_dependencies'][entry]+c['scope']['frozen_paths'])}
    return digest({'files':files,'command':command,'environment':c['environment'],
                   'data':c['data'],'verification':c['verification'],'metric':c['primary_metric'],
                   'guard_metrics':c['guard_metrics'],'audit':(s.get('audit') or {}).get('frozen_hashes')})


def bootstrap_allowed(root):
    s=load_state(root);a=read_json(root/'adaptive'/'state.json')
    return not (a.get('bootstrap_closed') or s.get('audit') or s.get('frozen_commit') or
                any((root/'runs').glob('*/record.json')))


def canonical_command(c,command):
    require(isinstance(command,list) and command and all(isinstance(x,str) for x in command),'命令必须为argv字符串数组')
    if command[0]=='{python}':return list(command)
    require(Path(command[0]).is_absolute(),'训练解释器必须为契约占位符或已批准绝对路径')
    approved=os.path.normcase(str(safe_path(c['environment']['python'])))
    supplied=os.path.normcase(str(safe_path(command[0])))
    require(supplied==approved,'拒绝非契约批准的训练解释器')
    rest=list(command[1:])
    if rest[:2]==['-X','utf8']:rest=rest[2:]
    return ['{python}',*rest]


def validate_proposal(root,p,correction=False,bootstrap=False,normalizations=None):
    p=copy.deepcopy(p)
    s=load_state(root);c=engine.current_contract(root,s)
    if bootstrap:require(bootstrap_allowed(root),'初始实现窗口已关闭；不能用bootstrap改科学冻结文件')
    require(isinstance(p,dict) and p.get('action') in ('candidate','stop','request_resource','correct_evaluator'), '提案action无效')
    require(isinstance(p.get('reason'),str) and p['reason'].strip(), '提案缺少依据')
    if p['action'] in ('stop','request_resource'):return p
    require(isinstance(p.get('method_plan'),str) and p['method_plan'].strip(),'提案必须更新方法和技术路线')
    require(isinstance(p.get('files'),list) and len(p['files'])<=40,'文件变更列表无效')
    seen=set();total=0
    for change in p['files']:
        name=change['path'];inside(root/'worktree',name)
        require(name not in seen and not (root/'worktree'/name).is_symlink(),'重复或符号链接变更被拒绝')
        seen.add(name)
        allowed=(name in c['scope']['frozen_paths'] or project.matches(name,c['scope']['editable_paths'])) if bootstrap else (name in delegation(root).get('evaluator_implementation_paths',[]) and
                 name in c['scope']['frozen_paths'] and name != c['split_audit']['command'][1]) if correction else (
            project.matches(name,c['scope']['editable_paths']) and not project.matches(name,c['scope']['frozen_paths']))
        require(allowed,'提案修改越过批准代码范围或固定科学文件: '+name)
        require(isinstance(change.get('content'),str),'文件内容必须为字符串')
        total+=len(change['content'].encode('utf-8'))
    require(total<=2_000_000,'提案代码内容过大')
    if correction:
        require(p.get('definition_unchanged') is True,'纠错只能恢复原确认定义')
        return p
    require(isinstance(p.get('entries'),list),'必须列出完整矩阵训练命令')
    ids=[x.get('entry') for x in p['entries']]
    require(len(ids)==len(set(ids)) and set(ids)=={e['id'] for e in c['matrix']['entries']},'不得删除贡献目标、基线或比较条目')
    for entry in p['entries']:
        for key in ('command','screening_command'):
            raw=list(entry[key]);entry[key]=canonical_command(c,entry[key])
            if raw!=entry[key] and normalizations is not None:
                normalizations.append({'entry':entry['entry'],'field':key,'raw_argv':raw,
                    'canonical_argv':list(entry[key]),'approved_python':c['environment']['python'],
                    'rule':'exact approved resolved absolute interpreter; optional sole -X utf8 prefix; legacy validator unchanged'})
            engine.validate_command(root,c,entry[key],available_files=seen if bootstrap else ())
    # Additional keys cannot loosen fixed definitions or budgets; they are never applied.
    return p


def formal_gate(root,s):
    c=engine.current_contract(root,s);r=delegation(root)['rules'];done=s['matrix_done'];problems=[];comparisons=[]
    entries=c['matrix']['entries'];ref=c['matrix']['reference'];main=next(e['id'] for e in entries if e['role']=='proposed')
    missing=sorted({e['id'] for e in entries}-set(done))
    if missing:problems.append('missing:'+','.join(missing))
    sign=1 if engine.higher(c) else -1
    if ref in done and sign*(done[ref]['value']-r['baseline_floor'])<0:problems.append('baseline_floor')
    if main in done and sign*(done[main]['value']-r['target'])<0:problems.append('target')
    if problems:return {'passed':False,'problems':problems,'comparisons':comparisons}
    checks=[{'entry':ref,'min_effect':r['min_effect'],'ci_lower_bound':r['ci_lower_bound'],'id':'baseline_advantage'}]
    checks += [dict(entry=x['ablation'],**{k:v for k,v in x.items() if k!='ablation'}) for x in r['required_contributions']]
    checks += [dict(id='comparison:'+x['entry'],**x) for x in r['comparisons']]
    for check in checks:
        other=done[check['entry']]
        ci=engine.paired(c,root,done[main]['run_ids'],other['run_ids'])
        guards=engine.guard_violations(c,done[main].get('guards',{}),other.get('guards',{}))
        passed=ci['effect']>=check['min_effect'] and ci['ci_low']>=check['ci_lower_bound'] and not guards
        comparisons.append({'id':check['id'],'ci':ci,'guards':guards,'passed':passed})
        if not passed:problems.append(check['id'])
    return {'passed':not problems,'problems':problems,'comparisons':comparisons}


def _write_files(root,changes):
    for change in changes:
        path=inside(root/'worktree',change['path']);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(change['content'],encoding='utf-8',newline='\n')


def affected_stages(root,a):
    d=delegation(root)
    if d.get('downstream_stages') is not None:return [x for x in d['downstream_stages'] if x not in ('0','入口检查','项目入口检查')]
    bound=a.get('bound_project_root')
    if not bound:return []
    text=(safe_path(bound)/'PROJECT.md').read_text(encoding='utf-8')
    columns=None;number_column=None;stages=set(a.get('affected_stages',[]))
    for line in text.splitlines():
        if not line.strip().startswith('|'):continue
        cells=[x.strip() for x in line.strip().split('|')[1:-1]]
        if '阶段' in cells and '状态' in cells:
            columns=(cells.index('阶段'),cells.index('状态'));number_column=cells.index('#') if '#' in cells else None;continue
        if columns and len(cells)>max(columns) and cells[columns[1]] in ('已确认','待确认','进行中','完成','需返工'):
            if number_column is not None and cells[number_column]=='0':continue
            if cells[columns[0]] not in ('入口检查','项目入口检查'):stages.add(cells[columns[0]])
    return sorted(stages)


def install_proposal(root,a,p,agent_record,bootstrap=False):
    require(read_json(root/'adaptive'/'state.json')['status'] not in TERMINAL,'暂停/停止/人工关口阻止应用提案')
    mappings=[];p=validate_proposal(root,p,bootstrap=bootstrap,normalizations=mappings)
    agent_record=copy.deepcopy(agent_record)
    from .review_adapter import readable_method_plan
    method_markdown=readable_method_plan(p['method_plan'])
    if method_markdown!=p['method_plan']:
        agent_record['method_plan_normalization']={'raw_sha256':hashlib.sha256(p['method_plan'].encode('utf-8')).hexdigest(),
              'markdown_sha256':hashlib.sha256(method_markdown.encode('utf-8')).hexdigest(),
              'rule':'render technical sections as Markdown; raw model result retained unchanged'}
        p['method_plan']=method_markdown
    if mappings:
        agent_record['argv_normalizations']=mappings
        if agent_record.get('invocation_id'):
            invocation=inside(root/'adaptive'/'agents',agent_record['invocation_id']+'/invocation.json')
            if invocation.is_file():
                recorded=read_json(invocation);recorded['argv_normalizations']=mappings;write_json(invocation,recorded)
    d=delegation(root);s=load_state(root);c=engine.current_contract(root,s)
    require(not s.get('test_looks') and not a.get('final_selection'),'最终冻结/已见测试后禁止自动方法修订')
    if p['action'] in ('stop','request_resource'):
        a.update(status='awaiting_human' if p['action']=='request_resource' else 'stopped',stop_reason=p['reason'])
        persist(root,a,'resource_requested' if p['action']=='request_resource' else 'agent_stopped');return
    require(p['action']=='candidate','评价纠错必须走专用纠错门')
    previous=a.get('current_proposal');prior_commit=project.commit(root)
    repairing=bool(a.get('repair_pending'))
    prior_diagnosis=copy.deepcopy(a.get('diagnosis'))
    prior_proposal=read_json(root/'adaptive'/'proposals'/(previous+'.json'))['proposal'] if previous else None
    if previous:
        key='fault_retries' if a.get('repair_pending') else 'method_revisions'
        ceiling=d['budgets']['max_fault_retries' if key=='fault_retries' else 'max_method_revisions']
        require(a[key]<ceiling,'故障重试或方法修订上限已达')
        a[key]+=1
        a['affected_stages']=affected_stages(root,a)
    _write_files(root,p['files'])
    if previous:
        s['revision']+=1
        write_json(root/'plans'/f'contract-{s["revision"]:03d}.json',c)
        # Preserve budget and test history. Never call schema-v2 resume (which resets).
        s.update(status='ready',pending_incident=None)
    sha=project.snapshot(root,c,s.get('frozen_commit'),'matrix')
    if previous and repairing and not bootstrap and (sha!=prior_commit or p['entries']!=prior_proposal['entries']
                                                    or p['method_plan']!=prior_proposal['method_plan']):
        pending=a.get('pending_method_classification') or {
            'prior_commit':prior_commit,'prior_proposal':previous,'prior_method_plan':prior_proposal['method_plan'],
            'incident':prior_diagnosis}
        pending.update(proposed_commit=sha,proposed_reason=p['reason'])
        a['pending_method_classification']=pending
    # Unchanged, explicitly declared relevant dependencies permit reuse across commits.
    keep={}
    for e in p['entries']:
        old=s['matrix_done'].get(e['entry'])
        fingerprint=condition_fingerprint(root,e['entry'],e['command'])
        if old and old.get('condition_fingerprint')==fingerprint:
            keep[e['entry']]=old
            a['reuse'].append({'entry':e['entry'],'source_candidate':old['candidate_id'],'fingerprint':fingerprint,'time':timestamp()})
    s['matrix_done']=keep;s['status']='ready'
    proposal_id='proposal-'+uuid.uuid4().hex[:12]
    write_json(root/'adaptive'/'proposals'/(proposal_id+'.json'),{'proposal':p,'agent_record':agent_record,'commit':sha,'revision':s['revision']})
    a.update(current_proposal=proposal_id, current_candidate=None,current_entry=None,evidence_level=None,
             method_plan=p['method_plan'],diagnosis=p['reason'],repair_pending=False,revision_pending=False)
    if bootstrap:a.update(bootstrap_pending=True,bootstrap_review=None)
    a['proposal_history'].append(proposal_id)
    save_state(root,s,'delegated_method_revision' if previous else 'delegated_initial_method')
    from .recovery import clone_candidate
    recovered=clone_candidate(root,a,s,c,d,p,sha)
    if recovered:
        if a.get('pending_method_classification'):
            recovered['review']=None;write_json(root/'candidates'/(recovered['id']+'.json'),recovered)
        a.update(current_candidate=recovered['id'],current_entry=recovered['entry'],evidence_level=recovered['evidence_level'])
    engine.write_plan(root,s,'预先授权自动修订：'+p['reason'])
    persist(root,a,'method_plan_updated')


def correct(root,record):
    p=read_json(record) if not isinstance(record,dict) else record
    with locked(root),adaptive_state_locked(root):
        a=read_json(root/'adaptive'/'state.json');s=load_state(root)
        if s.get('test_looks') or a.get('final_selection'):
            a.update(status='awaiting_human',stop_reason='post_test_evaluator_correction_requires_specific_confirmation')
            write_json(root/'adaptive'/'pending-correction.json',p);persist(root,a,'post_test_correction_blocked')
            raise GateError('已冻结/已见测试后评价纠错须独立审查及作者具体确认；不自动重开方法搜索')
        require(not s.get('active_run') and not s.get('active_test'),'运行期间不能纠错')
        p={**p,'action':'correct_evaluator'};validate_proposal(root,p,correction=True)
        # Save proposal first; a fresh reviewer must pass before any evaluator change.
        write_json(root/'adaptive'/'pending-correction.json',p)
        a['pending_correction']=True;persist(root,a,'evaluator_correction_requested')
    return a


def _verify_review_invocation(root,out,record,purpose):
    from .agent_backends import selected_backend, verify_replay
    from .agent_runner import REVIEW
    d=delegation(root);backend=selected_backend(d)
    require(record.get('backend','codex')==backend,'审查调用后端与选定授权不一致')
    if backend=='codex':return
    require(record.get('purpose')==purpose and record.get('fresh_context') is True
            and record.get('status')=='completed','Claude审查缺少已完成的新会话调用')
    ident=record.get('invocation_id');require(isinstance(ident,str) and ident,'Claude审查缺少实际调用记录')
    folder=inside(root/'adaptive'/'agents',ident)
    require(read_json(folder/'invocation.json')==record,'Claude审查记录与实际调用文件不一致')
    raw=verify_replay(root,d,folder,record,REVIEW)
    normalized,_=normalize_review(root,raw,record)
    require(all(out.get(key)==normalized[key] for key in REVIEW['properties']),
            'Claude审查结果与实际事件不一致')


def _apply_correction(root,a,review):
    require(read_json(root/'adaptive'/'state.json')['status'] not in TERMINAL,'暂停/停止阻止应用纠错')
    p=read_json(root/'adaptive'/'pending-correction.json');s=load_state(root);c=engine.current_contract(root,s)
    require(review['verdict']=='pass','纠错未通过新上下文审查')
    require(review.get('candidate_id')=='evaluator-correction' and review.get('commit')==project.commit(root),
            '评价纠错审查必须绑定当前提交和明确纠错身份')
    require(review.get('invocation',{}).get('thread_id') and review['invocation'].get('fresh_context') is True,
            '缺少真实新上下文审查调用身份')
    _verify_review_invocation(root,review,review['invocation'],'correction_review')
    require(isinstance(review.get('artifacts_read'),list) and review['artifacts_read'],'纠错审查未登记源文件读取')
    for name in review['artifacts_read']:require(inside(root/'worktree',name).is_file(),'纠错审查引用不存在的源文件')
    validate_proposal(root,p,correction=True)
    before=project.commit(root);affected=[]
    for path in (root/'runs').glob('*/record.json'):
        rec=read_json(path)
        if not rec.get('invalidated'):
            rec['invalidated']={'reason':p['reason'],'time':timestamp(),'selection_affected':True}
            write_json(path,rec);affected.append(rec['run_id'])
    _write_files(root,p['files'])
    project.git(root/'worktree','add','--all');project.git(root/'worktree','commit','-m','Reviewed restoration of original evaluator definition')
    after=project.commit(root)
    a['invalidations'].append({'before':before,'after':after,'run_ids':affected,'review':review,'reason':p['reason']})
    prior_audit=s.get('audit')
    if prior_audit:
        prior_audit={**prior_audit,'frozen_hashes':engine.frozen_hashes(root,c),
                     'evaluator_correction_review':review,'split_identity_unchanged':True}
    s.update(frozen_commit=after,audit=prior_audit,matrix_done={},stable=None,baseline_stable=None,baseline_value=None,
             status='ready',pending_incident=None)
    s['revision']+=1;write_json(root/'plans'/f'contract-{s["revision"]:03d}.json',c)
    a.update(pending_correction=False,current_candidate=None,current_entry=None,evidence_level=None)
    a['method_plan']=p['method_plan'];a['affected_stages']=affected_stages(root,a)
    save_state(root,s,'evaluator_corrected_all_dependent_selections_invalidated')
    persist(root,a,'evaluator_correction_applied_retraining_required')


def _stop(root,a,reason,status_value='stopped'):
    a.update(status=status_value,stop_reason=reason);persist(root,a,'adaptive_stopped');return a


def _method_classification_evidence(root,a,c,current_commit):
    """Supply bound prior source evidence without extending the agent's tools."""
    pending=a['pending_method_classification'];work=root/'worktree'
    prior=pending.get('prior_commit');proposed=pending.get('proposed_commit')
    def verified_commit(value):
        require(isinstance(value,str) and len(value) in (40,64) and all(ch in '0123456789abcdef' for ch in value),
                '故障分类提交身份必须为完整Git提交')
        require(project.git(work,'rev-parse','--verify',value+'^{commit}')==value,'故障分类提交身份无效')
        return value
    verified_commit(prior);verified_commit(proposed)
    require(proposed==current_commit and project.clean(root),'故障分类新提交与当前干净源码不一致')
    project.git(work,'merge-base','--is-ancestor',prior,proposed)
    ident=pending.get('prior_proposal');require(isinstance(ident,str) and ident,'故障分类缺少原始提案身份')
    previous=read_json(inside(root/'adaptive'/'proposals',ident+'.json'))
    previous_commit=verified_commit(previous.get('commit'))
    project.git(work,'merge-base','--is-ancestor',previous_commit,prior)
    require(isinstance(previous.get('proposal'),dict) and
            previous['proposal'].get('method_plan')==pending.get('prior_method_plan'),'故障分类原始提案与旧技术路线不一致')
    declared=set(c['code']['files'])|set(c['scope']['frozen_paths'])
    declared|={name for names in delegation(root)['entry_dependencies'].values() for name in names}
    names=project.git(work,'-c','core.quotepath=false','diff','--no-ext-diff','--no-textconv',
                      '--no-renames','--name-only','-z',prior,proposed,'--')
    changed=sorted(name for name in names.split('\0') if name)
    for name in changed:
        path=inside(work,name)
        require('.git' not in path.relative_to(work).parts and
                (name in declared or project.matches(name,c['scope']['editable_paths'])),
                '故障分类差异越出批准源码范围')
    diff=project.git(work,'-c','core.quotepath=false','diff','--no-ext-diff','--no-textconv',
                     '--no-renames','--no-color','--full-index','--unified=20',prior,proposed,'--',*changed) if changed else ''
    return {'schema_version':1,'prior_commit':prior,'proposed_commit':proposed,
            'prior_proposal_id':ident,'prior_proposal_commit':previous_commit,'prior_proposal':previous['proposal'],
            'changed_paths':changed,'source_diff':diff}


def _agent_payload(root,a,purpose):
    verify_original(root)
    s=load_state(root);c=engine.current_contract(root,s)
    # No held-out test outputs, scores, or patient files enter a search prompt.
    records=[]
    for p in (root/'runs').glob('*/record.json'):
        rec=read_json(p);records.append({k:rec.get(k) for k in ('run_id','candidate_id','entry','seed','status','value','guards','anomaly','invalidated')})
    payload={'purpose':purpose,'current_commit':project.commit(root),'original_plan':(root/'plans'/'original.md').read_text(encoding='utf-8'),
            'contract':c,'delegation':delegation(root),'method_plan':a['method_plan'],
            'method_revisions':a['method_revisions'],'fault_retries':a['fault_retries'],'validation_runs':records,
            'pending_method_classification':a.get('pending_method_classification'),
            'diagnosis':a.get('diagnosis'),'proposal':read_json(root/'adaptive'/'proposals'/(a['current_proposal']+'.json')) if a.get('current_proposal') else None,
            'candidate':read_json(root/'candidates'/(a['current_candidate']+'.json')) if a.get('current_candidate') else None}
    if payload['delegation'].get('agent_backend','codex')=='claude' and a.get('pending_method_classification'):
        payload['method_classification_evidence']=_method_classification_evidence(root,a,c,payload['current_commit'])
    return payload


def _review_candidate(root,a,cand):
    from .agent_runner import invoke
    payload=_agent_payload(root,a,'review');payload['candidate']=cand
    out,record=invoke(root,delegation(root),'review',payload)
    if record.get('invocation_id'):
        a['review_persistence_pending']={'invocation_id':record['invocation_id'],'candidate_id':cand['id'],'commit':cand['commit']}
        with locked(root),adaptive_state_locked(root):
            latest=read_json(root/'adaptive'/'state.json')
            require(latest['status'] not in TERMINAL,'暂停或停止阻止登记后台审查')
            latest['review_persistence_pending']=a['review_persistence_pending'];write_json(root/'adaptive'/'state.json',latest)
    out,record=normalize_review(root,out,record)
    _verify_review_invocation(root,out,record,'review')
    require(project.commit(root)==cand['commit'] and project.clean(root),'审查期间代码已改变')
    require(out['candidate_id']==cand['id'] and out['commit']==cand['commit'],'审查候选/提交绑定不一致')
    out.update(reviewer=record.get('backend','codex')+'-independent',agent_id=record['thread_id'],invocation=record,
               identity_assurance='real fresh '+record.get('backend','codex')+' CLI; same-family; not scientific proof')
    with internal():engine.review(root,_record_file(root,out))
    if out['verdict']=='block':_blocked_review(root,a,out)
    elif a.get('pending_method_classification'):_classify_review(root,a,cand,out)
    a['review_persistence_pending']=None
    with locked(root),adaptive_state_locked(root):
        latest=read_json(root/'adaptive'/'state.json');latest['review_persistence_pending']=None
        write_json(root/'adaptive'/'state.json',latest)
    return out


def _classify_review(root,a,cand,out):
    require(out.get('candidate_id')==cand['id'] and out.get('commit')==cand['commit']
            and project.commit(root)==cand['commit'] and project.clean(root),'语义审查提交不匹配或代码已改变')
    if a.get('pending_method_classification'):
        kind=out.get('change_kind');require(kind in ('initial','fault_repair','method_revision','uncertain'),'修复审查缺少独立语义分类')
        a['pending_method_classification']['review']=out
        if kind not in ('fault_repair','method_revision'):
            _stop(root,a,'independent_review_change_kind_uncertain','awaiting_human')
        elif kind=='method_revision':
            d=delegation(root)
            if a['method_revisions']>=d['budgets']['max_method_revisions']:
                _stop(root,a,'method_revision_limit_after_repair_classification')
            elif d['budgets']['training_seconds']-a['training_spent_seconds']<=d['budgets']['formal_reserve_seconds']:
                _stop(root,a,'method_change_cannot_consume_formal_reserve')
            else:
                a['method_revisions']+=1;a['pending_method_classification']=None
                cand['evidence_level']='classification_only';write_json(root/'candidates'/(cand['id']+'.json'),{**cand,'review':out})
                a.update(current_candidate=None,current_entry=None,evidence_level=None)
                persist(root,a,'independently_classified_method_revision_requires_screening')
        else:
            a['pending_method_classification']=None
            persist(root,a,'independent_review_confirmed_fault_repair_no_method_charge')
    return a


def _blocked_review(root,a,out):
    a.update(repair_pending=True,diagnosis={'kind':'review_block','candidate_id':out['candidate_id'],
             'findings':out['findings'],'review_invocation':out.get('invocation')})
    if a['fault_retries']>=delegation(root)['budgets']['max_fault_retries']:
        return _stop(root,a,'fault_retry_limit_after_review_block')
    persist(root,a,'fresh_review_block_preserved_bounded_repair_pending')
    return a


def _bootstrap_step(root,a,c):
    from .agent_runner import invoke
    if not a.get('current_proposal') or a.get('repair_pending'):
        if a.get('repair_pending') and a['fault_retries']>=delegation(root)['budgets']['max_fault_retries']:
            return _stop(root,a,'fault_retry_limit_after_bootstrap_review_block')
        payload=_agent_payload(root,a,'bootstrap_implementation')
        payload['bootstrap']={'allowed':True,'frozen_implementation_paths':c['scope']['frozen_paths'],
                              'constraint':'Implement only original confirmed scientific definitions; do not train or audit'}
        out,record=invoke(root,delegation(root),'proposal',payload)
        install_proposal(root,a,out,record,bootstrap=True)
        return a
    commit=project.commit(root)
    candidate={'id':'bootstrap-code-'+str(load_state(root)['revision']),'commit':commit,
               'phase':'bootstrap','revision':load_state(root)['revision'],
               'description':'Initial whole managed source implementation before first audit; no training permitted'}
    payload=_agent_payload(root,a,'bootstrap_review');payload['candidate']=candidate
    payload['bootstrap']={'allowed':True,'constraint':'Read-only review all initial training/audit/evaluator implementation against confirmed definitions; no execution'}
    out,record=invoke(root,delegation(root),'bootstrap_review',payload)
    out,record=normalize_review(root,out,record)
    _verify_review_invocation(root,out,record,'bootstrap_review')
    require(project.commit(root)==commit and project.clean(root),'bootstrap审查期间代码已改变')
    require(out.get('candidate_id')==candidate['id'] and out.get('commit')==commit,'bootstrap审查提交/身份不匹配')
    require(out.get('verdict') in ('pass','block') and isinstance(out.get('findings'),list),'bootstrap审查结论无效')
    require(isinstance(out.get('artifacts_read'),list) and out['artifacts_read'],'bootstrap审查缺少实际源文件读取')
    for name in out['artifacts_read']:require(inside(root/'worktree',name).is_file(),'bootstrap审查引用不存在的文件')
    required=set(c['scope']['frozen_paths'])|{name for names in delegation(root)['entry_dependencies'].values() for name in names}
    require(required.issubset(set(out['artifacts_read'])),'bootstrap审查必须列出实际检查的全部固定评价/审计与条目实现源文件')
    out.update(reviewer=record.get('backend','codex')+'-independent',agent_id=record['thread_id'],invocation=record)
    write_json(root/'evidence'/'reviews'/(candidate['id']+'-'+uuid.uuid4().hex[:8]+'.json'),out)
    a['bootstrap_review']=out
    if out['verdict']=='block':return _blocked_review(root,a,out)
    a.update(bootstrap_pending=False,bootstrap_closed=True)
    persist(root,a,'bootstrap_code_independently_reviewed_before_audit')
    return a


def _record_file(root,out):
    path=root/'adaptive'/'records'/(uuid.uuid4().hex+'.json');write_json(path,out);return path


def _prepare_candidate(root,a,entry,level):
    s=load_state(root);p=read_json(root/'adaptive'/'proposals'/(a['current_proposal']+'.json'))['proposal']
    spec=next(e for e in p['entries'] if e['entry']==entry)
    command=spec['screening_command' if level=='screening' else 'command']
    # Reconcile a crash after engine.candidate's durable snapshot but before this
    # supervisor's current_candidate pointer; preserve and adopt the same evidence.
    commit=project.commit(root);cand=None
    for path in sorted((root/'candidates').glob('*.json')):
        existing=read_json(path)
        if (existing['revision']==s['revision'] and existing.get('entry')==entry and existing['commit']==commit
                and existing['command']==command and not existing['runs'] and project.clean(root)
                and existing.get('evidence_level',level)==level):
            cand=existing;break
    if cand is None:
        ident='a-'+uuid.uuid4().hex[:12];command_path=_record_file(root,command)
        with internal():cand=engine.candidate(root,ident,'matrix',command_path,p['reason'],entry)
    ident=cand['id']
    cand['evidence_level']=level;cand['condition_fingerprint']=condition_fingerprint(root,entry,command)
    write_json(root/'candidates'/(ident+'.json'),cand)
    a.update(current_candidate=ident,current_entry=entry,evidence_level=level)
    persist(root,a,'candidate_screening_created' if level=='screening' else 'candidate_formal_created')
    _review_candidate(root,a,cand)


def _retry_incident(root,a,s):
    issue=s['pending_incident'];write_json(root/'evidence'/'failures'/('adaptive-'+issue['incident_id']+'.json'),issue)
    formal_negative=issue['kind']=='formal_validation'
    if not formal_negative and issue.get('run_id'):
        failed=read_json(root/'runs'/issue['run_id']/'record.json')
        a['recovery_source']={'candidate_id':failed['candidate_id'],'failed_run':failed['run_id'],'seed':failed['seed']}
        if a.get('paused_run')==failed['run_id']:
            # Explicit pause/resume is a continuation, never an automatic fault retry.
            p=read_json(root/'adaptive'/'proposals'/(a['current_proposal']+'.json'))['proposal']
            c=engine.current_contract(root,s)
            from .recovery import clone_candidate
            recovered=clone_candidate(root,a,s,c,delegation(root),p,project.commit(root))
            require(recovered is not None,'暂停期间条件改变，须人工核验恢复方向')
            s.update(status='ready',pending_incident=None)
            a.update(current_candidate=recovered['id'],current_entry=recovered['entry'],evidence_level=recovered['evidence_level'],paused_run=None)
            save_state(root,s,'explicit_user_resume_current_seed')
            persist(root,a,'user_resume_preserved_seeds_no_fault_charge');return
    a.update(diagnosis=issue,repair_pending=not formal_negative,revision_pending=formal_negative,current_candidate=None)
    # The proposer diagnoses actual fault evidence; it cannot alter definitions.
    if not formal_negative and a['fault_retries']>=delegation(root)['budgets']['max_fault_retries']:
        return _stop(root,a,'fault_retry_limit')
    s['status']='ready';s['pending_incident']=None;save_state(root,s,'preauthorized_incident_diagnosis')
    persist(root,a,'fault_preserved_for_bounded_repair')


def step(root):
    # Separate long-lived execution lock excludes scheduler/manual step collisions.
    from .scheduler import step_lock
    with step_lock(root):return _step(root)


def _step(root):
    verify_original(root)
    a=status(root);sync_projection(root,a)
    if a['status'] in TERMINAL:return a
    d=delegation(root)
    require(digest(d)==a['delegation_hash'],'初次委托被修改；拒绝自动执行')
    if datetime.now(timezone.utc)>=utc(a['deadline_utc']):return _stop(root,a,'deadline')
    if a['training_spent_seconds']>=d['budgets']['training_seconds']:return _stop(root,a,'training_budget')
    s=load_state(root);c=engine.current_contract(root,s)
    require(digest(c)==a['contract_hash'],'初次确认契约被修改；不得自动放宽范围或预算')
    require(digest({k:c[k] for k in ('task','data','primary_metric','guard_metrics','verification','matrix')})==a['scientific_identity'],
            '固定科学定义或矩阵目标已改变')
    if s.get('active_run') or s.get('active_test'):return a
    if a.get('final_selection'):
        if c['test']['policy']=='none':return _stop(root,a,'validation_complete_no_heldout_test','completed')
        for entry,done in a['final_selection']['entries'].items():
            if done['candidate_id'] not in a['tested_candidates']:
                # Test results never return to a proposal; test failures require a human.
                previous=[t for t in s['tests'] if t['candidate_id']==done['candidate_id']]
                if previous:
                    if previous[-1].get('error'):return _stop(root,a,'locked_test_failed_requires_human','awaiting_human')
                    a['tested_candidates'].append(done['candidate_id']);persist(root,a,'final_test_recorded');return a
                with internal():engine.test(root,done['candidate_id'],'最终验证全部达标后统一冻结测试；结果仅报告')
                persist(root,a,'final_test_started');return a
        return _stop(root,a,'frozen_test_complete_no_search_feedback','completed')
    if s.get('test_looks'):return _stop(root,a,'unexpected_test_exposure','awaiting_human')
    if s['status']=='awaiting_report':
        _retry_incident(root,a,s);return a
    if a.get('pending_correction'):
        from .agent_runner import invoke
        payload=_agent_payload(root,a,'correction_review');payload['correction']=read_json(root/'adaptive'/'pending-correction.json')
        out,record=invoke(root,d,'correction_review',payload)
        out,record=normalize_review(root,out,record)
        out['invocation']=record;_apply_correction(root,a,out);return a
    if not s.get('audit'):
        needed=set(c['scope']['frozen_paths'])|{name for names in d['entry_dependencies'].values() for name in names}
        missing=[name for name in needed if not inside(root/'worktree',name).is_file()]
        if a.get('bootstrap_pending') or (missing and bootstrap_allowed(root)):
            return _bootstrap_step(root,a,c)
        require(not missing,'冻结/依赖实现缺失且初始实现窗口已关闭')
        if a.get('bootstrap_review'):
            require(a['bootstrap_review']['verdict']=='pass' and a['bootstrap_review']['commit']==project.commit(root)
                    and project.clean(root),'初次代码审查后发生改动；禁止执行未审audit')
        a['bootstrap_closed']=True
        persist(root,a,'initial_implementation_window_closed_before_audit')
        with internal():engine.audit(root)
        persist(root,a,'split_audit_passed');return a
    if not a.get('current_proposal') or a.get('repair_pending') or a.get('revision_pending'):
        if a.get('revision_pending') and a['method_revisions']>=d['budgets']['max_method_revisions']:
            return _stop(root,a,'method_revision_limit')
        # Reserve cannot be spent on another method proposal with no exploration headroom.
        source=a.get('recovery_source')
        source_candidate=read_json(root/'candidates'/(source['candidate_id']+'.json')) if source else None
        formal_repair=a.get('repair_pending') and (a.get('evidence_level')=='formal' or
                        (source_candidate and source_candidate.get('evidence_level')=='formal'))
        if a.get('current_proposal') and not formal_repair and d['budgets']['training_seconds']-a['training_spent_seconds']<=d['budgets']['formal_reserve_seconds']:
            return _stop(root,a,'formal_reserve_insufficient_for_new_exploration')
        from .agent_runner import invoke
        out,record=invoke(root,d,'proposal',_agent_payload(root,a,'proposal'))
        if out.get('action')=='correct_evaluator':return correct(root,out)
        install_proposal(root,a,out,record);return a
    ref=c['matrix']['reference']
    ordered=[ref]+[e['id'] for e in c['matrix']['entries'] if e['id']!=ref]
    if ref in s['matrix_done']:
        sign=1 if engine.higher(c) else -1
        if sign*(s['matrix_done'][ref]['value']-d['rules']['baseline_floor'])<0:
            a.update(revision_pending=True,diagnosis='基线低于确认合理水平；先核验基线，不判主方法优势')
            persist(root,a,'baseline_validation_failed');return a
    if len(s['matrix_done'])==len(ordered):
        try:gate=formal_gate(root,s)
        except GateError:
            if datetime.now(timezone.utc)>=utc(a['deadline_utc']):return _stop(root,a,'deadline_during_formal_statistics')
            raise
        write_json(root/'adaptive'/'gates'/(uuid.uuid4().hex+'.json'),gate)
        if gate['passed']:
            deadline_timeout(root,1)
            a['final_selection']={'time':timestamp(),'entries':copy.deepcopy(s['matrix_done']),'formal_gate':gate,
                                  'frozen_commit':project.commit(root),'revision':s['revision']}
            a['current_candidate']=None;persist(root,a,'early_convergence_final_frozen');return a
        a.update(revision_pending=True,diagnosis=gate);persist(root,a,'formal_gate_not_met');return a
    entry=next(e for e in ordered if e not in s['matrix_done'])
    if not a.get('current_candidate') or a.get('current_entry')!=entry:
        classification=a.get('pending_method_classification')
        _prepare_candidate(root,a,entry,'formal' if entry==ref or classification else 'screening');return a
    cand=read_json(root/'candidates'/(a['current_candidate']+'.json'))
    if not cand.get('review'):
        _review_candidate(root,a,cand);return a
    if cand['review']['verdict']=='block':_blocked_review(root,a,cand['review']);return a
    if a.get('pending_method_classification'):
        _classify_review(root,a,cand,cand['review']);return a
    runs=[read_json(root/'runs'/rid/'record.json') for rid in cand['runs']]
    successful=[r for r in runs if r['status']=='completed']
    if cand['evidence_level']=='screening' and successful:
        value=successful[0]['value'];sign=1 if engine.higher(c) else -1
        role=next(e['role'] for e in c['matrix']['entries'] if e['id']==entry)
        if role=='proposed' and sign*(value-d['rules']['screening_floor'])<0:
            a.update(current_candidate=None,revision_pending=True,diagnosis={'screening_rejected':cand['id'],'value':value})
            persist(root,a,'screening_rejected_not_formal_evidence');return a
        _prepare_candidate(root,a,entry,'formal');return a
    used={r['seed'] for r in runs}
    seed=next((seed for seed in c['verification']['seeds'] if seed not in used),None)
    require(seed is not None,'候选已无可用seed但尚无正式结果；请人工核验')
    try:admit_training(root,a,cand['evidence_level'],c['budget']['run_timeout_seconds'])
    except GateError:return _stop(root,a,'formal_reserve_or_training_budget')
    with internal():engine.run(root,cand['id'],seed)
    persist(root,a,'owned_training_started');return a


def export(root):
    a=status(root);report=engine.export(root)
    a=status(root);raw=read_json(root/'report.json');s=raw['state'];d=delegation(root)
    gate=(a.get('final_selection') or {}).get('formal_gate')
    if gate is None and isinstance(a.get('diagnosis'),dict) and 'problems' in a['diagnosis']:
        gate=a['diagnosis']
    if gate is None:gate={'passed':False,'problems':['formal_gate_not_completed_or_evidence_not_current']}
    evidence={'screening_run_ids':[],'invalidated_run_ids':[],'valid_completed_formal_run_ids':[],
              'failed_run_ids':[],'blocked_reviews':0}
    records=raw['runs']
    for rec in records:
        candidate_path=root/'candidates'/(rec['candidate_id']+'.json')
        candidate=read_json(candidate_path) if candidate_path.is_file() else {}
        if rec.get('invalidated'):evidence['invalidated_run_ids'].append(rec['run_id'])
        elif candidate.get('evidence_level')=='screening' or rec.get('evidence_level')=='screening':
            evidence['screening_run_ids'].append(rec['run_id'])
        elif rec['status']=='completed':evidence['valid_completed_formal_run_ids'].append(rec['run_id'])
        if rec['status'] in ('anomaly','failed','interrupted'):evidence['failed_run_ids'].append(rec['run_id'])
    for path in (root/'evidence'/'reviews').glob('*.json'):
        if read_json(path).get('verdict')=='block':evidence['blocked_reviews']+=1
    latest=max(records,key=lambda r:r.get('created_at') or r.get('finished_at') or '') if records else None
    acceptance={'status':a['status'],'stop_reason':a.get('stop_reason'),'formal_gate':gate,
                'training_spent_seconds':a['training_spent_seconds'],'budgets':d['budgets'],
                'method_revisions':a['method_revisions'],'fault_retries':a['fault_retries'],
                'deadline_utc':a['deadline_utc'],'latest_attempt':latest,'valid_entry_results':s.get('matrix_done',{}),
                'final_selection':a.get('final_selection'),'test_looks':s.get('test_looks',0),
                'evidence_classification':evidence}
    raw['legacy_acceptance_status']=raw['acceptance_status'];raw['acceptance_status']=a['status']
    raw['adaptive_acceptance']=acceptance;write_json(root/'report.json',raw)
    legacy=(root/'report.md').read_text(encoding='utf-8')
    header=['# 自适应委托实验报告','',
        '委托验收状态：**'+a['status']+'**；停止/等待原因：'+str(a.get('stop_reason') or '尚无终止原因')+'。','',
        '正式门：'+('已按委托规则达标并冻结' if gate.get('passed') and a.get('final_selection') else '未达标或未完成')+
        '；未满足项：'+(', '.join(str(x) for x in gate.get('problems',[])) or '无已登记缺项')+'。','',
        f'累计训练：{a["training_spent_seconds"]:.3f} / {d["budgets"]["training_seconds"]} 秒；方法修订：{a["method_revisions"]} / {d["budgets"]["max_method_revisions"]}；故障重试：{a["fault_retries"]} / {d["budgets"]["max_fault_retries"]}；截止：{a["deadline_utc"]}。','',
        f'训练失败记录：{len(evidence["failed_run_ids"])}；审查阻止：{evidence["blocked_reviews"]}；筛选运行：{len(evidence["screening_run_ids"])}；失效运行：{len(evidence["invalidated_run_ids"])}；有效已完成正式运行：{len(evidence["valid_completed_formal_run_ids"])}。筛选和失效运行不属于正式验收证据。','',
        '最新尝试：'+str(latest['run_id']+' / '+latest['candidate_id']+' / '+latest['status'] if latest else '尚无训练运行')+'。',
        '当前有效条目结果（仍须整体优势和全部贡献门）：'+', '.join(sorted(s.get('matrix_done',{})))+'。',
        '最终方案：'+('已冻结；见下方清单' if a.get('final_selection') else '尚未冻结')+f'；测试查看次数：{s.get("test_looks",0)}。','',
        '```json',json.dumps({'formal_gate':gate,'final_selection':a.get('final_selection'),'test_looks':s.get('test_looks',0),
                             'evidence_classification':evidence},ensure_ascii=False,allow_nan=False,indent=2),'```','',
        '下方原始 v2 报告中的 matrix_complete 仅表示矩阵条目完整，不能覆盖上面的自适应委托验收状态；单项结果完整不代表贡献成立或研究有效。','',
        '---','',legacy]
    temporary=root/('report-'+uuid.uuid4().hex+'.tmp')
    with temporary.open('w',encoding='utf-8',newline='\n') as f:
        f.write('\n'.join(header));f.flush();os.fsync(f.fileno())
    os.replace(temporary,root/'report.md')
    write_json(root/'adaptive-report.json',{'adaptive':a,'controlled_report':report,
        'limits':['合成/流程验收不证明医学、临床或外部泛化有效性','同家族新上下文审查不构成科学证明',
                  '控制器不是操作系统沙箱','验证集选择带选择偏倚；冻结测试结果不回流方法选择',
                  '中断可从头重跑当前seed；完整checkpoint连续恢复须训练器和另行协议核验']})
    return {**report,'legacy_status':report.get('status'),'status':a['status'],
            'adaptive_report':str(root/'adaptive-report.json'),'adaptive_status':a['status']}


def verify_original(root):
    state=load_state(root)
    checksum=state.get('original_plan_sha256')
    require(isinstance(checksum,str) and len(checksum)==64,'原始计划缺少初始化哈希；不自动迁移或信任历史改写')
    require(hashlib.sha256((root/'plans'/'original.md').read_bytes()).hexdigest()==checksum,
            '原始计划快照已被修改，禁止继续自适应或作为模型输入')


from .review_adapter import normalize_review,reconcile_review
