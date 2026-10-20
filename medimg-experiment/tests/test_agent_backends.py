"""Protocol fixtures are unit evidence only, never real CLI acceptance."""
import copy
from datetime import datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from medexp import adaptive, agent_runner
from medexp.common import GateError, read_json, write_json
from tests import test_adaptive_runtime as adaptive_tests


def output():
    return {'candidate_id':'candidate-unit','commit':'unit-commit','verdict':'pass',
            'findings':[],'artifacts_read':['train.py'],'limitations':'Protocol fixture only',
            'change_kind':'initial','additional_evidence':[]}


def events(session, result=None, cwd=None):
    init={'type':'system','subtype':'init','session_id':session,'model':'unit-configured-provider-model',
          'tools':['Read','StructuredOutput']}
    if cwd is not None:init['cwd']=str(cwd)
    return [init,{'type':'result','subtype':'success','session_id':session,'is_error':False,
             'structured_output':output() if result is None else result}]


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='agent-backend-unit-')
        self.root=Path(self.tmp.name).resolve();(self.root/'worktree').mkdir()
        self.d={'agent_backend':'claude','claude':{'executable':sys.executable,'max_turns':8},
                'deadline_utc':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
                'budgets':{'step_timeout_seconds':10}}
        write_json(self.root/'adaptive'/'state.json',{'status':'ready'})
        self.environment_patch=patch.object(agent_runner,'child_environment',return_value={'PYTHONUTF8':'1'})
        self.environment_patch.start();self.addCleanup(self.environment_patch.stop)
    def tearDown(self):self.tmp.cleanup()
    def backend(self):
        self.assertTrue((ROOT/'scripts'/'medexp'/'agent_backends.py').is_file(),
                        'Native backend protocol module is required')
        return importlib.import_module('medexp.agent_backends')
    def test_selection_is_legacy_codex_without_mutation_and_claude_only_is_valid(self):
        b=self.backend();legacy={'codex':{'executable':sys.executable}};before=copy.deepcopy(legacy)
        self.assertEqual(b.validate_backend(legacy),'codex');self.assertEqual(legacy,before)
        self.assertEqual(b.validate_backend(self.d),'claude')
    def test_invalid_backend_native_path_and_turn_bound_are_rejected(self):
        b=self.backend()
        for update in [{'agent_backend':'other'},{'agent_backend':None},
                       {'claude':{'executable':'claude.exe','max_turns':8}},
                       {'claude':{'executable':sys.executable,'max_turns':True}},
                       {'claude':{'executable':sys.executable,'max_turns':0}},
                       {'claude':{'executable':sys.executable,'max_turns':101}}]:
            with self.subTest(update=update),self.assertRaises(GateError):b.validate_backend({**self.d,**update})
        script=self.root/'claude.cmd';script.write_text('@echo off',encoding='utf-8')
        with self.assertRaises(GateError):b.validate_backend({**self.d,'claude':{'executable':str(script),'max_turns':8}})
    def test_claude_protocol_requires_one_success_with_actual_matching_init(self):
        b=self.backend();session=str(uuid.uuid4());good=events(session,cwd=self.root/'worktree')
        self.assertEqual(b.parse_claude_events(good,session,agent_runner.REVIEW,self.root/'worktree'),output())
        variants=[good[1:],good[:1],good+[good[1]],list(reversed(good)),
                  [good[0],{**good[1],'session_id':str(uuid.uuid4())}],
                  [{**good[0],'session_id':str(uuid.uuid4())},good[1]],
                  [good[0],{**good[1],'is_error':True}],
                  [good[0],{**good[1],'subtype':'error_max_turns'}],
                  [good[0],{k:v for k,v in good[1].items() if k!='structured_output'}],
                  [good[0],{**good[1],'structured_output':{**output(),'verdict':'maybe'}}],
                  [good[0],{**good[1],'structured_output':{**output(),'findings':'invented'}}],
                  [good[0],{**good[1],'structured_output':{**output(),'extra':True}}]]
        variants += [[{**good[0],'tools':['Read','Bash']},good[1]],
                     [good[0],{**good[1],'is_error':0}]]
        for stream in variants:
            with self.subTest(stream=stream),self.assertRaises(GateError):
                b.parse_claude_events(stream,session,agent_runner.REVIEW,self.root/'worktree')
    def test_invocation_uses_fresh_restricted_native_argv_and_preserves_events(self):
        seen=[];root=self.root
        class Stub:
            def __init__(self,argv,cwd,env,path):
                self.argv=argv;self.closed=False;seen.append(self)
                session=argv[argv.index('--session-id')+1]
                Path(path).write_text('\n'.join(json.dumps(e) for e in events(session,cwd=cwd))+'\n',encoding='utf-8')
            def poll(self):return 0
            def close(self):self.closed=True
        with patch.object(agent_runner,'OwnedProcess',Stub):
            result,record=agent_runner.invoke(root,self.d,'review',{})
            other,second=agent_runner.invoke(root,self.d,'review',{})
        self.assertEqual(result,output());self.assertNotEqual(record['thread_id'],second['thread_id'])
        self.assertEqual(record['backend'],'claude');self.assertIsNone(record['sandbox'])
        self.assertEqual(record['model'],'unit-configured-provider-model')
        self.assertEqual(record['cwd'],str((root/'worktree').resolve()))
        self.assertEqual(record['read_only_mechanism'],'restricted CLI tools: Read,Glob,Grep; not an OS sandbox')
        argv=seen[0].argv
        self.assertEqual(argv[0],sys.executable);self.assertEqual(argv[1],'-p')
        for flag in ['--bare','--restricted','--no-session-persistence','--strict-mcp-config','--verbose']:
            self.assertIn(flag,argv)
        for flag,value in [('--tools','Read,Glob,Grep'),('--disallowedTools','mcp__*'),
                           ('--permission-mode','plan'),('--max-turns','8'),('--output-format','stream-json')]:
            self.assertEqual(argv[argv.index(flag)+1],value)
        self.assertEqual(json.loads(argv[argv.index('--mcp-config')+1]),{'mcpServers':{}})
        self.assertNotIn('--model',argv);self.assertNotIn('--resume',argv)
        folder=root/'adaptive'/'agents'/record['invocation_id']
        self.assertEqual(Path(argv[argv.index('--add-dir')+1]),folder)
        self.assertEqual(json.loads(argv[argv.index('--json-schema')+1]),read_json(folder/'schema.json'))
        self.assertEqual(read_json(folder/'schema.json')['properties']['additional_evidence']['items']['pattern'],
                         r'^adaptive/agents/[A-Za-z0-9_-]+/(input|invocation)\.json$')
        prompt=(folder/'prompt.txt').read_text(encoding='utf-8')
        self.assertIn('adaptive/agents/'+record['invocation_id']+'/input.json',prompt)
        self.assertIn('without a study-directory prefix, comments, annotations or explanations',prompt)
        self.assertEqual(argv.count('--add-dir'),1)
        self.assertEqual(read_json(folder/'result.json'),output());self.assertTrue(all(s.closed for s in seen))
    def test_invocation_rejects_missing_or_foreign_actual_init_cwd(self):
        for actual in (None,self.root,'worktree'):
            class Stub:
                def __init__(self,argv,cwd,env,path):
                    session=argv[argv.index('--session-id')+1]
                    Path(path).write_text('\n'.join(json.dumps(e) for e in events(session,cwd=actual)),encoding='utf-8')
                def poll(self):return 0
                def close(self):pass
            with self.subTest(actual=actual),patch.object(agent_runner,'OwnedProcess',Stub),self.assertRaises(GateError):
                agent_runner.invoke(self.root,self.d,'review',{})
        self.assertTrue(all(read_json(p)['status']=='failed' for p in (self.root/'adaptive'/'agents').glob('*/invocation.json')))
    def test_failed_launch_is_recorded_without_backend_fallback(self):
        with patch.object(agent_runner,'OwnedProcess',side_effect=OSError('unit launch failure')) as launch:
            with self.assertRaises(OSError):agent_runner.invoke(self.root,self.d,'review',{})
        self.assertEqual(launch.call_count,1)
        record=read_json(next((self.root/'adaptive'/'agents').glob('*/invocation.json')))
        self.assertEqual(record['status'],'failed');self.assertEqual(record['backend'],'claude')
    def test_expired_deadline_is_recorded_without_starting_process(self):
        self.d['deadline_utc']='2000-01-01T00:00:00+00:00'
        with patch.object(agent_runner,'OwnedProcess') as launch,self.assertRaises(GateError):
            agent_runner.invoke(self.root,self.d,'review',{})
        launch.assert_not_called()
        paths=list((self.root/'adaptive'/'agents').glob('*/invocation.json'))
        self.assertEqual(len(paths),1,'Expired invocation must retain a failed audit record')
        self.assertEqual(read_json(paths[0])['status'],'failed')
    def test_pause_and_timeout_close_owned_process_and_preserve_failure(self):
        seen=[]
        class Running:
            def __init__(self,*args):self.closed=False;seen.append(self)
            def poll(self):return None
            def close(self):self.closed=True
        write_json(self.root/'adaptive'/'state.json',{'status':'paused'})
        with patch.object(agent_runner,'OwnedProcess',Running),self.assertRaises(GateError):
            agent_runner.invoke(self.root,self.d,'review',{})
        write_json(self.root/'adaptive'/'state.json',{'status':'ready'})
        self.d['budgets']['step_timeout_seconds']=1e-9
        with patch.object(agent_runner,'OwnedProcess',Running),self.assertRaises(GateError):
            agent_runner.invoke(self.root,self.d,'review',{})
        self.assertTrue(all(s.closed for s in seen))
        self.assertTrue(all(read_json(p)['status']=='failed' for p in (self.root/'adaptive'/'agents').glob('*/invocation.json')))
    def test_replay_binds_backend_exact_argv_and_event_output(self):
        b=self.backend();folder=self.root/'adaptive'/'agents'/'review-unit';folder.mkdir(parents=True)
        session=str(uuid.uuid4());argv=b.build_argv(self.root,self.d,folder,'<saved prompt.txt>',agent_runner.REVIEW,session)
        record={'backend':'claude','argv':argv,'thread_id':session,'requested_session_id':session,
                'sandbox':None,'read_only_mechanism':b.READ_ONLY_TOOLS,
                'cwd':str(self.root/'worktree'),
                'model':events(session)[0]['model'],'actual_tools':events(session)[0]['tools']}
        write_json(folder/'result.json',output())
        (folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events(session,cwd=self.root/'worktree')),encoding='utf-8')
        self.assertEqual(b.verify_replay(self.root,self.d,folder,record,agent_runner.REVIEW),output())
        for changed in [{**record,'backend':'codex'},{**record,'argv':argv+['--dangerously-skip-permissions']},
                        {**record,'requested_session_id':str(uuid.uuid4())},
                        {**record,'cwd':str(self.root)},
                        {k:v for k,v in record.items() if k!='cwd'}]:
            with self.subTest(changed=changed),self.assertRaises(GateError):
                b.verify_replay(self.root,self.d,folder,changed,agent_runner.REVIEW)
        other={**self.d,'agent_backend':'codex','codex':{'executable':sys.executable}}
        with self.assertRaises(GateError):b.verify_replay(self.root,other,folder,record,agent_runner.REVIEW)
        write_json(folder/'result.json',{**output(),'limitations':'tampered result'})
        with self.assertRaises(GateError):b.verify_replay(self.root,self.d,folder,record,agent_runner.REVIEW)
        described={**output(),'additional_evidence':['adaptive/agents/review-unit/input.json (invocation record: contract)']}
        write_json(folder/'result.json',described)
        (folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events(session,described,self.root/'worktree')),encoding='utf-8')
        with self.assertRaises(GateError):b.verify_replay(self.root,self.d,folder,record,agent_runner.REVIEW)
    def test_replay_rejects_missing_or_foreign_actual_init_cwd(self):
        b=self.backend();folder=self.root/'adaptive'/'agents'/'review-unit';folder.mkdir(parents=True)
        session=str(uuid.uuid4());init=events(session,cwd=self.root/'worktree')[0]
        record={'backend':'claude','argv':b.build_argv(self.root,self.d,folder,'<saved prompt.txt>',agent_runner.REVIEW,session),
                'thread_id':session,'requested_session_id':session,'sandbox':None,'read_only_mechanism':b.READ_ONLY_TOOLS,
                'cwd':str(self.root/'worktree'),'model':init['model'],'actual_tools':init['tools']}
        write_json(folder/'result.json',output())
        for actual in (None,self.root,'worktree'):
            (folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events(session,cwd=actual)),encoding='utf-8')
            with self.subTest(actual=actual),self.assertRaises(GateError):
                b.verify_replay(self.root,self.d,folder,record,agent_runner.REVIEW)
    def test_legacy_codex_argv_is_preserved(self):
        b=self.backend();d={'codex':{'executable':sys.executable}};folder=self.root/'invocation'
        argv=b.build_argv(self.root,d,folder,'unit-prompt',agent_runner.REVIEW)
        self.assertEqual(argv,[sys.executable,'exec','--ephemeral','--json','--color','never',
                              '-s','read-only','-C',str(self.root/'worktree'),
                              '--output-schema',str(folder/'schema.json'),'-o',str(folder/'result.json'),'unit-prompt'])
    def test_claude_review_metadata_pattern_rejects_description_and_other_scopes(self):
        b=self.backend();schema=copy.deepcopy(agent_runner.REVIEW)
        schema['properties']['additional_evidence']=copy.deepcopy(schema['properties']['additional_evidence'])
        schema['properties']['additional_evidence']['items']['pattern']=r'^adaptive/agents/[A-Za-z0-9_-]+/(input|invocation)\.json$'
        canonical='adaptive/agents/review-unit/input.json'
        self.assertEqual(b.validate_output({**output(),'additional_evidence':[canonical]},schema)['additional_evidence'],[canonical])
        self.assertEqual(b.validate_output({**output(),'additional_evidence':[canonical.replace('input.json','invocation.json')]},schema)['verdict'],'pass')
        invalid=[canonical+' (invocation record: contract, original_plan, ...)',
                 'live-study/'+canonical,'adaptive/proposals/proposal-unit.json','runs/run-unit/record.json',
                 '../'+canonical,str(self.root/'adaptive'/'agents'/'review-unit'/'input.json'),
                 'adaptive/agents/review-unit/../../input.json']
        for value in invalid:
            with self.subTest(value=value),self.assertRaises(GateError):
                b.validate_output({**output(),'additional_evidence':[value]},schema)
        session=str(uuid.uuid4())
        with self.assertRaises(GateError):
            b.parse_claude_events(events(session,{**output(),'additional_evidence':[invalid[0]]},self.root/'worktree'),
                                  session,agent_runner.REVIEW,self.root/'worktree')
    def test_provider_schema_is_claude_review_only_and_keeps_codex_schema_unchanged(self):
        b=self.backend();before=copy.deepcopy(agent_runner.REVIEW);proposal=copy.deepcopy(agent_runner.PROPOSAL)
        schema=b.provider_schema('claude',agent_runner.REVIEW)
        self.assertIsNot(schema,agent_runner.REVIEW)
        self.assertEqual(schema['properties']['additional_evidence']['items']['pattern'],
                         r'^adaptive/agents/[A-Za-z0-9_-]+/(input|invocation)\.json$')
        self.assertEqual(schema['properties']['artifacts_read'],before['properties']['artifacts_read'])
        self.assertEqual(schema['properties']['candidate_id'],before['properties']['candidate_id'])
        self.assertEqual(b.provider_schema('codex',agent_runner.REVIEW),before)
        self.assertEqual(b.provider_schema('claude',agent_runner.PROPOSAL),proposal)
        self.assertEqual(agent_runner.REVIEW,before);self.assertEqual(agent_runner.PROPOSAL,proposal)
    def test_child_environment_reads_only_connection_fields_and_rejects_invalid_settings(self):
        b=self.backend();settings=self.root/'settings.json'
        secret='UNIT-SECRET-NOT-A-CREDENTIAL'
        write_json(settings,{'env':{'ANTHROPIC_AUTH_TOKEN':secret,'ANTHROPIC_MODEL':'unit-model',
                                  'PATH':'untrusted','BASH_ENV':'untrusted'},'hooks':{'arbitrary':'ignored'}})
        parent={'ANTHROPIC_AUTH_TOKEN':'stale','PATH':'original'}
        env=b.child_environment(self.d,parent,settings)
        self.assertEqual(env['ANTHROPIC_AUTH_TOKEN'],secret);self.assertEqual(env['PATH'],'original')
        self.assertNotIn('BASH_ENV',env);self.assertEqual(parent['ANTHROPIC_AUTH_TOKEN'],'stale')
        self.assertEqual(b.child_environment({'codex':{}},parent,settings)['ANTHROPIC_AUTH_TOKEN'],'stale')
        for malformed in ['bad-json','[]','{"env": []}','{"env":{"ANTHROPIC_MODEL":42}}']:
            settings.write_text(malformed,encoding='utf-8')
            with self.subTest(malformed=malformed),self.assertRaises(GateError):b.child_environment(self.d,parent,settings)
        settings.unlink();self.assertEqual(b.child_environment(self.d,parent,settings)['ANTHROPIC_AUTH_TOKEN'],'stale')
        settings.write_text('\ufeff'+json.dumps({'env':{'ANTHROPIC_MODEL':'bom-model'}}),encoding='utf-8')
        self.assertEqual(b.child_environment(self.d,{'CLAUDE_CONFIG_DIR':str(self.root)})['ANTHROPIC_MODEL'],'bom-model')
        with patch.dict(b.os.environ,{'MEDEXP_BLOCKED_ROOTS':str(self.root)}),self.assertRaises(GateError):
            b.child_environment(self.d,parent,settings)
    def test_connection_secret_never_enters_invocation_record_or_argv(self):
        b=self.backend();secret='UNIT-CONNECTION-SECRET';settings=self.root/'settings.json'
        write_json(settings,{'env':{'ANTHROPIC_AUTH_TOKEN':secret,'ANTHROPIC_MODEL':'unit-configured'}})
        seen=[]
        class Stub:
            def __init__(self,argv,cwd,env,path):
                seen.append((argv,env));session=argv[argv.index('--session-id')+1]
                Path(path).write_text('\n'.join(json.dumps(e) for e in events(session,cwd=cwd)),encoding='utf-8')
            def poll(self):return 0
            def close(self):pass
        with patch.object(agent_runner,'child_environment',side_effect=lambda d:b.child_environment(d,{},settings)),patch.object(agent_runner,'OwnedProcess',Stub):
            result,record=agent_runner.invoke(self.root,self.d,'review',{})
        self.assertEqual(seen[0][1]['ANTHROPIC_AUTH_TOKEN'],secret)
        self.assertNotIn(secret,json.dumps(record));self.assertNotIn(secret,json.dumps(seen[0][0]))


