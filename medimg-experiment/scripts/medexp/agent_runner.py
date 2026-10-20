"""Actual bounded native CLI invocations; no synthetic production backend."""
import json
import time
import uuid
from datetime import datetime, timezone

from .common import require, write_json, read_json, timestamp, safe_path
from .process import OwnedProcess
from .agent_backends import (validate_backend, build_argv, recorded_argv, child_environment,
                             read_events, parse_claude_events, provider_schema, READ_ONLY_TOOLS)


def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


STRING={'type':'string'}
ARGV={'type':'array','items':STRING}
FILE=obj({'path':STRING,'content':STRING})
ENTRY=obj({'entry':STRING,'command':ARGV,'screening_command':ARGV})
PROPOSAL=obj({'action':{'type':'string','enum':['candidate','stop','request_resource','correct_evaluator']},
              'reason':STRING,'method_plan':STRING,'files':{'type':'array','items':FILE},
              'entries':{'type':'array','items':ENTRY},'definition_unchanged':{'type':'boolean'}})
REVIEW=obj({'candidate_id':STRING,'commit':STRING,'verdict':{'type':'string','enum':['pass','block']},
            'findings':{'type':'array','items':STRING},'artifacts_read':ARGV,'limitations':STRING,
            'change_kind':{'type':'string','enum':['initial','fault_repair','method_revision','uncertain']},
            'additional_evidence':ARGV})


