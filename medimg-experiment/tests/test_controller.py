import copy
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts' / 'controller.py'


def contract(source, plan, data):
    return {
        'schema_version': 2, 'study_id': 'fixture-study', 'task': 'classification', 'mode': 'search',
        'hypothesis': 'approved fixture hypothesis, not scientific evidence',
        'plan_path': str(plan), 'stages': ['baseline', 'explore', 'verify'],
        'code': {'source_root': str(source), 'files': ['train.py', 'evaluate.py', 'audit.py']},
        'primary_metric': {'name': 'accuracy', 'direction': 'higher', 'selection': 'last', 'target': 0.87, 'min_effect': 0.01},
        'guard_metrics': [],
        'baseline': {'source': 'fixture', 'strength_rationale': 'fixture', 'tuning_parity': 'fixture'},
        'data': {'paths': [str(data)], 'labels_source': 'synthetic fixture',
                 'split_reference': 'independent patients train/validation; fixture only',
                 'group_unit': 'patient', 'evaluation_protocol': 'fixed fixture evaluator'},
        'split_audit': {'command': ['{python}', 'audit.py', '{output}'], 'timeout_seconds': 30},
        'test': {'policy': 'none', 'rationale': 'fixture without held-out test'},
        'scope': {'editable_paths': ['train.py'], 'parameters': ['--mode', '--score'], 'frozen_paths': ['evaluate.py', 'audit.py']},
        'anomaly': {'max_drop': 0.05, 'unit': 'absolute', 'warmup_steps': 0,
                    'reference_ranges': {}, 'consecutive_outside_range': 3},
        'budget': {'total_seconds': 120, 'run_timeout_seconds': 15, 'max_candidates': 5, 'max_no_improvement': 3},
        'verification': {'seeds': [1, 2, 3], 'aggregation': 'mean', 'normal_range': [0.8, 0.99], 'max_std': 0.1,
                         'ci': {'method': 'paired_bootstrap', 'statistic': 'mean_per_case', 'resamples': 200,
                                'level': 0.95, 'seed': 7, 'lower_bound_rule': 'zero'}},
        'environment': {'python': sys.executable, 'device': 'cpu', 'dependencies': {}, 'min_free_bytes': 1024},
        'retention': {'mode': 'necessary'},
    }


AUDIT = r'''import json,sys
ids=[f'p{i:02d}' for i in range(20)]
sp={'train':{'group_ids':ids[:10],'class_counts':{'0':5,'1':5}},'val':{'group_ids':ids[10:],'class_counts':{'0':5,'1':5}}}
if 'with-test' in sys.argv:sp['test']={'group_ids':[f't{i:02d}' for i in range(8)],'class_counts':{'0':4,'1':4}}
json.dump({'group_unit':'patient','splits':sp},open(sys.argv[1],'w'))
'''


