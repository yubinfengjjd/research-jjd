"""Verified trainer-defined complete checkpoint recovery, or honest seed restart."""
import hashlib
import os
import subprocess
import uuid
from .common import require, inside, read_json, write_json, safe_path, timestamp

FIELDS={'model','optimizer','scheduler','rng_python','rng_numpy','rng_torch','rng_cuda',
        'sampler','progress','selection','configuration'}


def select(root,c,d,source,failed_run,seed):
    from .adaptive import utc
    from datetime import datetime, timezone
    result={'strategy':'restart_current_seed','source_run_id':failed_run,'seed':seed,
            'reason':'未提供可验证的完整恢复协议；保留已完成seed，仅新run重跑当前seed','time':timestamp()}
    policy=d.get('recovery')
    if not policy:return result
    checkpoint=inside(root/'runs'/failed_run,policy['checkpoint'])
    if not checkpoint.is_file():return {**result,'reason':'完整checkpoint缺失；不能把仅权重当续训'}
    out=root/'adaptive'/'recovery'/(uuid.uuid4().hex+'.json');out.parent.mkdir(parents=True,exist_ok=True)
    argv=[]
    for x in policy['validator_command']:
        argv.extend([str(safe_path(c['environment']['python'])),'-X','utf8'] if x=='{python}' else
                    [str(checkpoint) if x=='{checkpoint}' else str(out) if x=='{output}' else x])
    timeout=min(policy['timeout_seconds'],d['budgets']['step_timeout_seconds'],
                (utc(d['deadline_utc'])-datetime.now(timezone.utc)).total_seconds())
    require(timeout>0,'恢复核验前整体截止时间已到')
    try:
        r=subprocess.run(argv,cwd=root/'worktree',capture_output=True,text=True,encoding='utf-8',errors='replace',
                         timeout=timeout,env={**os.environ,'PYTHONUTF8':'1'},creationflags=0x08000000 if os.name=='nt' else 0)
        (out.with_suffix('.log')).write_text(r.stdout[-20000:]+'\n'+r.stderr[-20000:],encoding='utf-8')
        require(r.returncode==0,'恢复核验脚本失败')
        evidence=read_json(out)
        require(evidence.get('compatible') is True and evidence.get('complete_state') is True,'checkpoint状态不完整/不兼容')
        require(FIELDS.issubset(set(evidence.get('fields',[]))),'缺少优化器、随机性、采样或进度等完整恢复状态')
        require(evidence.get('source_run_id')==failed_run and evidence.get('seed')==seed,'checkpoint来源run或seed不一致')
        checksum=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        require(evidence.get('checkpoint_sha256')==checksum,'checkpoint哈希不一致')
        return {**result,'strategy':'resume_full_state','checkpoint':str(checkpoint),'checkpoint_sha256':checksum,
                'validator_evidence':str(out),'reason':evidence.get('reason','完整状态已由冻结训练器协议核验')}
    except Exception as exc:
        return {**result,'reason':'完整恢复核验未通过；新run重跑当前seed: '+str(exc),'validator_evidence':str(out)}


def clone_candidate(root,a,s,c,d,p,commit):
    from .adaptive import condition_fingerprint
    source_meta=a.pop('recovery_source',None)
    if not source_meta:return None
    old=read_json(root/'candidates'/(source_meta['candidate_id']+'.json'))
    spec=next(e for e in p['entries'] if e['entry']==old['entry'])
    command=spec['screening_command' if old['evidence_level']=='screening' else 'command']
    fingerprint=condition_fingerprint(root,old['entry'],command)
    if old.get('condition_fingerprint')!=fingerprint:
        write_json(root/'adaptive'/'recovery'/(uuid.uuid4().hex+'.json'),
                   {'strategy':'retrain_changed_conditions','source':source_meta,'reason':'条件已变，旧seed或checkpoint不得混用'})
        return None
    good=[rid for rid in old['runs'] if read_json(root/'runs'/rid/'record.json')['status']=='completed' and
          not read_json(root/'runs'/rid/'record.json').get('invalidated')]
    recovery=select(root,c,d,old,source_meta['failed_run'],source_meta['seed'])
    ident='recovery-'+uuid.uuid4().hex[:12]
    review=old.get('review') if old['commit']==commit and old['command']==command else None
    if review:
        review={**review,'candidate_id':ident,'reused_from_candidate':old['id'],
                'reuse_reason':'完全相同已审代码与命令，仅重新执行当前seed/完整状态恢复'}
    candidate={**old,'id':ident,'commit':commit,'revision':s['revision'],'command':command,'runs':good,
               'review':review,'recovery':recovery,'condition_fingerprint':fingerprint,'description':p['reason']}
    write_json(root/'candidates'/(ident+'.json'),candidate)
    from . import project
    project.git(root/'worktree','update-ref','refs/medexp/candidates/'+ident,commit)
    return candidate
