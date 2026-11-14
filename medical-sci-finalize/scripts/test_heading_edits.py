"""Bounded heading calibration; synthetic evidence, never scientific approval."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import evidence_edit as edit
from test_evidence_edit import digest, span


OLD = '## 3.3 The model performs on par with comparators'
NEW = '## 3.3 The model shows no consistent advantage over comparators'
ZH_OLD = '## 3.3 模型与对照表现相近'
ZH_NEW = '## 3.3 模型相对对照未显示一致优势'


def fixture(root):
    before, after = root/'before', root/'after'
    before.mkdir()
    after.mkdir()
    en, zh, both = 'Results_EN.md', 'Results_ZH.md', 'Results_EN_ZH.md'
    body = '\n\nIn cohort A, 12 scans showed no benefit (PMID:12345678).\n\n## 3.4 External findings\n\nOther findings retained.\n'
    old = {en: '# Results\n\n'+OLD+body,
           zh: '# 结果\n\n'+ZH_OLD+body,
           both: '# Results\n\n'+OLD+'\n**模型与对照表现相近**'+body}
    new = {en: old[en].replace(OLD, NEW), zh: old[zh].replace(ZH_OLD, ZH_NEW),
           both: old[both].replace(OLD, NEW).replace('**模型与对照表现相近**', '**模型相对对照未显示一致优势**')}
    for directory, texts in [(before, old), (after, new)]:
        for key, text in texts.items():
            (directory/key).write_bytes(text.encode('utf-8'))
    def pair(key, left, right):
        return dict(source=span(key, old[key], left), candidate=span(key, new[key], right))
    heading = dict(id='H1', section_id=en+'#heading-2', **pair(en, OLD, NEW),
                   reviewed_by='Author', rationale='Calibrate comparative strength; same comparison and section.',
                   translations=[dict(language='ZH', source=[span(zh, old[zh], ZH_OLD)],
                     candidate=[span(zh, new[zh], ZH_NEW)], reviewed_by='Author', rationale='Same calibrated comparison.'),
                     dict(language='EN_ZH', source=[span(both, old[both], OLD), span(both, old[both], '**模型与对照表现相近**')],
                     candidate=[span(both, new[both], NEW), span(both, new[both], '**模型相对对照未显示一致优势**')],
                     reviewed_by='Author', rationale='Both displayed languages calibrated together.')])
    review = dict(schema_version=1, reviewers=dict(editor='Author', scientific='Author', bilingual='Author'),
                  inventory={key: dict(source_sha256=digest(before/key), candidate_sha256=digest(after/key)) for key in old},
                  claims=[], unknowns=[], heading_edits=[heading],
                  narrative=dict(reviewed_by='Author', source=[span(en, old[en])], candidate=[span(en, new[en])],
                    summary='Full Results reviewed; comparison title calibrated to unchanged evidence.',
                    issues=[dict(id='N1', kind='overclaiming heading', **{side: [heading[side]] for side in ('source','candidate')},
                        decision='resolved', central=False, reviewed_by='Author', reason='Title now matches seed-varying comparison.')]))
    path = root/'review.json'
    path.write_text(json.dumps(review, ensure_ascii=False), encoding='utf-8')
    return before, after, path, review, old, new


class HeadingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.before, self.after, self.path, self.review, self.old, self.new = fixture(Path(self.temp.name))

    def compare(self):
        self.path.write_text(json.dumps(self.review, ensure_ascii=False), encoding='utf-8')
        return edit.compare_paths(self.before, self.after, self.path)

    def rewrite(self, key, text):
        (self.after/key).write_bytes(text.encode('utf-8'))
        self.review['inventory'][key]['candidate_sha256'] = digest(self.after/key)

    def test_explicit_three_language_title_calibration(self):
        self.assertEqual(self.compare()['errors'], [])

    def test_undeclared_titles_stay_locked(self):
        del self.review['heading_edits']
        self.assertTrue(self.compare()['errors'])

    def test_stale_inventory_and_exact_spans_rejected(self):
        self.review['inventory']['Results_EN.md']['source_sha256'] = '0'*64
        self.assertTrue(self.compare()['errors'])
        self.review['inventory']['Results_EN.md']['source_sha256'] = digest(self.before/'Results_EN.md')
        self.review['heading_edits'][0]['candidate']['start'] += 1
        self.assertTrue(self.compare()['errors'])

    def test_missing_bilingual_or_combined_mapping_rejected(self):
        for language in ('ZH', 'EN_ZH'):
            original = copy.deepcopy(self.review)
            self.review['heading_edits'][0]['translations'] = [x for x in self.review['heading_edits'][0]['translations'] if x['language'] != language]
            self.assertTrue(self.compare()['errors'])
            self.review = original
        self.review['heading_edits'][0]['translations'][1]['source'].pop()
        self.review['heading_edits'][0]['translations'][1]['candidate'].pop()
        self.assertTrue(self.compare()['errors'])

    def test_heading_edit_needs_narrative_issue(self):
        self.review['narrative']['issues'] = []
        self.assertTrue(self.compare()['errors'])

    def test_level_count_order_and_section_identity_rejected(self):
        original = copy.deepcopy(self.review)
        for text in (self.new['Results_EN.md'].replace(NEW, '# 3.3 Calibrated'),
                     self.new['Results_EN.md']+'\n## Added section\n',
                     self.new['Results_EN.md'].replace(NEW, '## 3.4 External findings').replace('## 3.4 External findings\n\nOther', NEW+'\n\nOther')):
            self.rewrite('Results_EN.md', text)
            self.assertTrue(self.compare()['errors'])
            self.review = copy.deepcopy(original)
        self.rewrite('Results_EN.md', self.new['Results_EN.md'])
        self.review['heading_edits'][0]['section_id'] = 'Results_EN.md#heading-3'
        self.assertTrue(self.compare()['errors'])

    def test_heading_permission_does_not_cover_body_edits(self):
        self.rewrite('Results_EN.md', self.new['Results_EN.md'].replace('no benefit', 'benefit'))
        self.assertTrue(self.compare()['errors'])

    def test_unchanged_unknown_under_renamed_section_keeps_identity(self):
        key = 'Results_EN.md'
        needle = 'In cohort A, 12 scans showed no benefit (PMID:12345678).'
        self.review['unknowns'] = [dict(id='U1', source=span(key, self.old[key], needle),
            candidate=span(key, self.new[key], needle), reason='Original evidence retained.')]
        self.assertEqual(self.compare()['errors'], [])

    def test_renamed_scope_does_not_allow_cross_section_unknown_move(self):
        key = 'Results_EN.md'
        needle = 'Other findings retained.'
        # An identical duplicate exists in another section; exact literal identity is insufficient.
        left = self.old[key].replace('In cohort A', needle+' In cohort A')
        (self.before/key).write_bytes(left.encode())
        self.review['inventory'][key]['source_sha256'] = digest(self.before/key)
        self.review['narrative']['source'] = [span(key, left)]
        self.review['unknowns'] = [dict(id='U1', source=span(key, left, needle),
            candidate=span(key, self.new[key], needle), reason='Cannot migrate scope.')]
        self.assertTrue(self.compare()['errors'])

    def test_preexisting_negative_or_numeric_heading_evidence_cannot_disappear(self):
        self.assertNotEqual(edit._tokens('## No advantage in 12 scans'), edit._tokens('## Advantage in 12 scans'))
        h = self.review['heading_edits'][0]
        h['source']['text'] = '## no advantage'
        self.assertTrue(self.compare()['errors'])


if __name__ == '__main__':
    unittest.main()
