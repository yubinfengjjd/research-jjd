"""Matrix-mode controller tests (fixture trainer, no real models)."""
import json
import time
import unittest

from tests import test_controller as base


class MatrixTests(base.ControllerTests):
    def setUp(self):
        super().setUp()
        self.c.update(mode='matrix', stages=['matrix'])
        self.c['matrix'] = {'reference': 'b', 'entries': [{'id': 'b', 'role': 'baseline', 'description': 'baseline'},
                                                          {'id': 'p', 'role': 'proposed', 'description': 'proposed'},
                                                          {'id': 'a', 'role': 'ablation', 'description': 'ablation'}]}
        for k in ('target', 'min_effect'):
            self.c['primary_metric'].pop(k)
        self.c['budget'] = {'total_seconds': 300, 'run_timeout_seconds': 15}
        self.c['verification']['ci'].pop('lower_bound_rule')
        self.save_contract()

    def entry(self, ident, entry, score):
        command = self.base/f'{ident}-command.json'
        command.write_text(json.dumps(['{python}', 'train.py', '--seed', '{seed}', '--score', str(score)]), encoding='utf-8')
        r = self.call('candidate', '--root', self.study, '--id', ident, '--phase', 'matrix', '--command', command,
                      '--description', 'fixture', '--entry', entry)
        review = self.base/f'{ident}-review.json'
        review.write_text(json.dumps({'candidate_id': ident, 'commit': r['commit'], 'verdict': 'pass', 'reviewer': 'independent-subagent',
                                      'agent_id': 'fixture', 'findings': [], 'artifacts_read': ['train.py']}), encoding='utf-8')
        self.call('review', '--root', self.study, '--record', review)
        for s in (1, 2, 3):
            r = self.run_candidate(ident, s)
        return r

    def test_matrix_runs_all_entries_reports_ci_and_worse_ablation_is_not_an_incident(self):
        self.init()
        self.assertEqual(self.entry('cb', 'b', .85)['status'], 'ready')
        self.call('candidate', '--root', self.study, '--id', 'dup', '--phase', 'matrix', '--command',
                  self.base/'cb-command.json', '--description', 'x', '--entry', 'b', ok=False)
        self.entry('cp', 'p', .90)
        r = self.entry('ca', 'a', .82)
        self.assertEqual(r['status'], 'matrix_complete', r.get('pending_incident'))
        self.call('export', '--root', self.study)
        rep = json.loads((self.study/'report.json').read_text(encoding='utf-8'))
        rows = {m['entry']: m for m in rep['matrix']}
        self.assertGreater(rows['p']['ci_vs_reference']['ci_low'], 0)
        self.assertLess(rows['a']['ci_vs_reference']['ci_high'], 0)

    def test_resume_carries_unchanged_entries_only(self):
        self.init(); self.entry('cb', 'b', .85); self.entry('cp', 'p', .90); self.entry('ca', 'a', .82)
        self.c['matrix']['entries'][2]['description'] = 'ablation v2'
        self.c['matrix']['entries'].append({'id': 'n', 'role': 'comparison', 'description': 'new neighbour'})
        self.save_contract()
        r = self.call('resume', '--root', self.study, '--contract', self.cf, '--direction', '修改消融并加近邻对比', '--statement', '用户确认')
        self.assertEqual(sorted(r['matrix_done']), ['b', 'p'])
        self.assertEqual(r['matrix_done']['b']['carried_from_revision'], 1)
        self.assertEqual(r['status'], 'ready')

    def test_matrix_test_requires_completion(self):
        (self.source/'test_eval.py').write_text(base.TEST_EVAL, encoding='utf-8')
        self.c['code']['files'].append('test_eval.py'); self.c['scope']['frozen_paths'].append('test_eval.py')
        self.c['split_audit']['command'] = ['{python}', 'audit.py', '{output}', 'with-test']
        self.c['test'] = {'policy': 'locked', 'reference': 'fixture', 'command': ['{python}', 'test_eval.py', '{run_dir}', '{output}'], 'timeout_seconds': 20}
        self.save_contract(); self.init()
        self.entry('cb', 'b', .85)
        self.call('test', '--root', self.study, '--candidate', 'cb', '--rationale', 'early', ok=False)
        self.entry('cp', 'p', .90); self.entry('ca', 'a', .82)
        for ident in ('cb', 'cp'):
            self.call('test', '--root', self.study, '--candidate', ident, '--rationale', 'final')
            deadline = time.monotonic()+20
            while self.call('status', '--root', self.study)['status'] == 'testing' and time.monotonic() < deadline:
                time.sleep(.2)
        self.call('export', '--root', self.study)
        rep = json.loads((self.study/'report.json').read_text(encoding='utf-8'))
        self.assertEqual(rep['state']['test_looks'], 2)
        self.assertEqual(rep['test_comparisons'][0]['reference'], 'cb')
        self.assertAlmostEqual(rep['test_comparisons'][0]['ci']['effect'], .05)


def load_tests(loader, tests, pattern):
    # Only the matrix tests; inherited search-mode tests do not apply to a matrix contract.
    names = [n for n in MatrixTests.__dict__ if n.startswith('test_')]
    return unittest.TestSuite(MatrixTests(n) for n in names)


if __name__ == '__main__':
    unittest.main()