FIXTURE = r'''import argparse,json,os,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--seed',type=int);p.add_argument('--mode',default='normal');p.add_argument('--score',type=float,default=.85);a=p.parse_args()
out=Path(os.environ['ME_OUTPUT_DIR']);rid=os.environ['ME_RUN_ID'];phase=os.environ['ME_PHASE']
metric=json.loads(Path(os.environ['ME_CONTRACT_PATH']).read_text())['primary_metric']['name']
if a.mode=='crash': raise RuntimeError('injected crash')
if a.mode=='timeout': time.sleep(15)
if a.mode=='slow': time.sleep(.35)
score=float('nan') if a.mode=='nan' else a.score
if a.mode=='variable':score=.75 if a.seed==1 else .95
line={'run_id':rid,'phase':phase,'step':1,'metric':metric,'value':score,'time':'2026-10-12T00:00:00Z'}
with (out/'metrics.jsonl').open('w') as f:f.write(json.dumps(line)+'\n');f.flush()
ids=[f'p{i:02d}' for i in range(10,20)]
vals=[score]*10 if a.mode!='jitter' else [score+(.01 if i%2 else -.01)*(1+a.seed) for i in range(10)]
if score==score:(out/'cases.jsonl').write_text(''.join(json.dumps({'case_id':c,'value':v})+'\n' for c,v in zip(ids,vals)))
if a.mode=='malformed':(out/'result.json').write_text('not json')
else:
 (out/'weights.npz').write_bytes(b'fixture checkpoint, not trained weights')
 ms={metric:score,'brier':.5 if a.mode=='badguard' else .1}
 (out/'result.json').write_text(json.dumps({'run_id':rid,'phase':phase,'completed':True,'metrics':ms,'artifacts':['weights.npz']}))
if a.mode=='delete_metrics':time.sleep(2.3);(out/'metrics.jsonl').unlink()
'''


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='medexp-fixture-')
        self.base = Path(self.tmp.name)
        self.source = self.base/'input';self.source.mkdir()
        (self.source/'train.py').write_text(FIXTURE, encoding='utf-8')
        (self.source/'evaluate.py').write_text('# fixed evaluator fixture\n', encoding='utf-8')
        (self.source/'audit.py').write_text(AUDIT, encoding='utf-8')
        self.plan = self.base/'plan.md';self.plan.write_text('原始计划，不得更改', encoding='utf-8')
        self.data = self.base/'data';self.data.mkdir()
        self.study = self.base/'managed'
        self.c = contract(self.source,self.plan,self.data)
        self.cf = self.base/'contract.json';self.save_contract()

    def tearDown(self):
        # All workers are bounded; wait for the owned worker to exit before cleanup.
        for _ in range(80):
            state = self.study/'state.json'
            if not state.exists() or not json.loads(state.read_text(encoding='utf-8')).get('active_run'):break
            time.sleep(.1)
        self.tmp.cleanup()

    def save_contract(self):self.cf.write_text(json.dumps(self.c),encoding='utf-8')

    def call(self,*args,ok=True):
        r=subprocess.run([sys.executable,str(CLI),*map(str,args)],capture_output=True,text=True,encoding='utf-8',env={**os.environ,'PYTHONUTF8':'1'})
        if ok:self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        else:self.assertNotEqual(r.returncode,0,r.stdout+r.stderr)
        return json.loads(r.stdout)

    def init(self,approve=True):
        self.call('init','--root',self.study,'--contract',self.cf)
        if approve:
            self.call('approve','--root',self.study,'--statement','用户确认该fixture契约与预算')
            self.call('audit','--root',self.study)

    def candidate(self,ident='base',phase='baseline',score=.85,mode='normal'):
        command=self.base/f'{ident}-command.json'
        command.write_text(json.dumps(['{python}','train.py','--seed','{seed}','--score',str(score),'--mode',mode]),encoding='utf-8')
        r=self.call('candidate','--root',self.study,'--id',ident,'--phase',phase,'--command',command,'--description','fixture only')
        review=self.base/f'{ident}-review.json'
        review.write_text(json.dumps({'candidate_id':ident,'commit':r['commit'],'verdict':'pass','reviewer':'independent-subagent','agent_id':'fixture-review-agent','findings':[],'artifacts_read':['train.py','evaluate.py'],'limitations':'test fixture; no real model review'}),encoding='utf-8')
        self.call('review','--root',self.study,'--record',review)
        return ident

    def run_candidate(self,ident,seed):
        self.call('run','--root',self.study,'--candidate',ident,'--seed',seed)
        deadline=time.monotonic()+22
        while time.monotonic()<deadline:
            r=self.call('status','--root',self.study)
            if not r['active_run']:return r
            time.sleep(.1)
        self.fail('worker did not reach terminal state')

    def baseline(self):
        ident=self.candidate();self.run_candidate(ident,1);self.run_candidate(ident,2);return self.run_candidate(ident,3)

    def test_unconfirmed_contract_blocks_training_and_preserves_source(self):
        self.init(False)
        command=self.base/'cmd.json';command.write_text(json.dumps(['{python}','train.py','--seed','{seed}']))
        self.call('candidate','--root',self.study,'--id','base','--phase','baseline','--command',command,'--description','fixture',ok=False)
        self.assertEqual(json.loads((self.study/'state.json').read_text(encoding='utf-8'))['status'],'awaiting_confirmation')
        self.assertEqual(self.plan.read_text(encoding='utf-8'),'原始计划，不得更改')
        self.assertFalse((self.source/'.git').exists())

    def test_missing_success_rule_rejected_before_init_side_effects(self):
        del self.c['primary_metric']['target'];self.save_contract()
        self.call('init','--root',self.study,'--contract',self.cf,ok=False)
        self.assertFalse(self.study.exists())

    def test_relative_external_contract_paths_are_rejected_before_init(self):
        # Each relative path actually exists from the caller cwd; accepting it
        # would bind a different file/data/interpreter from the worker cwd.
        cases=[('plan',('plan_path',),self.plan),
               ('data',('data','paths'),self.data),
               ('python',('environment','python'),Path(sys.executable)),
               ('code',('code','source_root'),self.source)]
        original=copy.deepcopy(self.c)
        for label,keys,value in cases:
            with self.subTest(path=label):
                self.c=copy.deepcopy(original)
                try:
                    rel=os.path.relpath(value,self.base)
                except ValueError:
                    # A Windows interpreter may be on a different drive from
                    # the temp directory.  This gate never executes it.
                    local=self.base/value.name
                    shutil.copy2(value,local)
                    rel=local.name
                if len(keys)==1:self.c[keys[0]]=rel
                else:self.c[keys[0]][keys[1]]=[rel] if label=='data' else rel
                self.save_contract();root=self.base/('relative-'+label)
                r=subprocess.run([sys.executable,str(CLI),'init','--root',str(root),'--contract',str(self.cf)],
                                 cwd=self.base,capture_output=True,text=True,encoding='utf-8',
                                 env={**os.environ,'PYTHONUTF8':'1'})
                self.assertNotEqual(r.returncode,0,r.stdout)
                self.assertIn('绝对路径',r.stdout)
                self.assertFalse(root.exists())

    def test_baseline_requires_all_seeds_and_ordinary_rejection_continues(self):
        self.init();ident=self.candidate()
        r=self.run_candidate(ident,1);self.assertIsNone(r['stable']);self.assertEqual(r['status'],'ready',r)
        r=self.run_candidate(ident,2);self.assertIsNone(r['stable'])
        r=self.run_candidate(ident,3);self.assertIsNotNone(r['stable']);self.assertEqual(r['stage'],'explore')
        r=self.run_candidate(self.candidate('weak','explore',.84),1)
        self.assertEqual(r['status'],'ready');self.assertEqual(r['no_improvement'],1)
        self.assertEqual(r['stable']['value'],.85)

    def test_anomaly_report_precedes_rollback_and_resume_requires_direction(self):
        self.init();self.baseline()
        r=self.run_candidate(self.candidate('bad','explore',.70),1)
        self.assertEqual(r['status'],'awaiting_report')
        self.call('recover','--root',self.study,ok=False)
        self.call('reported','--root',self.study,'--statement','已向用户汇报异常数值与阶段')
        r=self.call('recover','--root',self.study)
        self.assertEqual(r['status'],'awaiting_direction')
        self.assertTrue(list((self.study/'evidence'/'failures').glob('*.json')))
        self.call('resume','--root',self.study,'--contract',self.cf,'--direction','','--statement','用户确认',ok=False)
        self.assertEqual(self.plan.read_text(encoding='utf-8'),'原始计划，不得更改')

    def test_changed_code_invalidates_review_and_frozen_evaluator_is_rejected(self):
        self.init();ident=self.candidate()
        work=self.study/'worktree'
        (work/'train.py').write_text(FIXTURE+'\n# changed\n',encoding='utf-8')
        self.call('run','--root',self.study,'--candidate',ident,'--seed',1,ok=False)
        (work/'train.py').write_text(FIXTURE,encoding='utf-8')
        self.run_candidate(ident,1);self.run_candidate(ident,2);self.run_candidate(ident,3)
        (work/'evaluate.py').write_text('# changed metric\n',encoding='utf-8')
        command=self.base/'cmd.json';command.write_text(json.dumps(['{python}','train.py','--seed','{seed}']))
        self.call('candidate','--root',self.study,'--id','tamper','--phase','explore','--command',command,'--description','fixture',ok=False)

    def test_reaching_target_requires_formal_replication(self):
        self.init();self.baseline()
        r=self.run_candidate(self.candidate('good','explore',.90),1)
        self.assertEqual(r['status'],'verification_required');self.assertNotEqual(r['status'],'accepted')
        # Same code/config are independently reviewed for formal verification.
        ident=self.candidate('formal','verify',.90)
        r=self.run_candidate(ident,1);self.assertNotEqual(r['status'],'accepted')
        r=self.run_candidate(ident,2);self.assertNotEqual(r['status'],'accepted')
        r=self.run_candidate(ident,3);self.assertEqual(r['status'],'accepted')
        self.assertEqual(len(r['stable']['run_ids']),3)
        ci=r['stable']['ci_vs_baseline'];self.assertGreater(ci['ci_low'],0);self.assertEqual(ci['cases'],10)

    def test_crash_nan_bad_output_timeout_all_await_report_without_stable(self):
        for mode in ['crash','nan','malformed','timeout']:
            with self.subTest(mode=mode):
                # Separate study, never retry a failed run.
                self.study=self.base/f'managed-{mode}'
                if mode=='timeout':self.c['budget']['run_timeout_seconds']=.3;self.save_contract()
                self.init();r=self.run_candidate(self.candidate(mode=mode),1)
                self.assertEqual(r['status'],'awaiting_report');self.assertIsNone(r['stable'])
                self.call('reported','--root',self.study,'--statement','已汇报fixture异常')
                r=self.call('recover','--root',self.study)
                self.assertEqual(r['status'],'awaiting_direction')
                self.assertIn('暂无',r['recovery_note'])

    def test_budget_exhaustion_does_not_claim_accepted(self):
        self.c['budget']['max_candidates']=1;self.save_contract()
        self.init();self.baseline()
        self.run_candidate(self.candidate('first','explore',.84),1)
        ident=self.candidate('second','explore',.83)
        self.call('run','--root',self.study,'--candidate',ident,'--seed',1,ok=False)
        r=self.call('status','--root',self.study)
        self.assertEqual(r['status'],'budget_exhausted');self.assertIsNone(r['active_run'])

    def test_blocked_review_and_wrong_stage_cannot_train(self):
        self.init();ident=self.candidate()
        r=self.call('status','--root',self.study)
        self.call('run','--root',self.study,'--candidate',ident,'--seed',4,ok=False)
        cand=json.loads((self.study/'candidates'/'base.json').read_text())
        review=self.base/'blocked.json'
        review.write_text(json.dumps({**cand['review'],'verdict':'block','findings':[{'severity':'major','reason':'fixture blocker'}]}))
        self.call('review','--root',self.study,'--record',review)
        self.call('run','--root',self.study,'--candidate',ident,'--seed',1,ok=False)
        command=self.base/'explore-command.json';command.write_text(json.dumps(['{python}','train.py','--seed','{seed}']))
        self.call('candidate','--root',self.study,'--id','early','--phase','explore','--command',command,'--description','fixture',ok=False)

    def test_successful_resume_retains_plan_history_and_requires_new_baseline(self):
        self.init();self.baseline()
        self.run_candidate(self.candidate('bad','explore',.70),1)
        self.call('reported','--root',self.study,'--statement','已汇报')
        self.call('recover','--root',self.study)
        r=self.call('resume','--root',self.study,'--contract',self.cf,'--direction','用户选择降低学习率','--statement','用户确认新方向及预算')
        self.assertEqual(r['revision'],2);self.assertEqual(r['stage'],'baseline');self.assertIsNone(r['stable'])
        self.assertTrue((self.study/'plans'/'contract-001.json').exists())
        self.assertTrue((self.study/'plans'/'contract-002.json').exists())
        self.assertEqual((self.study/'plans'/'original.md').read_text(encoding='utf-8'),'原始计划，不得更改')

    def test_formal_negative_is_retained_and_requires_report(self):
        self.init();self.baseline()
        ident=self.candidate('good','explore',.90);self.run_candidate(ident,1)
        # Replication criteria may reject high but excessively variable valid results.
        formal=self.candidate('formal','verify',.90)
        self.run_candidate(formal,1);self.run_candidate(formal,2)
        # Test final acceptance logic on a hand-checked observed second replicate,
        # without modifying evaluator or pretending to have actually trained it.
        from importlib import import_module
        scripts=str(ROOT/'scripts')
        if scripts not in sys.path:sys.path.insert(0,scripts)
        module=import_module('medexp.engine')
        from medexp.common import read_json,write_json,locked,load_state,save_state
        rid='r-fixture-final';out=self.study/'runs'/rid;out.mkdir()
        record={'run_id':rid,'candidate_id':formal,'phase':'verify','revision':1,'commit':json.loads((self.study/'candidates'/'formal.json').read_text())['commit'],'seed':3,'status':'running','value':None,'guards':{}}
        write_json(out/'record.json',record)
        with locked(self.study):
            state=load_state(self.study);state['active_run']=rid;state['status']='running';save_state(self.study,state,'fixture_reservation')
            cand=read_json(self.study/'candidates'/'formal.json');cand['runs'].append(rid);write_json(self.study/'candidates'/'formal.json',cand)
        module.finish(self.study,record,.83,{'artifacts':['fixture']},.1)
        r=self.call('status','--root',self.study)
        self.assertEqual(r['status'],'awaiting_report')
        neg=list((self.study/'evidence'/'negative-results').glob('*.json'))
        self.assertEqual(len(neg),1);self.assertTrue(read_json(neg[0])['valid_negative_result'])
        self.assertEqual(r['stable']['value'],.85)

    def test_duplicate_seed_switch_cannot_fake_replication(self):
        self.init()
        command=self.base/'duplicate-seed.json'
        command.write_text(json.dumps(['{python}','train.py','--seed','{seed}','--seed=1']))
        self.call('candidate','--root',self.study,'--id','duplicate','--phase','baseline','--command',command,'--description','fixture',ok=False)

    def test_normal_completion_before_short_deadline_is_not_timeout(self):
        self.c['budget']['run_timeout_seconds']=1.0;self.save_contract();self.init()
        ident=self.candidate()
        r=self.run_candidate(ident,1)
        self.assertEqual(r['status'],'ready',r)

    def test_unhealthy_replicate_cannot_hide_behind_healthy_mean(self):
        self.init();ident=self.candidate(mode='variable')
        self.run_candidate(ident,1);self.run_candidate(ident,2);r=self.run_candidate(ident,3)
        self.assertEqual(r['status'],'awaiting_report');self.assertIsNone(r['stable'])

    def test_missing_worker_registration_is_reconciled_without_starting_training(self):
        self.init()
        rid='r-orphan-fixture';directory=self.study/'runs'/rid;directory.mkdir()
        record={'run_id':rid,'phase':'baseline','worker_pid':None,'worker_token':None,'created_at':'2000-01-01T00:00:00+00:00','status':'queued','value':None}
        (directory/'record.json').write_text(json.dumps(record),encoding='utf-8')
        state=json.loads((self.study/'state.json').read_text(encoding='utf-8'));state.update(active_run=rid,status='running')
        (self.study/'state.json').write_text(json.dumps(state),encoding='utf-8')
        r=self.call('status','--root',self.study)
        self.assertEqual(r['status'],'awaiting_report');self.assertIsNone(r['active_run'])

    def test_destroyed_raw_metrics_cannot_be_accepted_from_cached_value(self):
        self.init();r=self.run_candidate(self.candidate(mode='delete_metrics'),1)
        self.assertEqual(r['status'],'awaiting_report')
        record=json.loads(next((self.study/'runs').glob('*/record.json')).read_text())
        self.assertEqual(record['status'],'anomaly')
        self.assertTrue(next((self.study/'runs').glob('*/metrics.observed.jsonl')).is_file())

    def test_export_during_training_does_not_race_heartbeat_record_writes(self):
        self.init();ident=self.candidate(mode='slow')
        self.call('run','--root',self.study,'--candidate',ident,'--seed',1)
        for _ in range(8):self.call('export','--root',self.study)
        r=self.call('status','--root',self.study)
        deadline=time.monotonic()+10
        while r['active_run'] and time.monotonic()<deadline:
            time.sleep(.1);r=self.call('status','--root',self.study)
        self.assertEqual(r['status'],'ready',r)

    def test_candidate_alias_cannot_silently_repeat_same_code_and_parameters(self):
        self.init();ident=self.candidate('first');self.run_candidate(ident,1)
        command=self.base/'alias-command.json'
        command.write_text(json.dumps(['{python}','train.py','--seed','{seed}','--score','.85','--mode','normal']))
        # Match exact argv of first, independent of candidate label.
        first=json.loads((self.study/'candidates'/'first.json').read_text())
        command.write_text(json.dumps(first['command']))
        self.call('candidate','--root',self.study,'--id','alias','--phase','baseline','--command',command,'--description','same attempt relabelled',ok=False)

    def test_monitor_crash_accounts_elapsed_and_owns_child_cleanup(self):
        self.init();ident=self.candidate(mode='timeout')
        run=self.call('run','--root',self.study,'--candidate',ident,'--seed',1)
        scripts=str(ROOT/'scripts')
        if scripts not in sys.path:sys.path.insert(0,scripts)
        from medexp.common import locked,read_json
        from medexp.process import is_alive
        import _winapi
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            with locked(self.study):record=read_json(self.study/'runs'/run['run_id']/'record.json')
            if record['training_pid']:break
            time.sleep(.05)
        self.assertIsNotNone(record['training_pid'])
        time.sleep(.3)
        self.assertTrue(is_alive(record['worker_pid'],record['worker_token']))
        handle=_winapi.OpenProcess(1,False,record['worker_pid'])
        try:_winapi.TerminateProcess(handle,1)
        finally:_winapi.CloseHandle(handle)
        time.sleep(.1)
        r=self.call('status','--root',self.study)
        self.assertEqual(r['status'],'awaiting_report')
        self.assertGreater(r['spent_seconds'],0)
        self.assertFalse(is_alive(record['training_pid'],record['training_token']))
        with locked(self.study):saved=read_json(self.study/'runs'/run['run_id']/'record.json')
        self.assertTrue(saved['elapsed_seconds_estimated'])

    def test_lower_is_better_metric_uses_correct_rejection_and_target_direction(self):
        self.c['primary_metric'].update(name='loss',direction='lower',target=.13)
        self.c['verification']['normal_range']=[0,1];self.save_contract()
        self.init();self.baseline()
        r=self.run_candidate(self.candidate('worse','explore',.86),1)
        self.assertEqual(r['no_improvement'],1)
        r=self.run_candidate(self.candidate('better','explore',.10),1)
        self.assertEqual(r['status'],'verification_required')
        ident=self.candidate('formal','verify',.10)
        self.run_candidate(ident,1);self.run_candidate(ident,2);r=self.run_candidate(ident,3)
        self.assertEqual(r['status'],'accepted');self.assertAlmostEqual(r['stable']['value'],.10)

    def test_warmup_cannot_hide_collapse_of_a_completed_short_candidate(self):
        self.c['anomaly']['warmup_steps']=10;self.save_contract()
        self.init();self.baseline()
        r=self.run_candidate(self.candidate('shortbad','explore',.70),1)
        self.assertEqual(r['status'],'awaiting_report')


    def test_audit_detects_group_leakage_and_blocks_candidates(self):
        (self.source/'audit.py').write_text(AUDIT.replace("ids[10:]","ids[9:]"),encoding='utf-8')
        self.call('init','--root',self.study,'--contract',self.cf)
        self.call('approve','--root',self.study,'--statement','ok')
        r=self.call('audit','--root',self.study,ok=False);self.assertIn('泄漏',r['summary_zh'])
        command=self.base/'cmd.json';command.write_text(json.dumps(['{python}','train.py','--seed','{seed}']))
        self.call('candidate','--root',self.study,'--id','base','--phase','baseline','--command',command,'--description','fixture',ok=False)

    def test_two_seeds_and_old_schema_rejected(self):
        self.c['verification']['seeds']=[1,2];self.save_contract()
        self.call('init','--root',self.study,'--contract',self.cf,ok=False)
        self.c['verification']['seeds']=[1,2,3];self.c['schema_version']=1;self.save_contract()
        self.call('init','--root',self.study,'--contract',self.cf,ok=False)
        self.assertFalse(self.study.exists())

    def test_guard_degradation_rejects_explore_candidate(self):
        self.c['guard_metrics']=[{'name':'brier','direction':'lower','max_degradation':0.01}];self.save_contract()
        self.init();self.baseline()
        r=self.run_candidate(self.candidate('better-but-worse-guard','explore',.90,mode='badguard'),1)
        self.assertEqual(r['status'],'ready');self.assertEqual(r['no_improvement'],1)
        self.assertTrue(list((self.study/'evidence'/'rejections').glob('*.json')))

    def test_ci_crossing_zero_blocks_acceptance(self):
        self.c['primary_metric']['min_effect']=0.0;self.c['primary_metric']['target']=.85;self.save_contract()
        self.init();self.baseline()
        self.run_candidate(self.candidate('tiny','explore',.851,mode='jitter'),1)
        ident=self.candidate('formal','verify',.851,mode='jitter')
        self.run_candidate(ident,1);self.run_candidate(ident,2);r=self.run_candidate(ident,3)
        self.assertEqual(r['status'],'awaiting_report');self.assertIn('CI',r['pending_incident']['detail'])

    def test_locked_test_only_for_baseline_or_accepted(self):
        (self.source/'test_eval.py').write_text(TEST_EVAL,encoding='utf-8')
        self.c['code']['files'].append('test_eval.py');self.c['scope']['frozen_paths'].append('test_eval.py')
        self.c['split_audit']['command']=['{python}','audit.py','{output}','with-test']
        self.c['test']={'policy':'locked','reference':'fixture test','command':['{python}','test_eval.py','{run_dir}','{output}'],'timeout_seconds':20}
        self.save_contract();self.init();self.baseline()
        ident=self.candidate('good','explore',.90);self.run_candidate(ident,1)
        self.call('test','--root',self.study,'--candidate','good','--rationale','peek',ok=False)
        self.call('test','--root',self.study,'--candidate','base','--rationale','reference')
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            r=self.call('status','--root',self.study)
            if r['status']!='testing':break
            time.sleep(.2)
        self.assertEqual(r['status'],'verification_required');self.assertEqual(r['test_looks'],1)
        self.assertIsNone(r['tests'][0]['error'],r['tests'][0]);self.assertAlmostEqual(r['tests'][0]['summary']['value'],.85)
        self.call('test','--root',self.study,'--candidate','base','--rationale','again',ok=False)


TEST_EVAL = r'''import json,sys
from pathlib import Path
run,out=Path(sys.argv[1]),Path(sys.argv[2])
v=json.loads((run/'result.json').read_text())['metrics']['accuracy']
ids=[f't{i:02d}' for i in range(8)]
(out/'cases.jsonl').write_text(''.join(json.dumps({'case_id':c,'value':v})+'\n' for c in ids))
(out/'result.json').write_text(json.dumps({'completed':True,'metrics':{'accuracy':v}}))
'''


if __name__=='__main__':unittest.main()
