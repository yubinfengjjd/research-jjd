"""Synthetic real-file tests for source-bound structural editing."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

try:
    import evidence_edit as edit
except ModuleNotFoundError:
    edit = None


EN_OLD = '# Results\n\nIn cohort A, 12 scans showed no benefit (PMID:12345678).\n\nIn cohort A, no benefit was observed.\n'
EN_NEW = '# Results\n\nIn cohort A, 12 scans showed no benefit (PMID:12345678); no benefit was observed.\n'
ZH_OLD = '# Results\n\n队列A的12张扫描无获益 (PMID:12345678)。\n\n队列A无获益。\n'
ZH_NEW = '# Results\n\n队列A的12张扫描无获益 (PMID:12345678)；无获益。\n'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def span(file, text, needle=None):
    needle = text.strip() if needle is None else needle
    start = text.index(needle)
    return dict(file=file, start=start, end=start+len(needle), text=needle)


def fixture(root, combined=True):
    before = root/'project/04_manuscript'
    after = root/'stage'
    before.mkdir(parents=True)
    after.mkdir()
    en, zh, both = 'Results/Results_EN.md', 'Results/Results_ZH.md', 'Results/Results_EN_ZH.md'
    old = {en: EN_OLD, zh: ZH_OLD}
    new = {en: EN_NEW, zh: ZH_NEW}
    if combined:
        old[both] = EN_OLD+'\n'+ZH_OLD
        new[both] = EN_NEW+'\n'+ZH_NEW
    for directory, contents in [(before, old), (after, new)]:
        for key, value in contents.items():
            path = directory/key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding='utf-8', newline='')
    facts = []
    for ident, kind, value in [('n', 'measurement', '12 scans'), ('negative', 'qualifier', 'no benefit'),
                               ('cite', 'citation', 'PMID:12345678')]:
        facts.append(dict(id=ident, kind=kind, source=[span(en, EN_OLD, value)],
                          candidate=[span(en, EN_NEW, value)], context=[dict(
                          source=span(en, EN_OLD, 'In cohort A, 12 scans showed no benefit (PMID:12345678)'),
                          candidate=span(en, EN_NEW, 'In cohort A, 12 scans showed no benefit (PMID:12345678)'), scope=[0])]))
    translations = []
    for lang, key in [('ZH', zh)] + ([('EN_ZH', both)] if combined else []):
        trans_facts = []
        for fact in facts:
            value = {'n': '12张扫描', 'negative': '无获益', 'cite': 'PMID:12345678'}[fact['id']]
            trans_facts.append(dict(fact=fact['id'], source=[span(key, old[key], value)],
                                    candidate=[span(key, new[key], value)], context=[dict(
                                    source=span(key, old[key], '队列A的12张扫描无获益 (PMID:12345678)'),
                                    candidate=span(key, new[key], '队列A的12张扫描无获益 (PMID:12345678)'), scope=[0])]))
            if lang == 'EN_ZH':
                trans_facts[-1]['source'].append(span(key, old[key], fact['source'][0]['text']))
                trans_facts[-1]['candidate'].append(span(key, new[key], fact['candidate'][0]['text']))
                trans_facts[-1]['context'].append(dict(
                    source=span(key, old[key], 'In cohort A, 12 scans showed no benefit (PMID:12345678)'),
                    candidate=span(key, new[key], 'In cohort A, 12 scans showed no benefit (PMID:12345678)'), scope=[1]))
        translations.append(dict(language=lang, source=[span(key, old[key])], candidate=[span(key, new[key])],
                                 facts=trans_facts, scope=[dict(source=span(key, old[key], '队列A'),
                                 candidate=span(key, new[key], '队列A'))], reviewed_by='Author',
                                 rationale='Same cohort, count and adverse finding checked in both languages.'))
        if lang == 'EN_ZH':
            translations[-1]['scope'].append(dict(source=span(key, old[key], 'cohort A'),
                                                  candidate=span(key, new[key], 'cohort A')))
    review = dict(schema_version=1, reviewers=dict(editor='Author', scientific='Author', bilingual='Author'),
                  inventory={k: dict(source_sha256=digest(before/k), candidate_sha256=digest(after/k)) for k in old},
                  claims=[dict(id='C1', reviewed_by='Author', source=[span(en, EN_OLD)], candidate=[span(en, EN_NEW)],
                  scope=[dict(axis='cohort', source=span(en, EN_OLD, 'cohort A'), candidate=span(en, EN_NEW, 'cohort A'))],
                  facts=facts, provenance=[dict(source=span(en, EN_OLD, 'PMID:12345678'),
                  candidate=span(en, EN_NEW, 'PMID:12345678'))], translations=translations)], unknowns=[],
                  narrative=dict(reviewed_by='Author', source=[span(en, EN_OLD)], candidate=[span(en, EN_NEW)],
                  summary='Whole Results read for flow and preserved adverse evidence.', issues=[dict(id='N1', kind='repetition',
                  source=[span(en, EN_OLD)], candidate=[span(en, EN_NEW)], decision='resolved', central=False,
                  reviewed_by='Author', reason='Repeated cohort qualifier merged within Results; adverse result retained.')]))
    review_path = root/'review.json'
    review_path.write_text(json.dumps(review, ensure_ascii=False), encoding='utf-8')
    changes = root/'changes.json'
    changes.write_text(json.dumps({'schema_version': 1, 'review_sha256': digest(review_path),
                                  'decisions': ['N1']}), encoding='utf-8')
    decisions = root/'decisions.json'
    decisions.write_bytes(changes.read_bytes())
    return before, after, review_path, changes, decisions, review


class StructuralTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(edit, 'structural editing module is required')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.before, self.after, self.review_path, self.changes, self.decisions, self.review = fixture(self.root)

    def save(self):
        self.review_path.write_text(json.dumps(self.review, ensure_ascii=False), encoding='utf-8')

    def compare(self):
        return edit.compare_paths(self.before, self.after, self.review_path)

    def test_merge_qualifiers_and_bilingual_group(self):
        result = self.compare()
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['files']), 3)
        result = edit.apply_edit(self.before, self.after, self.review_path, self.changes,
                                 self.decisions, self.before.parent, '2026-11-05')
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['applied']), 3)
        self.assertEqual((self.before/'Results/Results_EN.md').read_text(encoding='utf-8'), EN_NEW)
        self.assertEqual((Path(result['archive'])/'Results/Results_EN.md').read_text(encoding='utf-8'), EN_OLD)

    def test_stale_source_and_candidate_hashes(self):
        for side in [self.before, self.after]:
            target = side/'Results/Results_EN.md'
            original = target.read_bytes()
            target.write_bytes(original+b' ')
            self.assertTrue(self.compare()['errors'])
            target.write_bytes(original)

    def test_malformed_reviews_fail_closed(self):
        for bad in [[], None, {'schema_version': True}, dict(self.review, claims='yes'),
                    dict(self.review, inventory=[]), dict(self.review, unexpected=True)]:
            self.review_path.write_text(json.dumps(bad), encoding='utf-8')
            self.assertTrue(self.compare()['errors'], repr(bad))
        self.review_path.write_text('{', encoding='utf-8')
        self.assertTrue(self.compare()['errors'])

    def test_exact_span_and_scope_changes_rejected(self):
        self.review['claims'][0]['scope'][0]['candidate']['text'] = 'cohort B'
        self.save()
        self.assertTrue(self.compare()['errors'])
        self.review['claims'][0]['scope'][0]['candidate']['text'] = 'cohort A'
        self.review['claims'][0]['source'][0]['start'] = True
        self.save()
        self.assertTrue(self.compare()['errors'])

    def test_missing_adverse_fact_cannot_be_asserted_away(self):
        claim = self.review['claims'][0]
        claim['facts'] = [f for f in claim['facts'] if f['id'] != 'negative']
        for translation in claim['translations']:
            translation['facts'] = [f for f in translation['facts'] if f['fact'] != 'negative']
        self.save()
        self.assertTrue(self.compare()['errors'])

    def test_numeric_or_citation_loss_even_with_fresh_hash_and_claim(self):
        for old, new in [('12 scans', '13 scans'), ('PMID:12345678', 'PMID:87654321'), ('no benefit', 'benefit')]:
            with self.subTest(value=old):
                temp = self.root/old.replace(':', '_').replace(' ', '_')
                temp.mkdir()
                before, after, path, _, _, review = fixture(temp)
                target = after/'Results/Results_EN.md'
                target.write_text(EN_NEW.replace(old, new), encoding='utf-8', newline='')
                review['inventory']['Results/Results_EN.md']['candidate_sha256'] = digest(target)
                review['claims'][0]['candidate'] = [span('Results/Results_EN.md', target.read_text(encoding='utf-8'))]
                path.write_text(json.dumps(review), encoding='utf-8')
                self.assertTrue(edit.compare_paths(before, after, path)['errors'])

    def test_bilingual_boolean_or_missing_combined_coverage_rejected(self):
        self.review['claims'][0]['translations'] = True
        self.save()
        self.assertTrue(self.compare()['errors'])
        self.review['claims'][0]['translations'] = []
        self.save()
        self.assertTrue(self.compare()['errors'])

    def test_narrative_unresolved_central_issue_blocks(self):
        issue = self.review['narrative']['issues'][0]
        issue.update(decision='blocked', central=True)
        self.save()
        self.assertTrue(self.compare()['errors'])

    def test_unrelated_file_inventory_is_not_edit_authorization(self):
        (self.before/'notes.txt').write_text('private note', encoding='utf-8')
        (self.after/'notes.txt').write_text('changed', encoding='utf-8')
        self.assertTrue(self.compare()['errors'])

    def test_no_implicit_word_minimum_and_explicit_limit(self):
        self.assertEqual(self.compare()['errors'], [])
        self.review['author_limits'] = {'Results/Results_EN.md': {'max_words': 2}}
        self.save()
        self.assertTrue(self.compare()['errors'])

    def test_transaction_rollback_and_no_temporary_leftovers(self):
        self.assertEqual(self.compare()['errors'], [])
        originals = {str(p.relative_to(self.before)): p.read_bytes() for p in self.before.rglob('*') if p.is_file()}
        real_replace = edit.os.replace
        calls = []
        def fail_second(source, target):
            calls.append(str(target))
            if len(calls) == 2:
                raise OSError('synthetic write failure')
            return real_replace(source, target)
        with patch.object(edit.os, 'replace', side_effect=fail_second):
            result = edit.apply_edit(self.before, self.after, self.review_path, self.changes,
                                     self.decisions, self.before.parent, '2026-11-05')
        self.assertTrue(result['errors'])
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual({str(p.relative_to(self.before)): p.read_bytes() for p in self.before.rglob('*') if p.is_file()}, originals)

    def test_security_date_and_stage_overlap_and_symlink(self):
        for day, stage in [('../outside', self.after), ('2026-11-05', self.before)]:
            result = edit.apply_edit(self.before, stage, self.review_path, self.changes,
                                     self.decisions, self.before.parent, day)
            self.assertTrue(result['errors'])
        link = self.after/'escape'
        try:
            link.symlink_to(self.before, target_is_directory=True)
        except OSError:
            if os.name != 'nt':
                self.skipTest('OS does not permit symlink creation')
            created = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(self.before)], capture_output=True)
            self.assertEqual(created.returncode, 0, created.stderr.decode(errors='replace'))
        try:
            self.assertTrue(self.compare()['errors'])
        finally:
            if link.is_symlink():
                link.unlink()
            else:
                os.rmdir(link)

    def test_unknown_original_can_remain_while_other_prose_changes(self):
        key = 'Results/Results_EN.md'
        uncertain = 'The pilot boundary is unclear.'
        for directory in [self.before, self.after]:
            target = directory/key
            target.write_bytes(target.read_bytes()+b'\n'+uncertain.encode('utf-8')+b'\n')
        old, new = (self.before/key).read_text(encoding='utf-8'), (self.after/key).read_text(encoding='utf-8')
        self.review['inventory'][key] = dict(source_sha256=digest(self.before/key), candidate_sha256=digest(self.after/key))
        self.review['narrative']['source'] = [span(key, old)]
        self.review['narrative']['candidate'] = [span(key, new)]
        self.review['unknowns'] = [dict(id='U1', source=span(key, old, uncertain), candidate=span(key, new, uncertain),
                                        reason='Local interpretation pending; exact original retained.')]
        self.review['narrative']['issues'].append(dict(id='N2', kind='uncertain local scope', source=[span(key, old, uncertain)],
                  candidate=[span(key, new, uncertain)], decision='blocked', central=False, reviewed_by='Author',
                  reason='Original kept pending clarification; independent paragraph merge can proceed.'))
        self.save()
        self.assertEqual(self.compare()['errors'], [])
        target = self.after/key
        target.write_text(new.replace(uncertain, 'The pilot boundary is clear.'), encoding='utf-8', newline='')
        self.review['inventory'][key]['candidate_sha256'] = digest(target)
        self.save()
        self.assertTrue(self.compare()['errors'])

    def test_removed_unique_adverse_fact_with_fully_refreshed_review_is_rejected(self):
        key = 'Results/Results_EN.md'
        target = self.after/key
        new = EN_NEW.replace('no benefit', 'benefit')
        target.write_text(new, encoding='utf-8', newline='')
        self.review['inventory'][key]['candidate_sha256'] = digest(target)
        claim = self.review['claims'][0]
        claim['candidate'] = [span(key, new)]
        claim['facts'] = [f for f in claim['facts'] if f['id'] != 'negative']
        for translation in claim['translations']:
            translation['facts'] = [f for f in translation['facts'] if f['fact'] != 'negative']
        self.review['narrative']['candidate'] = [span(key, new)]
        self.review['narrative']['issues'][0]['candidate'] = [span(key, new)]
        def refresh_candidates(node):
            if isinstance(node, dict):
                for field, value in node.items():
                    if field == 'candidate':
                        for item in value if isinstance(value, list) else [value]:
                            if item['file'] == key:
                                item.update(span(key, new, item['text'].replace('no benefit', 'benefit')))
                    else:
                        refresh_candidates(value)
            elif isinstance(node, list):
                for item in node:
                    refresh_candidates(item)
        refresh_candidates(self.review)
        self.save()
        errors = self.compare()['errors']
        self.assertTrue(any('evidence changed' in error for error in errors), errors)

    def test_section_move_and_actual_scope_anchor_change(self):
        key = 'Results/Results_EN.md'
        old = EN_OLD+'\n## Secondary\n\nOther observation.\n'
        new = '# Results\n\nOther observation.\n\n## Secondary\n\n'+EN_NEW.split('\n\n', 1)[1]
        for directory, text in [(self.before, old), (self.after, new)]:
            (directory/key).write_text(text, encoding='utf-8', newline='')
        self.review['inventory'][key] = dict(source_sha256=digest(self.before/key), candidate_sha256=digest(self.after/key))
        self.review['claims'][0]['candidate'] = [span(key, new, EN_NEW.split('\n\n', 1)[1].strip())]
        self.review['claims'][0]['source'] = [span(key, old, EN_OLD.split('\n\n', 1)[1].strip())]
        self.save()
        self.assertTrue(self.compare()['errors'])

    def test_fresh_mixed_scope_swap_cannot_pass_literal_bags(self):
        old = '# Results\n\nIn cohort A, a single-run estimate was 0.8. In cohort B, cross-cohort validation yielded 0.9.\n'
        new = '# Results\n\nIn cohort B, a single-run estimate was 0.8. In cohort A, cross-cohort validation yielded 0.9.\n'
        before, after = self.root/'mixed_before', self.root/'mixed_after'
        before.mkdir()
        after.mkdir()
        key = 'Results_EN.md'
        (before/key).write_bytes(old.encode())
        (after/key).write_bytes(new.encode())
        def pair(value):
            return dict(source=span(key, old, value), candidate=span(key, new, value))
        # Each literal bag, inventory, exact span and disposition is fresh and valid;
        # the absent ownership context is precisely the missing scientific binding.
        claim = dict(id='M1', reviewed_by='Author', source=[span(key, old)], candidate=[span(key, new)],
                     scope=[dict(axis='cohort', **pair('cohort A')), dict(axis='cohort', **pair('cohort B'))],
                     provenance=[pair('estimate')], translations=[],
                     facts=[dict(id=str(i), kind='result', source=[span(key, old, value)], candidate=[span(key, new, value)])
                            for i, value in enumerate(['single-run', '0.8', 'cross-cohort validation', '0.9'])])
        review = dict(schema_version=1, reviewers=self.review['reviewers'], inventory={key: dict(
                      source_sha256=digest(before/key), candidate_sha256=digest(after/key))}, claims=[claim], unknowns=[],
                      narrative=dict(reviewed_by='Author', source=[span(key, old)], candidate=[span(key, new)],
                      summary='Whole manuscript reviewed.', issues=[dict(id='N1', kind='flow', source=[span(key, old)],
                      candidate=[span(key, new)], decision='resolved', central=False, reviewed_by='Author', reason='Grouped results.')]))
        self.review_path.write_text(json.dumps(review), encoding='utf-8')
        self.assertTrue(edit.compare_paths(before, after, self.review_path)['errors'])
        # Supplying isolated unchanged fact contexts cannot stand in for scope ownership.
        for fact in claim['facts']:
            fact['context'] = [dict(source=fact['source'][0], candidate=fact['candidate'][0], scope=[0, 1])]
        self.review_path.write_text(json.dumps(review), encoding='utf-8')
        self.assertTrue(edit.compare_paths(before, after, self.review_path)['errors'])
        # Omitting the second cohort declaration and claiming a broad context also fails.
        claim['scope'] = claim['scope'][:1]
        for fact in claim['facts']:
            fact['context'] = [dict(source=span(key, old), candidate=span(key, new), scope=[0])]
        self.review_path.write_text(json.dumps(review), encoding='utf-8')
        self.assertTrue(edit.compare_paths(before, after, self.review_path)['errors'])

    def test_real_same_unit_conjunction_merge_removes_duplicate_qualifier(self):
        old = '# Results\n\nSingle-run AUROC analysis showed A. Single-run AUROC analysis showed B.\n'
        new = '# Results\n\nSingle-run AUROC analysis showed A and B.\n'
        before, after = self.root/'merge_before', self.root/'merge_after'
        before.mkdir()
        after.mkdir()
        key = 'Results_EN.md'
        (before/key).write_bytes(old.encode())
        (after/key).write_bytes(new.encode())
        claim = dict(id='M1', reviewed_by='Author', source=[span(key, old)], candidate=[span(key, new)],
                     scope=[dict(axis='run', source=span(key, old, 'Single-run'), candidate=span(key, new, 'Single-run'))],
                     provenance=[dict(source=span(key, old, 'analysis'), candidate=span(key, new, 'analysis'))], translations=[],
                     facts=[dict(id=value, kind='result', source=[span(key, old, value)], candidate=[span(key, new, value)],
                     context=[dict(source=span(key, old, 'Single-run AUROC analysis showed '+value+'.'),
                                   candidate=span(key, new, 'Single-run AUROC analysis showed A and B.'), scope=[0])]) for value in ['A', 'B']])
        review = dict(schema_version=1, reviewers=self.review['reviewers'], inventory={key: dict(
                      source_sha256=digest(before/key), candidate_sha256=digest(after/key))}, claims=[claim], unknowns=[],
                      narrative=dict(reviewed_by='Author', source=[span(key, old)], candidate=[span(key, new)],
                      summary='Read whole Results for scope and flow.', issues=[dict(id='N1', kind='repetition', source=[span(key, old)],
                      candidate=[span(key, new)], decision='resolved', central=False, reviewed_by='Author', reason='Merged same-run findings; both atomic results retained.')]))
        self.review_path.write_text(json.dumps(review), encoding='utf-8')
        self.assertEqual(edit.compare_paths(before, after, self.review_path)['errors'], [])

    def test_hyphenated_scope_adjectives_do_not_create_named_run_ids(self):
        for text in ['The single-run AUROC was 0.82.', 'A single-run CI crossed zero.',
                     'The single–run AUROC was 0.82.', 'The single‑run CI crossed zero.']:
            self.assertEqual(edit._named_scopes(text), {})
        self.assertEqual(edit._named_scopes('The estimate in run A was 0.82.'), {'run': {'run a'}})

    def test_manifest_duplicate_keys_paths_and_invalid_types(self):
        for bad in [dict(self.review, unknowns=True), dict(self.review, author_limits={'../outside': {'max_words': 1}}),
                    dict(self.review, reviewers={'editor': 7, 'scientific': 'Author', 'bilingual': 'Author'})]:
            self.review_path.write_text(json.dumps(bad), encoding='utf-8')
            self.assertTrue(self.compare()['errors'])
        self.review_path.write_text('{"schema_version":1,"schema_version":1}', encoding='utf-8')
        self.assertTrue(self.compare()['errors'])

    def test_project_author_limits_cannot_be_omitted_from_review(self):
        path = self.before.parent/'writing-limits.json'
        path.write_text('{"results":{"max":2}}', encoding='utf-8')
        self.assertTrue(self.compare()['errors'])
        path.write_text('{"results":{"max":true}}', encoding='utf-8')
        self.assertTrue(self.compare()['errors'])

    def test_ci_bound_order_is_preserved_even_when_numeric_set_is_identical(self):
        left = '95% CI [0.1, 0.9]'
        right = '95% CI [0.9, 0.1]'
        self.assertNotEqual(edit._tokens(left), edit._tokens(right))

    def test_chinese_adjacent_count_is_detected_without_ascii_identifier_digits(self):
        self.assertIn((0, '12'), edit._tokens('队列A的12张扫描'))
        self.assertNotIn((0, '12'), edit._tokens('cohortA12'))
        self.assertNotEqual(edit._tokens('队列A的12张扫描'), edit._tokens('队列A的13张扫描'))

    def test_project_limits_validate_absent_known_sections_and_reject_unknown(self):
        path = self.before.parent/'writing-limits.json'
        path.write_text('{"abstract":{"max":250}}', encoding='utf-8')
        self.assertEqual(self.compare()['errors'], [])
        path.write_text('{"odd":{"max":250}}', encoding='utf-8')
        self.assertTrue(self.compare()['errors'])
        path.write_text('{"abstract":{"max":true}}', encoding='utf-8')
        self.assertTrue(self.compare()['errors'])

    def test_declared_legend_limits_apply_to_each_caption(self):
        path = self.before.parent/'writing-limits.json'
        path.write_text('{"legends":{"min":5,"max":12}}', encoding='utf-8')
        text = '**Figure 1. First title.** Four words retained here.\n\n**Figure 2. Other title.** Four words retained here.'
        edit._limits({}, self.before, {'Figure_Legends/Figure_Legends_EN.md': text})
        with self.assertRaises(ValueError):
            edit._limits({}, self.before, {'Figure_Legends/Figure_Legends_EN.md': '**Figure 1. Short.**'})

    def test_word_count_matches_canonical_and_abstract_limit_excludes_metadata(self):
        import check_finalize as strict
        texts = ['# Results\n\n**Some** [linked words](https://example.invalid) (PMID: 12345678) (Fig. 2) (a).',
                 'An AUC of 0.5 (95% CI 0.1–0.9) in 12 scans.', 'alpha-beta x(a) （b）， retained']
        for text in texts:
            self.assertEqual(edit._word_count(text), strict.word_count(text))
        path = self.before.parent/'writing-limits.json'
        path.write_text('{"abstract":{"max":2}}', encoding='utf-8')
        edit._limits({}, self.before, {'Abstract/Abstract_EN.md': '# Abstract\n\nTwo words\n\n## Keywords\n\nmany ignored metadata words\n\n## Highlights\n\nmany other ignored metadata words'})

    def test_claim_and_narrative_coverage_cannot_be_omitted(self):
        for field in ['claims', 'narrative']:
            original = copy.deepcopy(self.review)
            if field == 'claims':
                self.review[field] = []
            else:
                self.review[field]['issues'] = []
            self.save()
            self.assertTrue(self.compare()['errors'])
            self.review = original

    def test_archive_includes_unchanged_companion_and_rollbacks_are_exercised(self):
        key = 'Results/Results_ZH.md'
        (self.after/key).write_bytes((self.before/key).read_bytes())
        self.review['inventory'][key]['candidate_sha256'] = digest(self.after/key)
        translation = self.review['claims'][0]['translations'][0]
        translation['candidate'] = copy.deepcopy(translation['source'])
        for anchor in translation['scope']:
            anchor['candidate'] = copy.deepcopy(anchor['source'])
        for fact in translation['facts']:
            fact['candidate'] = copy.deepcopy(fact['source'])
        self.save()
        for path in [self.changes, self.decisions]:
            path.write_text(json.dumps({'schema_version': 1, 'review_sha256': digest(self.review_path),
                                       'decisions': ['N1']}), encoding='utf-8')
        self.assertEqual(self.compare()['errors'], [])
        result = edit.apply_edit(self.before, self.after, self.review_path, self.changes,
                                 self.decisions, self.before.parent, '2026-11-05')
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['applied']), 2)
        self.assertEqual(len(result['archived']), 3)
        self.assertEqual((Path(result['archive'])/key).read_bytes(), (self.before/key).read_bytes())

    def test_malformed_changes_decisions_and_archive_collision(self):
        for path in [self.changes, self.decisions]:
            saved = path.read_bytes()
            path.write_text('[]', encoding='utf-8')
            result = edit.apply_edit(self.before, self.after, self.review_path, self.changes,
                                     self.decisions, self.before.parent, '2026-11-05')
            self.assertTrue(result['errors'])
            path.write_bytes(saved)
        archive = self.before.parent/'_archive/2026-11-05/04_manuscript/Results/Results_EN.md'
        archive.parent.mkdir(parents=True)
        archive.write_text('unrelated historical content', encoding='utf-8')
        self.assertTrue(edit.apply_edit(self.before, self.after, self.review_path, self.changes,
                                       self.decisions, self.before.parent, '2026-11-05')['errors'])


if __name__ == '__main__':
    unittest.main()
