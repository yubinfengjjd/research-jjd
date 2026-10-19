import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
import time
import subprocess
import threading
import ctypes
from ctypes import wintypes
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from medexp import engine
from medexp.common import GateError, load_state, read_json, write_json
from tests.test_controller import contract, FIXTURE, AUDIT

class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='adaptive-test-'); self.base=Path(self.tmp.name)
        self.src=self.base/'src'; self.src.mkdir(); self.data=self.base/'data';self.data.mkdir()
        for name,content in [('train.py',FIXTURE),('evaluate.py','# fixed definition\n'),('audit.py',AUDIT)]:
            (self.src/name).write_text(content,encoding='utf-8')
        self.plan=self.base/'project-plan.md';self.plan.write_text('# Approved original\n',encoding='utf-8')
        self.root=self.base/'study';self.c=contract(self.src,self.plan,self.data)
        self.c.update(mode='matrix',stages=['matrix'],matrix={'reference':'b','entries':[
            {'id':'b','role':'baseline','description':'baseline'}, {'id':'p','role':'proposed','description':'main'},
            {'id':'a','role':'ablation','description':'module removal'}]})
        self.cf=self.base/'contract.json';write_json(self.cf,self.c)
        self.d={'schema_version':1,'authorization':'User explicitly delegates bounded method revisions',
            'deadline_utc':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
            'budgets':{'training_seconds':120,'max_method_revisions':2,'max_fault_retries':2,
                       'formal_reserve_seconds':45,'step_timeout_seconds':30,'poll_seconds':1},
            'rules':{'baseline_floor':0.8,'target':0.87,'min_effect':0.01,'ci_lower_bound':0,
                     'screening_floor':0.81,'required_contributions':[{'id':'module','ablation':'a','min_effect':0.01,'ci_lower_bound':0,
                         'claim':'Synthetic fixture module improves paired per-case validation score',
                         'falsification':'The paired effect or lower bound fails its confirmed rule',
                         'boundary':'Protocol fixture only; no medical or clinical claim'}],
                     'comparisons':[]},
            'entry_dependencies':{'b':['train.py'],'p':['train.py'],'a':['train.py']},
            'codex':{'executable':sys.executable}, 'project_root':None}
        self.df=self.base/'delegation.json';write_json(self.df,self.d)
    def tearDown(self): self.tmp.cleanup()
    def runtime(self):
        from medexp import adaptive
        return adaptive
    def init(self): return self.runtime().init(self.root,self.cf,self.df,'User authorizes fixture only')
    def test_initial_delegation_and_original_science_are_frozen(self):
        a=self.init(); self.assertEqual(a['method_revisions'],0)
        self.assertEqual(a['status'],'ready');self.assertEqual(load_state(self.root)['spent_seconds'],0)
        self.assertTrue((self.root/'adaptive'/'delegation.json').exists())
        self.assertEqual((self.root/'plans'/'original.md').read_text(encoding='utf-8'),'# Approved original\n')
    def test_manual_candidate_and_resume_cannot_bypass_active_delegation(self):
        self.init();command=self.base/'command.json';write_json(command,['{python}','train.py','--seed','{seed}'])
        with self.assertRaises(GateError): engine.candidate(self.root,'manual','matrix',command,'bypass','b')
        s=load_state(self.root);s['status']='budget_exhausted';write_json(self.root/'state.json',s)
        with self.assertRaises(GateError): engine.resume(self.root,self.cf,'reset','reset')
    def test_deadline_includes_nontraining_and_expiry_is_terminal(self):
        self.init();a=read_json(self.root/'adaptive'/'state.json');a['deadline_utc']='2000-01-01T00:00:00+00:00'
        write_json(self.root/'adaptive'/'state.json',a)
        a=self.runtime().step(self.root);self.assertEqual(a['status'],'stopped');self.assertEqual(a['stop_reason'],'deadline')
    def test_pause_never_auto_resumes(self):
        self.init();self.runtime().pause(self.root,'User requests pause')
        self.assertEqual(self.runtime().step(self.root)['status'],'paused')
        self.assertEqual(self.runtime().resume(self.root,'User explicitly resumes')['status'],'ready')
    def test_proposal_cannot_mutate_frozen_definition_or_request_shell(self):
        self.init(); proposal=self.proposal();proposal['files']=[{'path':'evaluate.py','content':'# changed'}]
        with self.assertRaises(GateError):self.runtime().validate_proposal(self.root,proposal)
        proposal=self.proposal();proposal['entries'][0]['command']=['cmd.exe','/c','echo bad']
        with self.assertRaises(GateError):self.runtime().validate_proposal(self.root,proposal)
    def proposal(self):
        return {'action':'candidate','reason':'Initial bounded method','method_plan':'Detailed technical route',
                'files':[],'entries':[{'entry':e,'command':['{python}','train.py','--seed','{seed}','--score',str(v)],
                'screening_command':['{python}','train.py','--seed','{seed}','--score',str(v)]} for e,v in [('b',.85),('p',.9),('a',.84)]]}
    def test_training_ledger_deduplicates_runs_across_contract_revisions(self):
        self.init()
        for rid,secs in [('r-one',7),('r-two',11)]:
            write_json(self.root/'runs'/rid/'record.json',{'run_id':rid,'elapsed_seconds':secs,'status':'anomaly','revision':1})
        a=self.runtime().status(self.root);self.assertEqual(a['training_spent_seconds'],18)
        s=load_state(self.root);s['spent_seconds']=0;s['revision']=2;write_json(self.root/'state.json',s)
        self.assertEqual(self.runtime().status(self.root)['training_spent_seconds'],18)
    def test_formal_reserve_blocks_exploration_and_seed_runs_cannot_overspend(self):
        self.init(); a=read_json(self.root/'adaptive'/'state.json');a['training_spent_seconds']=80
        with self.assertRaises(GateError): self.runtime().admit_training(self.root,a,'screening',15)
        self.assertEqual(self.runtime().admit_training(self.root,a,'formal',60),40)
    def test_post_test_correction_requires_specific_human_gate(self):
        self.init();s=load_state(self.root);s['test_looks']=1;write_json(self.root/'state.json',s)
        with self.assertRaises(GateError):self.runtime().correct(self.root,{'reason':'bug','definition_unchanged':True,'files':[]})
        self.assertEqual(self.runtime().status(self.root)['status'],'awaiting_human')
    def test_required_module_cannot_be_deleted_to_pass(self):
        self.init(); proposal=self.proposal();proposal['entries']=proposal['entries'][:2]
        with self.assertRaises(GateError): self.runtime().validate_proposal(self.root,proposal)
    def test_reuse_checks_dependency_content_and_configuration(self):
        self.init();rt=self.runtime();cmd=self.proposal()['entries'][0]['command']
        first=rt.condition_fingerprint(self.root,'b',cmd)
        (self.root/'worktree'/'train.py').write_text('# changed model',encoding='utf-8')
        self.assertNotEqual(first,rt.condition_fingerprint(self.root,'b',cmd))
    def test_final_gate_requires_target_baseline_and_contribution(self):
        self.init();rt=self.runtime();s=load_state(self.root)
        self.assertFalse(rt.formal_gate(self.root,s)['passed'])
        s['matrix_done']={e:{'candidate_id':e,'value':v,'run_ids':[]} for e,v in [('b',.7),('p',.95),('a',.9)]}
        gate=rt.formal_gate(self.root,s);self.assertFalse(gate['passed']);self.assertIn('baseline_floor',gate['problems'])

    def fixture_candidate(self,entry,score,level='formal'):
        rt=self.runtime();p=self.proposal()
        if not read_json(self.root/'state.json')['audit']:
            with rt.internal():engine.audit(self.root)
        if not read_json(self.root/'adaptive'/'state.json')['current_proposal']:
            a=rt.status(self.root);rt.install_proposal(self.root,a,p,{'fixture':'unit-only, not real agent evidence'})
        command=self.base/('cmd-'+entry+'.json');write_json(command,['{python}','train.py','--seed','{seed}','--score',str(score)])
        with rt.internal(): cand=engine.candidate(self.root,'fixture-'+entry,'matrix',command,'deterministic unit trainer',entry)
        cand['evidence_level']=level;cand['condition_fingerprint']=rt.condition_fingerprint(self.root,entry,cand['command'])
        write_json(self.root/'candidates'/(cand['id']+'.json'),cand)
        review=self.base/'review.json';write_json(review,{'candidate_id':cand['id'],'commit':cand['commit'],
            'reviewer':'independent-subagent','agent_id':'UNIT-FIXTURE-NOT-REAL-REVIEW','verdict':'pass',
            'findings':[],'artifacts_read':['train.py'],'limitations':'unit fixture only'})
        with rt.internal():engine.review(self.root,review)
        return cand

    def fixture_run(self,cand,seed):
        rt=self.runtime()
        with rt.internal():engine.run(self.root,cand['id'],seed)
        until=time.monotonic()+15
        while time.monotonic()<until:
            state=engine.status(self.root)
            if not state['active_run']:return state
            time.sleep(.1)
        self.fail('Owned fixture worker did not finish')

    def test_real_owned_screening_run_never_completes_formal_matrix(self):
        self.init();cand=self.fixture_candidate('b',.85,'screening')
        state=self.fixture_run(cand,1)
        self.assertEqual(state['matrix_done'],{})
        rec=read_json(next((self.root/'runs').glob('*/record.json')))
        self.assertEqual(rec['status'],'completed');self.assertEqual(rec['evidence_level'],'screening')
        self.assertGreater(self.runtime().status(self.root)['training_spent_seconds'],0)

    def test_real_owned_formal_runs_enforce_three_seeds_and_case_paired_contribution(self):
        self.init()
        for entry,score in [('b',.85),('p',.9),('a',.84)]:
            cand=self.fixture_candidate(entry,score)
            for seed in [1,2,3]:state=self.fixture_run(cand,seed)
        gate=self.runtime().formal_gate(self.root,state)
        self.assertTrue(gate['passed'],gate)
        self.assertEqual(len(gate['comparisons']),2)
        self.assertEqual(state['matrix_done']['b']['seeds'],[1,2,3])
        # A changed primary effect or missing module evidence must stop convergence.
        self.assertGreater(gate['comparisons'][0]['ci']['ci_low'],.049)

    def test_evaluator_correction_cannot_modify_split_audit(self):
        self.init();p=self.proposal();p.update(action='correct_evaluator',definition_unchanged=True,
                                              files=[{'path':'audit.py','content':'# change groups'}])
        with self.assertRaises(GateError):self.runtime().validate_proposal(self.root,p,correction=True)

    def test_revision_admission_does_not_reset_spent_budget_or_retry_history(self):
        self.init();rt=self.runtime()
        with rt.internal():engine.audit(self.root)
        a=rt.status(self.root);rt.install_proposal(self.root,a,self.proposal(),{'fixture':'unit-only'})
        a['training_spent_seconds']=17;a['fault_retries']=1
        s=load_state(self.root);s['spent_seconds']=17;write_json(self.root/'state.json',s)
        p=self.proposal();p['files']=[{'path':'train.py','content':FIXTURE+'\n# revised implementation\n'}]
        rt.install_proposal(self.root,a,p,{'fixture':'unit-only'})
        self.assertEqual(load_state(self.root)['spent_seconds'],17)
        self.assertEqual(a['method_revisions'],1);self.assertEqual(a['fault_retries'],1)
        self.assertEqual(rt.status(self.root)['training_spent_seconds'],17)

    def test_unavailable_full_checkpoint_restarts_only_failed_seed_and_keeps_completed_seeds(self):
        self.init();cand=self.fixture_candidate('b',.85)
        self.fixture_run(cand,1)
        rt=self.runtime();a=rt.status(self.root)
        source=read_json(self.root/'candidates'/(cand['id']+'.json'))
        failed={'run_id':'failed-seed2','seed':2,'candidate_id':cand['id'],'entry':'b','elapsed_seconds':2,'status':'anomaly'}
        write_json(self.root/'runs'/'failed-seed2'/'record.json',failed)
        source['runs'].append('failed-seed2');write_json(self.root/'candidates'/(cand['id']+'.json'),source)
        a['recovery_source']={'candidate_id':cand['id'],'failed_run':'failed-seed2','seed':2}
        a['repair_pending']=True
        rt.install_proposal(self.root,a,self.proposal(),{'fixture':'unit-only'})
        recovered=read_json(self.root/'candidates'/(a['current_candidate']+'.json'))
        self.assertEqual(recovered['runs'],source['runs'][:1])
        self.assertEqual(recovered['recovery']['strategy'],'restart_current_seed')
        state=self.fixture_run(recovered,2)
        self.assertEqual(len(read_json(self.root/'candidates'/(recovered['id']+'.json'))['runs']),2)
        self.assertEqual(a['fault_retries'],1)

    def test_method_revision_limit_blocks_model_call_before_dispatch(self):
        self.init();rt=self.runtime();a=rt.status(self.root)
        write_json(self.root/'adaptive'/'proposals'/'exhausted.json',{'proposal':self.proposal()})
        a.update(current_proposal='exhausted',revision_pending=True,method_revisions=2)
        write_json(self.root/'adaptive'/'state.json',a)
        with rt.internal():engine.audit(self.root)
        state=rt.step(self.root)
        self.assertEqual(state['stop_reason'],'method_revision_limit')

    def test_detached_scheduler_excludes_second_instance_and_obeys_user_pause(self):
        from medexp import scheduler
        from medexp.process import is_alive
        (self.src/'train.py').write_text(FIXTURE.replace('a=p.parse_args()',"a=p.parse_args();a.mode='timeout'"),encoding='utf-8')
        self.init();rt=self.runtime();cand=self.fixture_candidate('b',.85)
        with rt.internal():engine.run(self.root,cand['id'],1)
        owner=scheduler.start(self.root)['scheduler']
        self.assertTrue(is_alive(owner['pid'],owner['token']))
        with self.assertRaises(GateError):scheduler.start(self.root)
        rt.pause(self.root,'User explicitly pauses owned task')
        until=time.monotonic()+15
        while time.monotonic()<until:
            state=engine.status(self.root)
            if not state['active_run'] and not is_alive(owner['pid'],owner['token']):break
            time.sleep(.1)
        self.assertFalse(is_alive(owner['pid'],owner['token']))
        self.assertIsNone(state['active_run'])
        self.assertEqual(rt.status(self.root)['status'],'paused')
        rt.resume(self.root,'User explicitly resumes the same owned task')
        rt.step(self.root)
        self.assertEqual(rt.status(self.root)['fault_retries'],0)
        self.assertEqual(rt.status(self.root)['method_revisions'],0)

    def test_fault_retry_limit_stops_before_repair_model_dispatch(self):
        self.init();rt=self.runtime();a=rt.status(self.root);a['fault_retries']=2
        s=load_state(self.root);s.update(status='awaiting_report',pending_incident={
            'incident_id':'preflight','run_id':None,'kind':'preflight_environment','detail':'unit bounded failure'})
        write_json(self.root/'state.json',s);write_json(self.root/'adaptive'/'state.json',a)
        self.assertEqual(rt.step(self.root)['stop_reason'],'fault_retry_limit')

    def test_stale_background_update_cannot_undo_user_pause(self):
        self.init();rt=self.runtime();a=rt.status(self.root)
        rt.pause(self.root,'User pauses during model call')
        with self.assertRaises(GateError):rt.install_proposal(self.root,a,self.proposal(),{'fixture':'unit-only'})
        self.assertEqual(rt.status(self.root)['status'],'paused')

    def paper_project(self):
        paper=self.base/'paper';(paper/'00_plan').mkdir(parents=True)
        original='# Paper\n\n## Clinical question\nFixed aim.\n\n## Methods\nOriginal confirmed complete technical route.\n\n## Evaluation\nFixed metric definition.\n'
        self.plan=paper/'00_plan'/'project-plan.md';self.plan.write_text(original,encoding='utf-8')
        (paper/'PROJECT.md').write_text('# Paper\n\n## 阶段状态\n| # | 阶段 | 状态 |\n|---|---|---|\n| 7 | Results | 已确认 |\n',encoding='utf-8')
        self.c['plan_path']=str(self.plan);write_json(self.cf,self.c)
        self.d['project_root']=str(paper);write_json(self.df,self.d)
        return paper,original

    def test_initial_runtime_projection_preserves_confirmed_full_method_body(self):
        paper,original=self.paper_project();self.init()
        body=self.plan.read_text(encoding='utf-8')
        self.assertTrue(body.startswith(original),body)
        self.assertIn('| 7 | Results | 已确认 |',(paper/'PROJECT.md').read_text(encoding='utf-8'))

    def test_actual_runtime_method_revision_marks_existing_results_for_rework(self):
        paper,original=self.paper_project();self.init();rt=self.runtime()
        with rt.internal():engine.audit(self.root)
        a=rt.status(self.root);rt.install_proposal(self.root,a,self.proposal(),{'fixture':'unit-only'})
        p=self.proposal();p['method_plan']='Replacement module and full technical route after real validation diagnosis.'
        p['files']=[{'path':'train.py','content':FIXTURE+'\n# new candidate\n'}]
        rt.install_proposal(self.root,a,p,{'fixture':'unit-only'})
        self.assertIn('| 7 | Results | 需返工 |',(paper/'PROJECT.md').read_text(encoding='utf-8'))
        self.assertIn('Replacement module and full technical route',self.plan.read_text(encoding='utf-8'))
        project_file=paper/'PROJECT.md'
        project_file.write_text(project_file.read_text(encoding='utf-8').replace('| 7 | Results | 需返工 |','| 7 | Results | 已确认 |'),encoding='utf-8')
        rt.persist(self.root,a,'ordinary_heartbeat_without_method_change')
        self.assertIn('| 7 | Results | 已确认 |',project_file.read_text(encoding='utf-8'))

    def test_runtime_next_action_identifies_audit_then_proposal(self):
        self.init();rt=self.runtime();a=rt.status(self.root);s=load_state(self.root)
        self.assertIn('audit',rt.next_action(self.root,a,s,self.c)[0])
        with rt.internal():engine.audit(self.root)
        self.assertIn('proposal',rt.next_action(self.root,a,load_state(self.root),self.c)[0])

    def test_reviewed_evaluator_correction_preserves_split_and_allows_new_formal_candidate(self):
        self.d['evaluator_implementation_paths']=['evaluate.py'];write_json(self.df,self.d)
        self.init();rt=self.runtime()
        with rt.internal():engine.audit(self.root)
        a=rt.status(self.root);s=load_state(self.root);before=s['audit']['summary']
        p=self.proposal();p.update(action='correct_evaluator',definition_unchanged=True,
            files=[{'path':'evaluate.py','content':'# implementation restored to original definition\n'}])
        rt.correct(self.root,p);a=rt.status(self.root)
        rt._apply_correction(self.root,a,{'candidate_id':'evaluator-correction','commit':__import__('medexp.project',fromlist=['commit']).commit(self.root),
             'verdict':'pass','artifacts_read':['evaluate.py'],
             'invocation':{'thread_id':'UNIT-ONLY-NOT-REAL-REVIEW','fresh_context':True}})
        self.assertEqual(load_state(self.root)['audit']['summary'],before)
        rt.install_proposal(self.root,a,self.proposal(),{'fixture':'unit-only'})

    def test_original_plan_tampering_is_blocked_before_next_agent_dispatch(self):
        self.init();(self.root/'plans'/'original.md').write_text('changed source',encoding='utf-8')
        with self.assertRaises(GateError):self.runtime().step(self.root)

    def test_audit_subprocess_is_capped_by_remaining_overall_deadline(self):
        (self.src/'audit.py').write_text('import time\ntime.sleep(5)\n'+AUDIT,encoding='utf-8')
        self.init();rt=self.runtime();a=rt.status(self.root)
        a['deadline_utc']=(datetime.now(timezone.utc)+timedelta(seconds=.3)).isoformat()
        write_json(self.root/'adaptive'/'state.json',a);started=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):rt.step(self.root)
        self.assertLess(time.monotonic()-started,2)

    def fake_agent(self,purpose,payload,block=False):
        if purpose=='proposal':return self.proposal(),{'thread_id':'UNIT-PROPOSAL','fresh_context':True}
        cand=payload['candidate']
        return {'candidate_id':cand['id'],'commit':cand['commit'],'verdict':'block' if block else 'pass',
                'findings':['UNIT: fix candidate code'] if block else [],'artifacts_read':['train.py','evaluate.py','audit.py'] if purpose=='bootstrap_review' else ['train.py'],
                'limitations':'UNIT-ONLY fake external Codex result',
                'change_kind':'fault_repair' if payload.get('pending_method_classification') else 'initial'}, {'thread_id':'UNIT-BLOCK' if block else 'UNIT-FRESH-REVIEW','fresh_context':True}

    def test_blocked_fresh_review_enters_bounded_repair_and_new_review(self):
        self.init();rt=self.runtime();cand=self.fixture_candidate('b',.85)
        cand['review']=None;write_json(self.root/'candidates'/(cand['id']+'.json'),cand)
        a=rt.status(self.root);a.update(current_candidate=cand['id'],current_entry='b',evidence_level='formal')
        write_json(self.root/'adaptive'/'state.json',a)
        with patch('medexp.agent_runner.invoke',side_effect=lambda r,d,p,q:self.fake_agent(p,q,True)):
            rt._review_candidate(self.root,a,cand)
        a=rt.status(self.root)
        self.assertTrue(a['repair_pending']);self.assertEqual(a['status'],'ready')
        blocked=read_json(self.root/'candidates'/(cand['id']+'.json'))
        self.assertEqual(blocked['review']['verdict'],'block')
        p=self.proposal();p['files']=[{'path':'train.py','content':FIXTURE+'\n# reviewed repair\n'}]
        rt.install_proposal(self.root,a,p,{'thread_id':'UNIT-REPAIR'})
        self.assertEqual(a['fault_retries'],1);self.assertEqual(a['method_revisions'],0)
        with patch('medexp.agent_runner.invoke',side_effect=lambda r,d,p,q:self.fake_agent(p,q)):
            rt.step(self.root)
        new=read_json(self.root/'candidates'/(rt.status(self.root)['current_candidate']+'.json'))
        self.assertNotEqual(new['commit'],cand['commit']);self.assertEqual(new['review']['verdict'],'pass')
        self.assertNotEqual(new['review']['agent_id'],blocked['review']['agent_id'])

    def test_valid_low_ablation_screening_promotes_to_formal_without_method_rejection(self):
        self.init();rt=self.runtime()
        for entry,score in [('b',.85),('p',.9)]:
            cand=self.fixture_candidate(entry,score)
            for seed in [1,2,3]:self.fixture_run(cand,seed)
        cand=self.fixture_candidate('a',.6,'screening');self.fixture_run(cand,1)
        a=rt.status(self.root);a.update(current_candidate=cand['id'],current_entry='a',evidence_level='screening')
        write_json(self.root/'adaptive'/'state.json',a)
        with patch('medexp.agent_runner.invoke',side_effect=lambda r,d,p,q:self.fake_agent(p,q)):
            rt.step(self.root)
        a=rt.status(self.root)
        self.assertFalse(a.get('revision_pending'));self.assertEqual(a['evidence_level'],'formal')
        self.assertNotEqual(a['current_candidate'],cand['id'])

    def test_empty_source_bootstraps_frozen_implementation_then_review_before_audit(self):
        self.c['code']={'source_root':None,'files':[]};write_json(self.cf,self.c)
        self.init();rt=self.runtime();p=self.proposal();p['files']=[{'path':n,'content':s} for n,s in [('train.py',FIXTURE),('evaluate.py','# fixed definition\n'),('audit.py',AUDIT)]]
        calls=[]
        def agent(r,d,purpose,payload):
            calls.append(purpose)
            if purpose=='proposal':return p,{'thread_id':'UNIT-BOOTSTRAP-PROPOSAL','fresh_context':True}
            return self.fake_agent(purpose,payload)
        with patch('medexp.agent_runner.invoke',side_effect=agent):
            for _ in range(3):rt.step(self.root)
        self.assertEqual(calls,['proposal','bootstrap_review'])
        self.assertTrue(load_state(self.root)['audit']['passed'])
        self.assertTrue(rt.status(self.root)['bootstrap_review']['verdict']=='pass')
        self.assertEqual(list((self.root/'runs').glob('*/record.json')),[])
        with self.assertRaises(GateError):rt.validate_proposal(self.root,p,bootstrap=True)

    def test_actual_formal_baseline_record_projects_entry_without_duplicate_key_crash(self):
        paper,_=self.paper_project();self.init();cand=self.fixture_candidate('b',.85)
        for seed in [1,2,3]:self.fixture_run(cand,seed)
        self.runtime().persist(self.root,self.runtime().status(self.root),'actual_formal_baseline_completed')
        self.assertIn('fixture-b',(paper/'01_analysis'/'README.md').read_text(encoding='utf-8'))

    def test_candidate_crash_before_adaptive_persist_adopts_orphan_without_duplicate_training(self):
        self.init();rt=self.runtime()
        with rt.internal():engine.audit(self.root)
        a=rt.status(self.root);rt.install_proposal(self.root,a,self.proposal(),{'thread_id':'UNIT'})
        command=self.base/'orphan-command.json';write_json(command,self.proposal()['entries'][0]['command'])
        with rt.internal():orphan=engine.candidate(self.root,'orphan','matrix',command,'crash before adaptive persistence','b')
        with patch('medexp.agent_runner.invoke',side_effect=lambda r,d,p,q:self.fake_agent(p,q)):
            rt.step(self.root)
        self.assertEqual(rt.status(self.root)['current_candidate'],'orphan')
        self.assertEqual(list((self.root/'runs').glob('*/record.json')),[])
        self.assertEqual(len(list((self.root/'candidates').glob('*.json'))),1)

    def test_formal_bootstrap_statistics_abort_before_expired_deadline_can_freeze(self):
        from medexp import stats
        calls=[]
        def deadline():
            calls.append(1)
            if len(calls)>1:raise GateError('deadline')
        runs=[{str(i):.8 for i in range(20)}]*3
        with self.assertRaises(GateError):
            stats.paired_bootstrap('mean_per_case',runs,runs,True,'mean',100000,.95,7,checkpoint=deadline)
        self.assertLessEqual(len(calls),3)

    def test_bootstrap_review_block_repairs_frozen_implementation_before_window_closes(self):
        self.c['code']={'source_root':None,'files':[]};write_json(self.cf,self.c)
        self.init();rt=self.runtime();proposal_count=0;review_count=0
        def agent(r,d,purpose,payload):
            nonlocal proposal_count,review_count
            if purpose=='proposal':
                proposal_count+=1;p=self.proposal();p['files']=[{'path':n,'content':s} for n,s in [('train.py',FIXTURE),('evaluate.py','# restored definition '+str(proposal_count)),('audit.py',AUDIT)]]
                return p,{'thread_id':'UNIT-BOOTSTRAP-PROPOSAL-'+str(proposal_count),'fresh_context':True}
            review_count+=1
            return self.fake_agent(purpose,payload,block=review_count==1)
        with patch('medexp.agent_runner.invoke',side_effect=agent):
            for _ in range(5):rt.step(self.root)
        a=rt.status(self.root)
        self.assertEqual(a['fault_retries'],1);self.assertEqual(a['method_revisions'],0)
        self.assertEqual(a['bootstrap_review']['verdict'],'pass');self.assertTrue(load_state(self.root)['audit']['passed'])
        self.assertEqual(len(list((self.root/'evidence'/'reviews').glob('bootstrap-code-*.json'))),2)

    def test_blocked_review_at_zero_retry_ceiling_stops_without_training(self):
        self.d['budgets']['max_fault_retries']=0;write_json(self.df,self.d)
        self.init();rt=self.runtime();cand=self.fixture_candidate('b',.85);a=rt.status(self.root)
        with patch('medexp.agent_runner.invoke',side_effect=lambda r,d,p,q:self.fake_agent(p,q,True)):
            rt._review_candidate(self.root,a,cand)
        a=rt.status(self.root)
        self.assertEqual(a['status'],'stopped');self.assertEqual(a['fault_retries'],0)
        self.assertEqual(a['stop_reason'],'fault_retry_limit_after_review_block')
        self.assertEqual(list((self.root/'runs').glob('*/record.json')),[])

    def test_adaptive_export_overrides_matrix_completeness_with_unmet_contribution_status(self):
        self.init();rt=self.runtime()
        for entry,score in [('b',.85),('p',.9),('a',.9)]:
            cand=self.fixture_candidate(entry,score)
            for seed in [1,2,3]:self.fixture_run(cand,seed)
        gate=rt.formal_gate(self.root,load_state(self.root))
        a=rt.status(self.root);a.update(status='stopped',stop_reason='method_revision_limit',
             diagnosis=gate)
        write_json(self.root/'adaptive'/'state.json',a)
        rt.export(self.root)
        report=read_json(self.root/'report.json');body=(self.root/'report.md').read_text(encoding='utf-8')
        self.assertEqual(report['acceptance_status'],'stopped')
        self.assertEqual(report['legacy_acceptance_status'],'matrix_complete')
        self.assertEqual(report['adaptive_acceptance']['formal_gate']['problems'],['module'])
        self.assertTrue(body.startswith('# 自适应委托实验报告'))
        self.assertIn('method_revision_limit',body);self.assertIn('module',body)
        self.assertIn('筛选',body);self.assertIn('失效',body)

    def formal_repair_in_reserve(self,method_cap=2):
        self.d['budgets']['max_method_revisions']=method_cap;write_json(self.df,self.d)
        self.init();rt=self.runtime();cand=self.fixture_candidate('b',.85)
        write_json(self.root/'runs'/'reserve-failed'/'record.json',{'run_id':'reserve-failed','candidate_id':cand['id'],
             'entry':'b','seed':1,'phase':'matrix','revision':1,'status':'anomaly','elapsed_seconds':80})
        saved=read_json(self.root/'candidates'/(cand['id']+'.json'));saved['runs']=['reserve-failed'];write_json(self.root/'candidates'/(cand['id']+'.json'),saved)
        a=rt.status(self.root);a.update(repair_pending=True,recovery_source={'candidate_id':cand['id'],'failed_run':'reserve-failed','seed':1})
        write_json(self.root/'adaptive'/'state.json',a)
        return rt,a

    def test_compatible_formal_fault_recovery_can_use_formal_reserve(self):
        rt,a=self.formal_repair_in_reserve()
        with patch('medexp.agent_runner.invoke',side_effect=lambda r,d,p,q:self.fake_agent(p,q)):
            rt.step(self.root)
        a=rt.status(self.root)
        self.assertEqual(a['status'],'ready');self.assertEqual(a['fault_retries'],1)
        self.assertEqual(a['method_revisions'],0);self.assertIsNotNone(a['current_candidate'])
        self.assertEqual(a['training_spent_seconds'],80)

    def test_independent_method_classification_cannot_hide_search_in_reserved_fault_recovery(self):
        rt,a=self.formal_repair_in_reserve();p=self.proposal()
        p['files']=[{'path':'train.py','content':FIXTURE+'\n# changed relevant method implementation\n'}]
        rt.install_proposal(self.root,a,p,{'thread_id':'UNIT'})
        def method_review(r,d,purpose,payload):
            out,record=self.fake_agent(purpose,payload);out['change_kind']='method_revision';return out,record
        with patch('medexp.agent_runner.invoke',side_effect=method_review):rt.step(self.root)
        a=rt.status(self.root)
        self.assertEqual(a['status'],'stopped');self.assertEqual(a['stop_reason'],'method_change_cannot_consume_formal_reserve')
        self.assertEqual(a['method_revisions'],0);self.assertEqual(a['fault_retries'],1)
        self.assertEqual(len(list((self.root/'runs').glob('*/record.json'))),1)

    def test_fresh_review_classified_code_bugfix_uses_formal_reserve_with_zero_method_slots(self):
        rt,a=self.formal_repair_in_reserve(method_cap=0);p=self.proposal()
        p['files']=[{'path':'train.py','content':FIXTURE+'\n# intended method bug restored\n'}]
        rt.install_proposal(self.root,a,p,{'thread_id':'UNIT'})
        self.assertIsNotNone(a['pending_method_classification'])
        with patch('medexp.agent_runner.invoke',side_effect=lambda r,d,p,q:self.fake_agent(p,q)):
            rt.step(self.root)
        a=rt.status(self.root);self.assertEqual(a['status'],'ready')
        self.assertEqual(a['method_revisions'],0);self.assertEqual(a['fault_retries'],1)
        self.assertIsNone(a.get('pending_method_classification'))
        cand=read_json(self.root/'candidates'/(a['current_candidate']+'.json'))
        c=engine.current_contract(self.root,load_state(self.root))
        self.assertEqual(rt.effective_run_contract(self.root,c,cand)['budget']['run_timeout_seconds'],15)

    def test_adaptive_normalizes_only_approved_absolute_python_and_records_raw_mapping(self):
        self.init();rt=self.runtime()
        with rt.internal():engine.audit(self.root)
        p=self.proposal();raw=[str(Path(self.c['environment']['python'])).replace('\\','/'),'-X','utf8','train.py','--seed','{seed}','--score','.85']
        p['entries'][0]['command']=raw[:]
        a=rt.status(self.root);rt.install_proposal(self.root,a,p,{'thread_id':'UNIT-RAW-SHAPE'})
        stored=read_json(self.root/'adaptive'/'proposals'/(a['current_proposal']+'.json'))
        self.assertEqual(stored['proposal']['entries'][0]['command'],['{python}','train.py','--seed','{seed}','--score','.85'])
        self.assertEqual(stored['agent_record']['argv_normalizations'][0]['raw_argv'],raw)
        self.assertEqual(p['entries'][0]['command'],raw)

    def test_adaptive_python_normalization_rejects_other_executable_code_flags_and_shell(self):
        self.init();rt=self.runtime()
        for prefix in [['C:/unapproved/python.exe'],[str(self.c['environment']['python']),'-c','print(1)'],
                       [str(self.c['environment']['python']),'-X','utf8','-I'],['cmd.exe','/c'],
                       ['{python}','-X','utf8'],[str(self.c['environment']['python']),'-X','utf8','-X','utf8']]:
            with self.subTest(prefix=prefix):
                p=self.proposal();p['entries'][0]['command']=prefix+['train.py','--seed','{seed}']
                with self.assertRaises(GateError):rt.validate_proposal(self.root,p)
        # The legacy manual validator keeps requiring the placeholder.
        with self.assertRaises(GateError):engine.validate_command(self.root,self.c,[str(self.c['environment']['python']),'train.py','--seed','{seed}'])

    def completed_review_fixture(self):
        self.init();rt=self.runtime();cand=self.fixture_candidate('b',.85)
        cand=read_json(self.root/'candidates'/(cand['id']+'.json'));cand['review']=None
        write_json(self.root/'candidates'/(cand['id']+'.json'),cand)
        a=rt.status(self.root);a.update(current_candidate=cand['id'],current_entry='b',evidence_level='formal',fault_retries=1,training_spent_seconds=17)
        write_json(self.root/'adaptive'/'state.json',a)
        ident='review-UNIT-COMPLETED';folder=self.root/'adaptive'/'agents'/ident
        payload=rt._agent_payload(self.root,a,'review');payload['candidate']=cand
        write_json(folder/'input.json',payload)
        out,record=self.fake_agent('review',payload)
        out['artifacts_read']+=['../adaptive/agents/'+ident+'/input.json',
            '../adaptive/proposals/'+a['current_proposal']+'.json']
        record.update(invocation_id=ident,status='completed',purpose='review',sandbox='read-only')
        record['thread_id']='00000000-0000-4000-8000-000000000001'
        record['argv']=[self.d['codex']['executable'],'exec','--ephemeral','--json','-s','read-only','-C',str(self.root/'worktree')]
        write_json(folder/'invocation.json',record);write_json(folder/'result.json',out)
        (folder/'events.jsonl').write_text(json.dumps({'type':'thread.started','thread_id':record['thread_id']})+'\n'+json.dumps({'type':'turn.completed'})+'\n',encoding='utf-8')
        return rt,cand,a,folder,out,record

    def test_adaptive_review_moves_allowlisted_study_metadata_out_of_source_list(self):
        rt,cand,a,folder,out,record=self.completed_review_fixture()
        normalized,invocation=rt.normalize_review(self.root,out,record)
        self.assertEqual(normalized['artifacts_read'],['train.py'])
        self.assertEqual(len(normalized['additional_evidence']),2)
        self.assertTrue(invocation['review_input_normalizations'])
        self.assertEqual(len(out['artifacts_read']),3)

    def test_adaptive_review_rejects_tests_raw_data_and_unknown_external_evidence(self):
        rt,cand,a,folder,out,record=self.completed_review_fixture()
        for bad in ['../tests/exposed.json','../data/raw.json',str(self.data/'patient.json')]:
            path=Path(bad) if Path(bad).is_absolute() else self.root/'worktree'/bad
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}',encoding='utf-8')
            with self.subTest(bad=bad):
                proposal=copy.deepcopy(out);proposal['artifacts_read'].append(bad)
                with self.assertRaises(GateError):rt.normalize_review(self.root,proposal,record)

    def test_adaptive_review_resolves_metadata_relative_to_initial_bound_project(self):
        (self.base/'PROJECT.md').write_text('# Bound project\n',encoding='utf-8')
        self.d['project_root']=str(self.base);write_json(self.df,self.d)
        rt,cand,a,folder,out,record=self.completed_review_fixture()
        raw=copy.deepcopy(out)
        raw['artifacts_read']=['train.py',folder.joinpath('input.json').relative_to(self.base).as_posix()]
        proposal=self.root/'adaptive'/'proposals'/(a['current_proposal']+'.json')
        raw['additional_evidence']=[proposal.relative_to(self.base).as_posix()]
        normalized,invocation=rt.normalize_review(self.root,raw,record)
        self.assertEqual(normalized['artifacts_read'],['train.py'])
        self.assertEqual(normalized['additional_evidence'],[
            folder.joinpath('input.json').relative_to(self.root).as_posix(),proposal.relative_to(self.root).as_posix()])
        self.assertEqual(len(invocation['review_input_normalizations']),2)
        self.assertEqual(raw['artifacts_read'][1],'study/adaptive/agents/review-UNIT-COMPLETED/input.json')
        self.assertEqual(read_json(folder/'result.json'),out)

    def test_project_relative_review_metadata_cannot_escape_current_study_invocation_allowlist(self):
        (self.base/'PROJECT.md').write_text('# Bound project\n',encoding='utf-8')
        self.d['project_root']=str(self.base);write_json(self.df,self.d)
        rt,cand,a,folder,out,record=self.completed_review_fixture()
        for bad in ['other-study/adaptive/agents/'+record['invocation_id']+'/input.json',
                    'tests/exposed.json','data/raw.json','study/adaptive/unknown.json',
                    'study/adaptive/agents/review-OTHER/input.json','study/runs/r-test/record.json',
                    'study/worktree/train.py']:
            path=self.base/bad
            if not path.exists():write_json(path,{'phase':'test'} if '/runs/' in bad else {})
            raw=copy.deepcopy(out);raw['additional_evidence']=[bad]
            with self.subTest(bad=bad):
                with self.assertRaises(GateError):rt.normalize_review(self.root,raw,record)

    def test_completed_real_review_reconcile_preserves_budgets_and_records_old_technical_stop(self):
        rt,cand,a,folder,out,record=self.completed_review_fixture()
        a.update(status='awaiting_human',stop_reason='GateError: 路径越出受管目录',fault_retries=1,training_spent_seconds=17)
        rt.persist(self.root,a,'scheduler_error_requires_human')
        result=rt.reconcile_review(self.root,folder/'invocation.json')
        self.assertEqual(result['status'],'ready');self.assertEqual(result['fault_retries'],1)
        self.assertEqual(result['training_spent_seconds'],17);self.assertEqual(result['deadline_utc'],a['deadline_utc'])
        self.assertEqual(result['reconciliations'][-1]['old_stop_reason'],'GateError: 路径越出受管目录')
        saved=read_json(self.root/'candidates'/(cand['id']+'.json'));self.assertEqual(saved['review']['verdict'],'pass')

    def test_completed_review_reconcile_cannot_unlock_resource_pause_test_or_changed_input(self):
        rt,cand,a,folder,out,record=self.completed_review_fixture()
        for stop in ['resource_requested','post_test_evaluator_correction_requires_specific_confirmation','independent_review_change_kind_uncertain']:
            a.update(status='awaiting_human',stop_reason=stop);write_json(self.root/'adaptive'/'state.json',a)
            with self.assertRaises(GateError):rt.reconcile_review(self.root,folder/'invocation.json')
        a.update(status='paused',stop_reason='GateError: 路径越出受管目录');write_json(self.root/'adaptive'/'state.json',a)
        with self.assertRaises(GateError):rt.reconcile_review(self.root,folder/'invocation.json')
        a.update(status='awaiting_human',stop_reason='GateError: 路径越出受管目录');write_json(self.root/'adaptive'/'state.json',a)
        rt.persist(self.root,a,'resource_requested')
        with self.assertRaises(GateError):rt.reconcile_review(self.root,folder/'invocation.json')
        rt.persist(self.root,a,'scheduler_error_requires_human')
        payload=read_json(folder/'input.json');payload['delegation']['budgets']['training_seconds']+=1;write_json(folder/'input.json',payload)
        with self.assertRaises(GateError):rt.reconcile_review(self.root,folder/'invocation.json')

    def test_json_review_style_method_plan_is_rendered_as_readable_route_with_raw_audit(self):
        self.init();rt=self.runtime()
        with rt.internal():engine.audit(self.root)
        p=self.proposal();p['method_plan']=json.dumps({'candidate_id':None,'commit':'UNIT',
             'implementation':'Convolutional model technical route.','formal_training':'All confirmed formal seeds.'})
        raw=p['method_plan'];a=rt.status(self.root);rt.install_proposal(self.root,a,p,{'thread_id':'UNIT'})
        self.assertIn('### implementation',a['method_plan']);self.assertNotIn('candidate_id',a['method_plan'])
        self.assertEqual(p['method_plan'],raw)
        stored=read_json(self.root/'adaptive'/'proposals'/(a['current_proposal']+'.json'))
        self.assertTrue(stored['agent_record']['method_plan_normalization']['raw_sha256'])

    def windows_reader_lock(self,path,release_after):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        handle=kernel.CreateFileW(str(path),0x80000000,3,None,3,0x80,None)
        self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
        def release():
            time.sleep(release_after);kernel.CloseHandle(handle)
        thread=threading.Thread(target=release);thread.start();return thread

    @unittest.skipUnless(__import__('os').name=='nt','real Windows file sharing behavior')
    def test_atomic_json_replace_retries_real_short_windows_reader_sharing_lock(self):
        path=self.base/'atomic.json';write_json(path,{'version':1})
        reader=self.windows_reader_lock(path,.15);started=time.monotonic()
        try:write_json(path,{'version':2})
        finally:reader.join()
        self.assertEqual(read_json(path),{'version':2});self.assertGreater(time.monotonic()-started,.1)
        self.assertEqual(list(self.base.glob('atomic.json.*.tmp')),[])

    @unittest.skipUnless(__import__('os').name=='nt','real Windows file sharing behavior')
    def test_atomic_json_persistent_windows_lock_is_bounded_and_retains_failed_temp(self):
        path=self.base/'persistent.json';write_json(path,{'version':1})
        reader=self.windows_reader_lock(path,2.5);started=time.monotonic()
        try:
            with self.assertRaises(PermissionError):write_json(path,{'version':2})
            self.assertLess(time.monotonic()-started,2.4)
        finally:reader.join()
        self.assertEqual(read_json(path),{'version':1})
        remaining=list(self.base.glob('persistent.json.*.tmp'));self.assertEqual(len(remaining),1)
        self.assertEqual(read_json(remaining[0]),{'version':2})

    def test_terminal_status_and_step_account_missing_real_run_segment_once_without_training(self):
        self.init();rt=self.runtime();a=rt.status(self.root)
        values=[('failed-first',8.265),('completed-resume',6.5),('failed-controller-stop',4.188)]
        for rid,elapsed in values:write_json(self.root/'runs'/rid/'record.json',{'run_id':rid,'status':'anomaly','elapsed_seconds':elapsed})
        a.update(status='awaiting_human',stop_reason='PermissionError: [WinError 5] retained',training_spent_seconds=14.765,
                 charged_runs={'failed-first':8.265,'completed-resume':6.5},fault_retries=1)
        write_json(self.root/'adaptive'/'state.json',a)
        for operation in [rt.status,rt.step,rt.status]:
            result=operation(self.root)
            self.assertEqual(result['status'],'awaiting_human');self.assertEqual(result['fault_retries'],1)
            self.assertAlmostEqual(result['training_spent_seconds'],18.953,places=9)
        self.assertEqual(len(list((self.root/'runs').glob('*/record.json'))),3)

    @unittest.skipUnless(__import__('os').name=='nt','real Windows file sharing behavior')
    def test_pause_dominates_older_persist_retry_under_real_windows_reader(self):
        import os
        self.init();rt=self.runtime();old=rt.status(self.root);state=self.root/'adaptive'/'state.json'
        reader=self.windows_reader_lock(state,.18);started=threading.Event();errors=[]
        original_replace=os.replace
        def replace(source,destination):
            if Path(destination)==state and read_json(source).get('status')=='ready':started.set()
            return original_replace(source,destination)
        def background():
            try:rt.persist(self.root,old,'UNIT older background write')
            except Exception as exc:errors.append(str(exc))
        with patch('medexp.common.os.replace',side_effect=replace):
            writer=threading.Thread(target=background);writer.start()
            self.assertTrue(started.wait(2));time.sleep(.05)
            paused=rt.pause(self.root,'UNIT latest explicit pause must survive all older writers')
            writer.join(5);reader.join()
        self.assertFalse(writer.is_alive());self.assertEqual(paused['status'],'paused')
        final=read_json(state);self.assertEqual(final['status'],'paused')
        self.assertEqual(final['pause_statement'],'UNIT latest explicit pause must survive all older writers')

if __name__=='__main__':unittest.main()
