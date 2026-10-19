import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from medexp import projection
from medexp.common import GateError


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / 'paper'
        self.study = self.project / '01_analysis' / 'trial'
        (self.study / 'plans').mkdir(parents=True)
        (self.study / 'runs' / 'old').mkdir(parents=True)
        self.raw = self.study / 'runs' / 'old' / 'weights.pt'
        self.raw.write_bytes(b'old evidence must stay at original path')
        (self.project / '00_plan').mkdir()
        self.plan = self.project / '00_plan' / 'project-plan.md'
        self.original = '# Paper\n\n## Clinical question\nFixed question.\n\n## Methods\nOld module.\n\n## Evaluation\nFixed metric.\n'
        self.plan.write_text(self.original, encoding='utf-8')
        (self.study / 'plans' / 'original.md').write_text(self.original, encoding='utf-8')
        (self.project / '01_analysis' / 'README.md').write_text('# Analysis\n\nAn unrelated source must survive.\n', encoding='utf-8')
        (self.project / 'PROJECT.md').write_text('# Paper\n\n## 阶段状态\n| # | 阶段 | 状态 |\n|---|---|---|\n| 7 | Results | 已确认 |\n\n## 目录说明\nExisting directory note.\n\n## 变更记录\n', encoding='utf-8')
        self.snapshot = {
            'event_id': 'event-001', 'method_revision': 2, 'status': 'screening',
            'stage': 'development', 'current_method': 'New method',
            'method_plan': 'New module and revised training route; still to be tested.',
            'diagnosis': 'The old module failed its contribution rule.',
            'next_steps': ['Review new code', 'Run controlled training'],
            'latest_attempt': {'candidate': 'm2', 'state': 'unverified'},
            'valid_results': [{'candidate': 'baseline', 'source_revision': 1}],
            'final_selection': None, 'budgets': {'training_seconds_used': 12},
            'test_state': {'exposed': False}, 'affected_stages': ['Results']}

    def tearDown(self):
        self.tmp.cleanup()

    def test_revised_experiment_invalidates_existing_submission_without_rewriting_materials(self):
        project=self.project/'PROJECT.md'
        project.write_text(project.read_text(encoding='utf-8').replace(
            '| 7 | Results | 已确认 |', '| 7 | Results | 已确认 |\n| 13 | 期刊适配与投稿材料准备 | 已确认 |'),encoding='utf-8')
        material=self.project/'06_submission'/'journal'/'v1'/'author-page.md'
        material.parent.mkdir(parents=True);material.write_text('Approved author material remains untouched.',encoding='utf-8')
        self.snapshot['affected_stages'].append('期刊适配与投稿材料准备')
        projection.sync_project(self.study,self.snapshot)
        self.assertIn('| 13 | 期刊适配与投稿材料准备 | 需返工 |',project.read_text(encoding='utf-8'))
        self.assertEqual(material.read_text(encoding='utf-8'),'Approved author material remains untouched.')

    def test_updates_actual_method_and_preserves_fixed_sections_and_raw_runs(self):
        result = projection.sync_project(self.study, self.snapshot)
        self.assertTrue(result['synced'])
        body = self.plan.read_text(encoding='utf-8')
        self.assertIn('New module and revised training route', body)
        # Replaying an old receipt after a newer legitimate event checks the
        # latest projection, rather than mistaking that event for an edit.
        self.assertTrue(projection.sync_project(self.study,self.snapshot)['replayed'])
        self.assertIn('Old module.', body)  # explicitly historical, never an active route
        self.assertIn('初始确认参考，已被当前方案取代', body)
        self.assertIn('Fixed question.', body)
        self.assertIn('Fixed metric.', body)
        archived = list((self.project / '_archive').glob('*/00_plan/project-plan.md'))
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0].read_text(encoding='utf-8'), self.original)
        self.assertEqual(self.raw.read_bytes(), b'old evidence must stay at original path')
        self.assertIn('An unrelated source must survive.', (self.project/'01_analysis'/'README.md').read_text(encoding='utf-8'))
        project = (self.project/'PROJECT.md').read_text(encoding='utf-8')
        self.assertIn('| 7 | Results | 需返工 |', project)
        self.assertNotIn('| 实验 |', project)

    def test_idempotent_event_and_conflicting_replay(self):
        first = projection.sync_project(self.study, self.snapshot)
        second = projection.sync_project(self.study, self.snapshot)
        self.assertEqual(first['receipt'], second['receipt'])
        reordered = dict(reversed(list(self.snapshot.items())))
        self.assertTrue(projection.sync_project(self.study, reordered)['replayed'])
        self.assertEqual(len(list((self.project/'_archive').glob('*/00_plan/project-plan.md'))), 1)
        changed = copy.deepcopy(self.snapshot)
        changed['status'] = 'accepted'
        with self.assertRaises(GateError):
            projection.sync_project(self.study, changed)

    def test_same_day_updates_archive_uniquely_and_keep_valid_result(self):
        projection.sync_project(self.study, self.snapshot)
        second = copy.deepcopy(self.snapshot)
        second.update(event_id='event-002', status='rejected', method_plan=None)
        second['latest_attempt'] = {'candidate': 'm2', 'state': 'failed'}
        projection.sync_project(self.study, second)
        self.assertEqual(len(list((self.project/'_archive').glob('*/00_plan/project-plan.md'))), 2)
        body = self.plan.read_text(encoding='utf-8')
        self.assertIn('baseline', body)
        self.assertIn('failed', body)
        self.assertIn('New module and revised training route', body)

    def test_standalone_does_not_create_paper_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'study'
            root.mkdir()
            result = projection.sync_project(root, self.snapshot)
            self.assertFalse(result['synced'])
            self.assertFalse((root/'PROJECT.md').exists())

    def test_full_plan_replacement_is_not_just_appended_log(self):
        update = copy.deepcopy(self.snapshot)
        update['plan_markdown'] = '# Revised paper plan\n\n## Methods\nWhole new coherent route.\n\n## Clinical question\nFixed question.\n\n## Evaluation\nFixed metric.\n'
        projection.sync_project(self.study, update)
        text = self.plan.read_text(encoding='utf-8')
        self.assertIn('Whole new coherent route.', text)
        self.assertNotIn('Old module.', text)

    def test_prepared_transaction_can_recover_after_partial_write(self):
        from unittest.mock import patch
        actual = projection._atomic_text
        calls = []
        def crash_once(path, body):
            calls.append(str(path))
            if len(calls) == 2:
                raise OSError('injected projection interruption')
            return actual(path, body)
        with patch.object(projection, '_atomic_text', side_effect=crash_once):
            with self.assertRaises(OSError):
                projection.sync_project(self.study, self.snapshot)
        result = projection.sync_project(self.study, self.snapshot)
        self.assertTrue(result['synced'])
        self.assertEqual(len(list((self.project/'_archive').glob('*/00_plan/project-plan.md'))), 1)
        self.assertIn('New method', self.plan.read_text(encoding='utf-8'))

    def test_applied_replay_checks_current_files_and_archives(self):
        result = projection.sync_project(self.study, self.snapshot)
        archive = Path(result['archives'][0])
        saved = archive.read_bytes()
        archive.write_bytes(b'archive damaged')
        with self.assertRaises(GateError):
            projection.sync_project(self.study, self.snapshot)
        archive.write_bytes(saved)
        self.plan.write_text('external edit must not be silently accepted', encoding='utf-8')
        with self.assertRaises(GateError):
            projection.sync_project(self.study, self.snapshot)

    def test_prepared_resume_never_skips_missing_archive_for_already_published_file(self):
        from unittest.mock import patch
        actual = projection._atomic_text
        calls = []
        def interrupted(path, body):
            calls.append(path)
            if len(calls) == 2:
                raise OSError('interrupted')
            actual(path, body)
        with patch.object(projection, '_atomic_text', side_effect=interrupted):
            with self.assertRaises(OSError):
                projection.sync_project(self.study, self.snapshot)
        for path in (self.project/'_archive').glob('*/00_plan/project-plan.md'):
            path.unlink()  # deliberate fault injection only in this temp fixture
        with self.assertRaises(GateError):
            projection.sync_project(self.study, self.snapshot)

    def test_current_route_design_and_next_tasks_replace_outdated_active_sections(self):
        self.plan.write_text(self.original+'\n## 4. 实验或分析设计与成本\nRun the old module study.\n'
                             '\n## 8. 交叉一致性与冲突裁决\nOld claim is established.\n'
                             '\n## 9. 面向 agent 的工程实施计划\nNEXT: train old module.\n',encoding='utf-8')
        snap=copy.deepcopy(self.snapshot)
        snap['confirmed_contract']={'matrix':{'reference':'baseline','entries':[{'id':'main','role':'proposed','description':'Current contribution'}]},
                                   'task':'classification','primary_metric':{'name':'accuracy'},'verification':{'seeds':[1,2,3]}}
        snap['confirmed_rules']={'required_contributions':[{'id':'required-module','min_effect':0.02}]}
        snap['current_commands']=[{'entry':'main','command':['{python}','train.py']}]
        projection.sync_project(self.study,snap)
        text=self.plan.read_text(encoding='utf-8')
        self.assertIn('required-module',text)
        self.assertIn('当前实验设计与固定验收',text)
        self.assertIn('当前工程任务与停止条件',text)
        # Former commands are retained solely in explicitly superseded history.
        import re
        active=re.sub(r'<details>.*?</details>','',text,flags=re.S)
        self.assertNotIn('NEXT: train old module.',active)
        self.assertNotIn('Old claim is established.',active)

    def test_nested_model_headings_do_not_leave_stale_active_method_after_revision(self):
        import re
        first=copy.deepcopy(self.snapshot)
        first['method_plan']='## Network\nMethod B.\n## Training\nOld B training.'
        projection.sync_project(self.study,first)
        second=copy.deepcopy(first)
        second.update(event_id='second-method',method_plan='# Network\nMethod C.\n## Training\nNew C training.')
        projection.sync_project(self.study,second)
        text=self.plan.read_text(encoding='utf-8')
        active=re.sub(r'<details>.*?</details>','',text,flags=re.S)
        self.assertNotIn('Old B training.',active)
        self.assertIn('New C training.',active)
        self.assertEqual(text.count('<!-- medexp:history:route:begin -->'),1)

    def test_structured_method_narrative_becomes_readable_markdown(self):
        snap=copy.deepcopy(self.snapshot)
        snap['method_plan']=json.dumps({'commit':'recorded elsewhere','implementation':'Use the current network.',
                                        'formal_training':'Three unchanged seeds.','recovery':'Resume only verified full state.'})
        before=copy.deepcopy(snap)
        projection.sync_project(self.study,snap)
        body=self.plan.read_text(encoding='utf-8')
        self.assertIn('### 当前方法与技术路线\n\nUse the current network.',body)
        self.assertIn('### 正式训练\n\nThree unchanged seeds.',body)
        self.assertEqual(snap,before)


if __name__ == '__main__':
    unittest.main()
