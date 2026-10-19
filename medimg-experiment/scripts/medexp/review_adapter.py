"""Adaptive-only review evidence adaptation and narrowly bound persistence replay."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
from .common import require,safe_path,read_json,write_json,load_state,timestamp
from . import engine,project


def readable_method_plan(raw):
    try:value=json.loads(raw)
    except (json.JSONDecodeError,TypeError):return raw
    if not isinstance(value,dict):return raw
    excluded={'candidate_id','commit','change_kind','classification_basis','artifacts_read','metadata_read','reviewer','agent_id','verdict','findings'}
    sections=[]
    for key,text in value.items():
        if key in excluded:continue
        if isinstance(text,str) and text.strip():sections.append('### '+key.replace('_',' ')+'\n\n'+text.strip())
    return '\n\n'.join(sections) if sections else raw


def _metadata_allowed(root,path,invocation):
    if not path.is_relative_to(root):return False
    parts=path.relative_to(root).parts
    if len(parts)==4 and parts[:2]==('adaptive','agents'):
        return parts[2]==invocation and parts[3] in ('input.json','invocation.json')
    if len(parts)==3 and parts[:2] in (('adaptive','proposals'),('adaptive','recovery')):
        return path.suffix=='.json'
    if len(parts)==2 and parts[0]=='candidates':return path.suffix=='.json'
    if len(parts)==2 and parts[0]=='plans':
        return bool(re.fullmatch(r'contract-\d+\.json',parts[1]) or parts[1]=='original.md')
    if len(parts)==3 and parts[0]=='runs' and parts[2] in ('record.json','contract.json','candidate.json'):
        record=root/'runs'/parts[1]/'record.json'
        return record.is_file() and read_json(record).get('phase')!='test'
    return False


def normalize_review(root,out,record):
    """Never discard an unknown read; source and allowlisted metadata must exist."""
    out=copy.deepcopy(out);record=copy.deepcopy(record)
    require(isinstance(out.get('artifacts_read'),list),'审查源码读取列表无效')
    require(isinstance(out.get('additional_evidence',[]),list),'附加审查证据列表无效')
    s=load_state(root);c=engine.current_contract(root,s);work=root/'worktree'
    # Only the project root bound at delegation initialization is a third base.
    # This base resolves allowlisted study metadata, never new source/raw paths.
    bound=read_json(root/'adaptive'/'state.json').get('bound_project_root')
    declared=set(c['scope']['frozen_paths'])|set(c['code']['files'])
    from .adaptive import delegation
    declared|={name for names in delegation(root)['entry_dependencies'].values() for name in names}
    sources=[];metadata=[];mapping=[]
    for field in ('artifacts_read','additional_evidence'):
        for raw in out.get(field,[]):
            require(isinstance(raw,str) and raw.strip(),'审查读取路径必须为非空字符串')
            if Path(raw).is_absolute():choices=[safe_path(raw)]
            else:
                bases=[work,root] if field=='artifacts_read' else [root,work]
                choices=[safe_path(base/raw) for base in bases]
            path=next((p for p in choices if p.is_file()),choices[0])
            if not path.is_file() and not Path(raw).is_absolute() and bound:
                project_path=safe_path(Path(bound)/raw)
                if project_path.is_file():
                    require(_metadata_allowed(root,project_path,record.get('invocation_id')),
                            '审查元数据未获准，禁止tests/rawdata/任意外部: '+raw)
                    path=project_path
            require(path.is_file(),'审查引用的文件不存在: '+raw)
            if path.is_relative_to(work):
                name=path.relative_to(work).as_posix()
                require('.git' not in path.relative_to(work).parts and
                        (name in declared or project.matches(name,c['scope']['editable_paths'])),
                        '审查源码不在批准范围: '+raw)
                if name not in sources:sources.append(name)
                target='artifacts_read';canonical=name
            else:
                require(_metadata_allowed(root,path,record.get('invocation_id')),'审查元数据未获准，禁止tests/rawdata/任意外部: '+raw)
                canonical=path.relative_to(root).as_posix()
                if canonical not in metadata:metadata.append(canonical)
                target='additional_evidence'
            if field!=target or raw!=canonical:
                mapping.append({'raw_field':field,'raw_path':raw,'canonical_field':target,'canonical_path':canonical})
    require(sources,'审查必须包含实际存在的受管源码，不能仅阅读元数据')
    out['artifacts_read']=sources;out['additional_evidence']=metadata
    if mapping:record['review_input_normalizations']=mapping
    ident=record.get('invocation_id')
    if ident:
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,96}',ident),'调用身份无效')
        path=root/'adaptive'/'agents'/ident/'invocation.json'
        if path.is_file() and mapping:
            saved=read_json(path);saved['review_input_normalizations']=mapping;write_json(path,saved)
    return out,record


def reconcile_review(root,invocation_path):
    """Replay one already completed real review; never authorize a new decision."""
    from . import adaptive as runtime
    from .scheduler import step_lock
    from .process import is_alive
    with step_lock(root):
        runtime.verify_original(root);a=runtime.status(root);s=load_state(root);d=runtime.delegation(root)
        c=engine.current_contract(root,s)
        require(a['status']=='awaiting_human','仅技术性审查登记失败可协调；暂停/停止不能解除')
        technical=a.get('stop_reason','')
        prefixes=('GateError: 路径越出受管目录','GateError: 必须使用相对路径','GateError: 审查引用的文件不存在',
                  'GateError: 审查元数据未获准')
        pending=a.get('review_persistence_pending')
        require(technical.startswith(prefixes) or (pending and technical.startswith(('OSError:','PermissionError:'))),
                '不得解除resource/post-test/uncertain或其他人工关口')
        event_records=[json.loads(line) for line in (root/'adaptive'/'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        causal=next((event for event in reversed(event_records) if event.get('event_id')==a.get('last_event')),None)
        require(causal and causal.get('event')=='scheduler_error_requires_human','最后事件并非审查登记技术失败，禁止解除人工门')
        require(not s.get('active_run') and not s.get('active_test') and not s.get('test_looks')
                and not a.get('final_selection'),'有活动运行/已冻结/已见测试，禁止审查协调')
        require(runtime.digest(c)==a['contract_hash'] and runtime.digest(d)==a['delegation_hash'],'确认契约或授权已变化')
        require(a['deadline_utc']==d['deadline_utc'],'协调不能改变初始截止时间')
        runtime.deadline_timeout(root,1)
        scheduler=a.get('scheduler')
        require(not scheduler or not is_alive(scheduler['pid'],scheduler['token']),'原调度器仍活跃，禁止并发协调')
        ident=a.get('current_candidate');require(ident,'没有待登记的当前候选')
        cand=read_json(root/'candidates'/(ident+'.json'))
        require(cand.get('review') is None,'当前候选已有审查，不能重复登记或重计分类')
        for rid in cand['runs']:
            prior=read_json(root/'runs'/rid/'record.json')
            require(prior['candidate_id']!=ident and prior['status']=='completed' and not prior.get('invalidated'),
                    '待审当前候选已经运行，不能借协调跳过训练前审查')
        require(project.clean(root) and project.commit(root)==cand['commit'],'当前源码已变更，旧审查失效')
        path=safe_path(invocation_path)
        require(path.name=='invocation.json' and path.parent.parent==root/'adaptive'/'agents','仅接受本study实际调用记录')
        record=read_json(path);folder=path.parent
        require(record.get('invocation_id')==folder.name and record.get('purpose')=='review' and
                record.get('fresh_context') is True and record.get('status')=='completed' and
                record.get('sandbox')=='read-only','不是已完成的真实新上下文只读审查')
        thread=record.get('thread_id');require(isinstance(thread,str) and thread.strip(),'缺少真实thread身份')
        uuid.UUID(thread)
        argv=record.get('argv',[])
        require(argv and os.path.normcase(str(safe_path(argv[0])))==os.path.normcase(str(safe_path(d['codex']['executable'])))
                and 'exec' in argv and '--ephemeral' in argv and '--json' in argv,'实际Codex命令身份不匹配')
        require('-s' in argv and argv[argv.index('-s')+1]=='read-only' and '-C' in argv and
                safe_path(argv[argv.index('-C')+1])==root/'worktree','实际调用沙箱/工作目录不匹配')
        events=[]
        for line in (folder/'events.jsonl').read_text(encoding='utf-8',errors='replace').splitlines():
            try:events.append(json.loads(line))
            except json.JSONDecodeError:continue
        require(any(e.get('type')=='thread.started' and e.get('thread_id')==thread for e in events)
                and any(e.get('type')=='turn.completed' for e in events),'没有匹配的真实新会话/完成事件')
        saved=read_json(folder/'input.json');expected=runtime._agent_payload(root,a,'review');expected['candidate']=cand
        for key in ('contract','delegation','candidate','current_commit','original_plan','proposal','method_plan',
                    'pending_method_classification','validation_runs','diagnosis'):
            require(saved.get(key)==expected.get(key),'已完成审查输入绑定不再一致: '+key)
        require(saved==expected,'已完成审查完整输入绑定不再一致')
        if pending:require(pending['invocation_id']==folder.name and pending['candidate_id']==ident,'待登记调用身份不匹配')
        raw=read_json(folder/'result.json')
        require(raw.get('candidate_id')==ident and raw.get('commit')==cand['commit'] and raw.get('verdict')=='pass',
                '只能登记该候选实际已完成的pass；不得制造通过')
        require(raw.get('change_kind')!='uncertain','不确定的语义分类不能通过技术协调解除')
        out,record=normalize_review(root,raw,record)
        out.update(reviewer='codex-independent',agent_id=thread,invocation=record,
                   identity_assurance='replayed actual completed fresh Codex exec; same-family; not scientific proof')
        before={'training_spent_seconds':a['training_spent_seconds'],'fault_retries':a['fault_retries'],
                'method_revisions':a['method_revisions'],'deadline_utc':a['deadline_utc']}
        a.setdefault('reconciliations',[]).append({'time':timestamp(),'old_status':a['status'],
             'old_stop_reason':technical,'invocation_id':folder.name,'thread_id':thread,'budgets_before':before})
        a['status']='ready';a.pop('stop_reason',None)
        with runtime.internal():engine.review(root,runtime._record_file(root,out))
        if a.get('pending_method_classification'):runtime._classify_review(root,a,cand,out)
        a['review_persistence_pending']=None
        a['method_plan']=readable_method_plan(a['method_plan'])
        runtime.persist(root,a,'completed_fresh_review_reconciled_without_new_authorization')
        return a