def invoke(root, delegation, purpose, payload):
    from .adaptive import utc
    backend=validate_backend(delegation)
    ident=purpose+'-'+uuid.uuid4().hex[:12]
    directory=root/'adaptive'/'agents'/ident;directory.mkdir(parents=True)
    schema=provider_schema(backend,PROPOSAL if purpose=='proposal' else REVIEW)
    write_json(directory/'schema.json',schema);write_json(directory/'input.json',payload)
    prompt=(
        'You are a fresh independent medical imaging experiment '+purpose+'. Read the JSON input at '+str(directory/'input.json')+'. '
        'You may inspect only managed code and metadata needed to assess this task. Never read patient data, test outputs, '
        'credentials, or any configured blocked root. Never train, install, download, change files, call another model API, or execute '
        'commands other than read-only source/metadata inspection. Any Python inspection must use only the approved interpreter '
        'in input contract.environment.python with -X utf8. '
        'Do not change scientific task, labels, split, grouping unit, metric definitions, fixed evaluation, contribution goals, '
        'formal seeds or budgets. Resources/dependencies/weights need existing authorization; never download them. '
        'Return only the structured result. No score self-grading, no fabricated human approval or fabricated review evidence. '
    )
    if purpose=='proposal':
        prompt+=(
            'Your exclusive role in this call is PROPOSER, not reviewer. Supply complete file contents only for permitted editable paths, '
            'a reason grounded in observed validation evidence, and ALL matrix entries with command and screening_command. '
            'method_plan MUST be readable Markdown paragraphs/headings describing the current technical route, training, validation and next actions. '
            'Do not put serialized JSON, reviewer IDs, audit logs or a simulated review verdict in method_plan. '
            'Training argv MUST be ["{python}","train.py","--seed","{seed}",...] with the permitted script filename; '
            'do not add -X or interpreter flags because the controller injects -X utf8. Preserve baseline-first and fair formal training. '
            'Screening may use smaller preauthorized settings but is never formal evidence. Do not tweak the evaluator to make metrics pass. '
            'correct_evaluator requires an evidenced bug restoring the original definition, definition_unchanged=true and affected files. '
            'Use request_resource and wait if a new code/weights/dependency authorization is required. Return only PROPOSAL schema.'
        )
    else:
        prompt+=(
            'Your exclusive role is independent READ-ONLY REVIEWER. Inspect actual source, interfaces, fixed scope, fair baseline and ablation, '
            'test isolation and any proposed correction. Do not assume pass or generate a new method proposal. Bind candidate_id and commit '
            'to the input candidate; correction reviews use evaluator-correction and current_commit. '
            'artifacts_read contains ONLY actual source files as paths relative to worktree, with no .. and no absolute paths. '
            'Place permitted study metadata actually read in additional_evidence using study-relative paths: this invocation input/invocation, '
            'managed proposals/recovery/candidates/contracts and validation-run record metadata. Never read or cite tests, raw data or arbitrary external files. '
            'Independently classify change_kind from prior method, real incident and old/new code as initial, fault_repair restoring the same intended method, '
            'method_revision changing the method, or uncertain; do not accept the proposer label. Inspect the original commit/proposal and actual diff '
            'when pending_method_classification is supplied. Only fault_repair may use formal reserve without a method round; '
            'method_revision needs a method round and exploration allowance. Same-family review does not establish scientific validity. Return only REVIEW schema.'
        )
    if payload.get('bootstrap'):
        prompt+=' This is bounded initial bootstrap BEFORE any audit, frozen commit or run. Only the proposer may propose complete initial training, audit and frozen evaluator implementations explicitly listed in scope, implementing confirmed definitions. Never run them. A bootstrap reviewer must inspect ALL frozen audit/evaluator and declared entry source files and list them in artifacts_read before audit execution. This initial permission closes permanently after review/audit.'
    if backend=='claude' and purpose!='proposal':
        metadata='adaptive/agents/'+ident+'/'
        prompt+=(' For this Claude call, metadata reads are restricted to THIS invocation input.json and invocation.json. '
                 'All other necessary study metadata is already embedded in input.json. additional_evidence must be [] or '
                 'contain only these canonical study-relative paths: '+metadata+'input.json and '+metadata+'invocation.json. '
                 'Use exact path strings without a study-directory prefix, comments, annotations or explanations. '
                 'Read managed source only from the working directory; do not request additional directory access.')
        if payload.get('pending_method_classification'):
            prompt+=(' Independently inspect method_classification_evidence in input.json: the controller supplied '
                     'the bound prior/current Git commits, actual source_diff and archived prior_proposal. Compare them '
                     'with current managed source, the incident and current proposal before change_kind classification. '
                     'These are evidence, not a controller verdict. Return uncertain if they do not support classification.')
    (directory/'prompt.txt').write_text(prompt,encoding='utf-8')
    session=str(uuid.uuid4()) if backend=='claude' else None
    argv=build_argv(root,delegation,directory,prompt,schema,session)
    remaining=(utc(delegation['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()
    timeout=min(delegation['budgets']['step_timeout_seconds'],remaining)
    record={'invocation_id':ident,'purpose':purpose,'fresh_context':True,'started_at':timestamp(),
            'backend':backend,'argv':recorded_argv(argv,backend),
            'sandbox':'read-only' if backend=='codex' else None,'model_override':None,
            'thread_id':None,'status':'running','identity_assurance':'actual CLI events; same-family; not scientific proof'}
    if backend=='claude':record.update(requested_session_id=session,read_only_mechanism=READ_ONLY_TOOLS,
                                       cwd=str(safe_path(root/'worktree')))
    write_json(directory/'invocation.json',record)
    owner=None
    start=time.monotonic()
    try:
        require(timeout>0,backend+'调用前整体截止时间已到')
        owner=OwnedProcess(argv,record['cwd'] if backend=='claude' else str(root/'worktree'),
                           child_environment(delegation),str(directory/'events.jsonl'))
        while owner.poll() is None:
            require(time.monotonic()-start<timeout,backend+'步骤/整体截止时间超时')
            a=read_json(root/'adaptive'/'state.json')
            require(a['status'] not in ('paused','stopped'),'用户暂停或停止了'+backend+'调用')
            time.sleep(.2)
        code=owner.poll();require(code==0,'真实'+backend+'调用失败，查看脱敏本地调用日志: '+str(directory))
        if backend=='claude':
            stream=read_events(directory/'events.jsonl')
            result=parse_claude_events(stream,session,schema,safe_path(root/'worktree'))
            record['thread_id']=session
            init=next(e for e in stream if e.get('type')=='system' and e.get('subtype')=='init')
            if isinstance(init.get('model'),str):record['model']=init['model']
            record['actual_tools']=init['tools']
            write_json(directory/'result.json',result)
        else:
            require((directory/'result.json').is_file(),'Codex没有结构化最终输出')
            for line in (directory/'events.jsonl').read_text(encoding='utf-8',errors='replace').splitlines():
                try:event=json.loads(line)
                except json.JSONDecodeError:continue
                if event.get('type')=='thread.started':record['thread_id']=event.get('thread_id')
                if event.get('type')=='turn.completed':record['usage']=event.get('usage')
            require(isinstance(record['thread_id'],str) and record['thread_id'].strip(),
                    '缺少真实新会话 thread.started 身份，不能登记审查通过')
            result=read_json(directory/'result.json')
            require(isinstance(result,dict),'Codex输出必须为JSON对象')
            require(set(result)==set(schema['properties']),'Codex结构化结果字段不匹配')
        record.update(status='completed',finished_at=timestamp(),elapsed_seconds=time.monotonic()-start)
        write_json(directory/'invocation.json',record)
        return result,record
    except Exception as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc),finished_at=timestamp(),
                      elapsed_seconds=time.monotonic()-start)
        write_json(directory/'invocation.json',record)
        raise
    finally:
        if owner is not None:owner.close()