class DelegationTests(unittest.TestCase):
    # Use the existing synthetic contract setup, with only the selected new gate.
    setUp=adaptive_tests.AdaptiveTests.setUp
    tearDown=adaptive_tests.AdaptiveTests.tearDown
    runtime=adaptive_tests.AdaptiveTests.runtime
    def test_claude_only_delegation_does_not_require_inactive_codex(self):
        self.d.pop('codex');self.d.update(agent_backend='claude',claude={'executable':sys.executable,'max_turns':8})
        before=copy.deepcopy(self.d)
        self.runtime().validate_delegation(self.c,self.d)
        self.assertEqual(self.d,before)


class ReconcileTests(unittest.TestCase):
    setUp=adaptive_tests.AdaptiveTests.setUp
    tearDown=adaptive_tests.AdaptiveTests.tearDown
    runtime=adaptive_tests.AdaptiveTests.runtime
    init=adaptive_tests.AdaptiveTests.init
    proposal=adaptive_tests.AdaptiveTests.proposal
    fixture_candidate=adaptive_tests.AdaptiveTests.fixture_candidate
    fake_agent=adaptive_tests.AdaptiveTests.fake_agent
    completed_review_fixture=adaptive_tests.AdaptiveTests.completed_review_fixture
    def fixture(self):
        self.d.update(agent_backend='claude',claude={'executable':sys.executable,'max_turns':8})
        write_json(self.df,self.d)
        rt,cand,a,folder,out,record=self.completed_review_fixture()
        from medexp import agent_backends as b
        record.update(backend='claude',sandbox=None,read_only_mechanism=b.READ_ONLY_TOOLS,
                      cwd=str((self.root/'worktree').resolve()),
                      requested_session_id=record['thread_id'],model=events(record['thread_id'])[0]['model'],
                      actual_tools=events(record['thread_id'])[0]['tools'])
        record['argv']=b.build_argv(self.root,self.d,folder,'<saved prompt.txt>',agent_runner.REVIEW,record['thread_id'])
        out['additional_evidence']=[]
        write_json(folder/'invocation.json',record);write_json(folder/'result.json',out)
        (folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events(record['thread_id'],out,self.root/'worktree')),encoding='utf-8')
        a.update(status='awaiting_human',stop_reason='GateError: 路径越出受管目录')
        rt.persist(self.root,a,'scheduler_error_requires_human')
        return rt,cand,a,folder,record
    def test_completed_claude_review_reconciles_with_selected_label_and_unchanged_budget(self):
        rt,cand,a,folder,record=self.fixture()
        result=rt.reconcile_review(self.root,folder/'invocation.json')
        self.assertEqual(result['training_spent_seconds'],17);self.assertEqual(result['fault_retries'],1)
        self.assertEqual(result['deadline_utc'],a['deadline_utc'])
        saved=read_json(self.root/'candidates'/(cand['id']+'.json'))
        self.assertEqual(saved['review']['reviewer'],'claude-independent')
    def test_live_review_and_correction_cannot_relabel_codex_as_claude(self):
        rt,cand,a,folder,record=self.fixture()
        out=read_json(folder/'result.json')
        for purpose in ('review','correction_review','bootstrap_review'):
            with self.subTest(purpose=purpose),self.assertRaises(GateError):
                rt._verify_review_invocation(self.root,out,{**record,'backend':'codex'},purpose)
    def test_claude_reconcile_rejects_foreign_events_or_changed_frozen_input(self):
        rt,cand,a,folder,record=self.fixture()
        original=(folder/'events.jsonl').read_text(encoding='utf-8')
        (folder/'events.jsonl').write_text(original.replace(record['thread_id'],str(uuid.uuid4())),encoding='utf-8')
        with self.assertRaises(GateError):rt.reconcile_review(self.root,folder/'invocation.json')
        (folder/'events.jsonl').write_text(original,encoding='utf-8')
        payload=read_json(folder/'input.json');payload['delegation']['budgets']['training_seconds']+=1
        write_json(folder/'input.json',payload)
        with self.assertRaises(GateError):rt.reconcile_review(self.root,folder/'invocation.json')


class RepairEvidenceTests(unittest.TestCase):
    """Only isolated source snapshots; never CLI inference or model training."""
    setUp=adaptive_tests.AdaptiveTests.setUp
    tearDown=adaptive_tests.AdaptiveTests.tearDown
    runtime=adaptive_tests.AdaptiveTests.runtime
    init=adaptive_tests.AdaptiveTests.init
    proposal=adaptive_tests.AdaptiveTests.proposal
    fixture_candidate=adaptive_tests.AdaptiveTests.fixture_candidate
    formal_repair_in_reserve=adaptive_tests.AdaptiveTests.formal_repair_in_reserve
    def repair_fixture(self,backend='claude',change_source=True):
        if backend=='claude':self.d.update(agent_backend='claude',claude={'executable':sys.executable,'max_turns':8})
        rt,a=self.formal_repair_in_reserve(method_cap=0)
        prior_id=a['current_proposal'];prior=read_json(self.root/'adaptive'/'proposals'/(prior_id+'.json'))
        p=self.proposal();p.update(reason='A proposer assertion is not source evidence',
                                  files=[{'path':'train.py','content':adaptive_tests.FIXTURE+'\n# actual source repair marker\n'}])
        if not change_source:p.update(files=[],method_plan=p['method_plan']+' Updated plan only.')
        rt.install_proposal(self.root,a,p,{'thread_id':'UNIT-ONLY'})
        return rt,a,prior_id,prior
    def test_claude_fault_classification_input_contains_actual_git_diff_and_prior_proposal(self):
        rt,a,prior_id,prior=self.repair_fixture()
        payload=rt._agent_payload(self.root,a,'review')
        evidence=payload.get('method_classification_evidence')
        self.assertIsInstance(evidence,dict,'Restricted reviewer needs controller-supplied prior source evidence')
        pending=a['pending_method_classification']
        self.assertEqual(evidence['prior_commit'],pending['prior_commit'])
        self.assertEqual(evidence['proposed_commit'],payload['current_commit'])
        self.assertEqual(evidence['prior_proposal_id'],prior_id)
        self.assertEqual(evidence['prior_proposal'],prior['proposal'])
        self.assertEqual(evidence['changed_paths'],['train.py'])
        self.assertIn('diff --git a/train.py b/train.py',evidence['source_diff'])
        self.assertIn('+# actual source repair marker',evidence['source_diff'])
        self.assertEqual(a['method_revisions'],0);self.assertEqual(a['training_spent_seconds'],80)
    def test_fault_classification_evidence_rejects_stale_commit_or_missing_prior_proposal(self):
        rt,a,prior_id,prior=self.repair_fixture()
        for field,value in [('proposed_commit',prior['commit']),('prior_proposal','missing-unit-proposal')]:
            changed=copy.deepcopy(a);changed['pending_method_classification'][field]=value
            with self.subTest(field=field),self.assertRaises((GateError,FileNotFoundError)):
                rt._agent_payload(self.root,changed,'review')
    def test_fault_classification_evidence_rejects_dirty_current_source(self):
        rt,a,prior_id,prior=self.repair_fixture()
        with (self.root/'worktree'/'train.py').open('a',encoding='utf-8') as handle:handle.write('\n# uncommitted source\n')
        with self.assertRaises(GateError):rt._agent_payload(self.root,a,'review')
    def test_legacy_codex_pending_review_payload_does_not_gain_claude_evidence(self):
        rt,a,prior_id,prior=self.repair_fixture(backend='codex')
        self.assertNotIn('method_classification_evidence',rt._agent_payload(self.root,a,'review'))
    def test_plan_only_repair_has_bound_proposals_and_honest_empty_source_diff(self):
        rt,a,prior_id,prior=self.repair_fixture(change_source=False)
        evidence=rt._agent_payload(self.root,a,'review')['method_classification_evidence']
        self.assertEqual(evidence['changed_paths'],[]);self.assertEqual(evidence['source_diff'],'')
        self.assertEqual(evidence['prior_proposal'],prior['proposal'])
    def test_fault_classification_never_embeds_undeclared_changed_metadata(self):
        rt,a,prior_id,prior=self.repair_fixture()
        from medexp import project
        (self.root/'worktree'/'undeclared-metadata.txt').write_text('Unit-only excluded text',encoding='utf-8')
        project.git(self.root/'worktree','add','undeclared-metadata.txt')
        project.git(self.root/'worktree','commit','-m','Unit-only negative scope fixture')
        a['pending_method_classification']['proposed_commit']=project.commit(self.root)
        with self.assertRaisesRegex(GateError,'批准源码范围'):rt._agent_payload(self.root,a,'review')


if __name__=='__main__':unittest.main()
