"""Unit tests for scaffold_structural_review.py against evidence_edit gates."""
from __future__ import annotations

import json
import copy
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import evidence_edit as edit
import scaffold_structural_review as scaffold


class ScaffoldStructuralReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.proj = self.root / 'proj'
        self.before = self.proj / '04_manuscript'
        self.after = self.root / 'stage'
        self.before.mkdir(parents=True)
        self.after.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _run_verify(self, rationales=None):
        review_path = self.root / 'review.json'
        changes_path = self.root / 'changes.json'
        decisions_path = self.root / 'decisions.json'
        supplied = dict(rationales or {})
        supplied.setdefault('reviewers', dict.fromkeys(('editor', 'scientific', 'bilingual'), 'Synthetic test reviewer'))
        supplied.setdefault('narrative_summary', 'Synthetic fixture inventory and narrative explicitly reviewed for this test.')
        supplied.setdefault('issues', {'default': {'decision': 'resolved', 'reason': 'Synthetic fixture edit explicitly inspected.'}})
        draft, _, _ = scaffold.build_review_bundle(self.before, self.after, supplied)
        supplied.setdefault('inventory_review', {'reviewed_by': supplied['reviewers']['scientific'],
            'rationale': 'Synthetic fixtures only; no real manuscript or scientific approval.',
            'facts': [{'claim': c['id'], 'source': c['source'], 'candidate': c['candidate'],
                       'reason': 'Synthetic verbal fact inventory inspected explicitly.'} for c in draft['claims']]})
        summary = scaffold.write_review_bundle(
            self.before, self.after, review_path, changes_path, decisions_path,
            rationales=supplied, verify=True,
        )
        self.assertEqual(summary['compare']['errors'], [], summary)
        return review_path, changes_path, decisions_path, summary

    def test_crlf_prose_heading_subtitle_and_qualifiers_apply_cleanly(self):
        old_en = (
            '## Results\r\n\r\n'
            'Localization advantage remained unresolved (Fig. 6A; 0.5 px).\r\n\r\n'
            'Single-seed coverage was 75% in cohort A (12.5 vs 12.5).\r\n'
        )
        new_en = (
            '## Key Results\r\n\r\n'
            'Localization advantage was not established (Fig. 6A; 0.5 px).\r\n\r\n'
            'In the single evaluated seed, cohort A coverage was 75% (12.5 vs 12.5).\r\n'
        )
        old_zh = (
            '## 结果\r\n\r\n'
            '定位优势尚未明确（Fig. 6A；0.5 px）。\r\n\r\n'
            '队列 A 的单随机种子覆盖率为 75%（12.5 对 12.5）。\r\n'
        )
        new_zh = (
            '## 主要结果\r\n\r\n'
            '定位优势未能确立（图 6A；0.5 像素）。\r\n\r\n'
            '在单个评估种子中，队列 A 覆盖率为 75%（12.5 对 12.5）。\r\n'
        )
        old_ez = (
            '## Results\r\n**结果**\r\n\r\n'
            'Localization advantage remained unresolved (Fig. 6A; 0.5 px).\r\n\r\n'
            '定位优势尚未明确（Fig. 6A；0.5 px）。\r\n\r\n'
            'Single-seed coverage was 75% in cohort A (12.5 vs 12.5).\r\n\r\n'
            '队列 A 的单随机种子覆盖率为 75%（12.5 对 12.5）。\r\n'
        )
        new_ez = (
            '## Key Results\r\n**主要结果**\r\n\r\n'
            'Localization advantage was not established (Fig. 6A; 0.5 px).\r\n\r\n'
            '定位优势未能确立（图 6A；0.5 像素）。\r\n\r\n'
            'In the single evaluated seed, cohort A coverage was 75% (12.5 vs 12.5).\r\n\r\n'
            '在单个评估种子中，队列 A 覆盖率为 75%（12.5 对 12.5）。\r\n'
        )
        for name, data in [('Results_EN.md', old_en), ('Results_ZH.md', old_zh), ('Results_EN_ZH.md', old_ez)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Results_EN.md', new_en), ('Results_ZH.md', new_zh), ('Results_EN_ZH.md', new_ez)]:
            (self.after / name).write_bytes(data.encode('utf-8'))

        review_p, changes_p, decisions_p, _ = self._run_verify()
        applied = edit.apply_edit(self.before, self.after, review_p, changes_p, decisions_p, self.proj, '2026-11-15')
        self.assertEqual(applied['errors'], [], applied)
        self.assertEqual(sorted(applied['applied']), ['Results_EN.md', 'Results_EN_ZH.md', 'Results_ZH.md'])
        self.assertEqual((self.before / 'Results_EN.md').read_bytes(), new_en.encode('utf-8'))

    def test_multi_owner_caption_splits_cleanly_across_en_zh_and_enzh(self):
        old_en = (
            '## Legends\n\n'
            '**Figure 1.** In seed 0, MAE was 1.2 px (Fig. 1A). In seed 1, MAE was 1.5 px (Fig. 1B).\n'
        )
        new_en = (
            '## Legends\n\n'
            '**Figure 1.** Seed 0 showed 1.2 px MAE (Fig. 1A). Seed 1 showed 1.5 px MAE (Fig. 1B).\n'
        )
        old_zh = (
            '## 图注\n\n'
            '**图 1.** 在 seed 0 中 MAE 为 1.2 px（Fig. 1A）。在 seed 1 中 MAE 为 1.5 px（Fig. 1B）。\n'
        )
        new_zh = (
            '## 图注\n\n'
            '**图 1.** 种子0的 MAE 为 1.2 像素（图 1A）。种子1的 MAE 为 1.5 像素（图 1B）。\n'
        )
        old_ez = (
            '## Legends / 图注\n\n'
            '**Figure 1.** In seed 0, MAE was 1.2 px (Fig. 1A). In seed 1, MAE was 1.5 px (Fig. 1B).\n\n'
            '**图 1.** 在 seed 0 中 MAE 为 1.2 px（Fig. 1A）。在 seed 1 中 MAE 为 1.5 px（Fig. 1B）。\n'
        )
        new_ez = (
            '## Legends / 图注\n\n'
            '**Figure 1.** Seed 0 showed 1.2 px MAE (Fig. 1A). Seed 1 showed 1.5 px MAE (Fig. 1B).\n\n'
            '**图 1.** 种子0的 MAE 为 1.2 像素（图 1A）。种子1的 MAE 为 1.5 像素（图 1B）。\n'
        )
        for name, data in [('Legends_EN.md', old_en), ('Legends_ZH.md', old_zh), ('Legends_EN_ZH.md', old_ez)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Legends_EN.md', new_en), ('Legends_ZH.md', new_zh), ('Legends_EN_ZH.md', new_ez)]:
            (self.after / name).write_bytes(data.encode('utf-8'))

        _, _, _, summary = self._run_verify()
        self.assertGreaterEqual(summary['claims'], 2)

    def test_paragraph_merge_and_bilingual_only_heading_sync(self):
        old_en = '# Results\n\nFirst observation reached 80%.\n\nNext observation reached 90%.\n'
        new_en = '# Results\n\nFirst observation reached 80%, while next observation reached 90%.\n'
        old_zh = '# 结果旧题\n\n第一项观察达到 80%。\n\n下一项观察达到 90%。\n'
        new_zh = '# 结果新题\n\n第一项观察达到 80%，而下一项观察达到 90%。\n'
        for name, data in [('Results_EN.md', old_en), ('Results_ZH.md', old_zh)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Results_EN.md', new_en), ('Results_ZH.md', new_zh)]:
            (self.after / name).write_bytes(data.encode('utf-8'))

        review_p, _, _, summary = self._run_verify()
        review = json.loads(review_p.read_bytes().decode('utf-8'))
        self.assertEqual(summary['heading_edits'], 1)
        self.assertTrue(review['heading_edits'][0]['bilingual_sync_only'])

    def test_unchanged_multi_owner_sentence_inside_edited_note_preserved_verbatim(self):
        old_en = (
            '**Table S4.** Reference values are 0.9670 in seed 0, 0.9615 in seed 1, and 0.9584 in seed 2. '
            'The two ablations were evaluated in cohort A.\n'
        )
        new_en = (
            '**Table S4.** Reference values are 0.9670 in seed 0, 0.9615 in seed 1, and 0.9584 in seed 2. '
            'Both ablations underwent evaluation in cohort A.\n'
        )
        old_zh = (
            '**表 S4.** 参照值为种子 0 为 0.9670、种子 1 为 0.9615、种子 2 为 0.9584。'
            '在队列 A 中评估了两个消融。\n'
        )
        new_zh = (
            '**表 S4.** 参照值为种子 0 为 0.9670、种子 1 为 0.9615、种子 2 为 0.9584。'
            '两个消融均在队列 A 中完成评估。\n'
        )
        for name, data in [('Table_EN.md', old_en), ('Table_ZH.md', old_zh)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Table_EN.md', new_en), ('Table_ZH.md', new_zh)]:
            (self.after / name).write_bytes(data.encode('utf-8'))

        review_p, _, _, _ = self._run_verify()
        review = json.loads(review_p.read_bytes().decode('utf-8'))
        self.assertGreaterEqual(len(review['unknowns']), 1)

    def test_fails_closed_when_numeric_or_qualifier_evidence_drops(self):
        (self.before / 'Results_EN.md').write_bytes(b'# Results\n\nScore was 85% and remained unresolved.\n')
        (self.after / 'Results_EN.md').write_bytes(b'# Results\n\nScore improved to 95%.\n')
        with self.assertRaises(ValueError) as ctx:
            scaffold.build_review_bundle(self.before, self.after)
        self.assertIn('Evidence mismatch', str(ctx.exception))

    def test_single_newline_captions_pair_with_double_spaced_enzh(self):
        old_en = (
            '**Figure 1.** Cohort A reached 85% accuracy.\n'
            '**Figure 2.** Seed 0 evaluated 203 scans across sites.\n'
            '**Figure 3.** Calibration curve remained linear.\n'
        )
        new_en = (
            '**Figure 1.** Cohort A achieved 85% accuracy.\n'
            '**Figure 2.** Seed 0 evaluated 203 scans across sites.\n'
            '**Figure 3.** Calibration curve remained linear.\n'
        )
        old_zh = (
            '**图 1.** 队列 A 达到 85% 准确率。\n'
            '**图 2.** 种子 0 在各中心评估了 203 次扫描。\n'
            '**图 3.** 校准曲线保持线性。\n'
        )
        new_zh = (
            '**图 1.** 队列 A 取得 85% 准确率。\n'
            '**图 2.** 种子 0 在各中心评估了 203 次扫描。\n'
            '**图 3.** 校准曲线保持线性。\n'
        )
        old_ez = (
            '**Figure 1.** Cohort A reached 85% accuracy.\n\n'
            '**图 1.** 队列 A 达到 85% 准确率。\n\n'
            '**Figure 2.** Seed 0 evaluated 203 scans across sites.\n\n'
            '**图 2.** 种子 0 在各中心评估了 203 次扫描。\n\n'
            '**Figure 3.** Calibration curve remained linear.\n\n'
            '**图 3.** 校准曲线保持线性。\n'
        )
        new_ez = (
            '**Figure 1.** Cohort A achieved 85% accuracy.\n\n'
            '**图 1.** 队列 A 取得 85% 准确率。\n\n'
            '**Figure 2.** Seed 0 evaluated 203 scans across sites.\n\n'
            '**图 2.** 种子 0 在各中心评估了 203 次扫描。\n\n'
            '**Figure 3.** Calibration curve remained linear.\n\n'
            '**图 3.** 校准曲线保持线性。\n'
        )
        for name, data in [('Figure_Legends_EN.md', old_en), ('Figure_Legends_ZH.md', old_zh), ('Figure_Legends_EN_ZH.md', old_ez)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Figure_Legends_EN.md', new_en), ('Figure_Legends_ZH.md', new_zh), ('Figure_Legends_EN_ZH.md', new_ez)]:
            (self.after / name).write_bytes(data.encode('utf-8'))

        _, _, _, summary = self._run_verify()
        self.assertGreaterEqual(summary['claims'], 1)

    def test_methods_language_markers_and_results_subtitle_trimming(self):
        old_en = (
            '# Results\n\n'
            '## 3.1 Baseline Characteristics\n'
            '**Clinical summary**\n\n'
            'Cohort A included 120 eyes.\n\n'
            'Training used single-seed runs and achieved 91%.\n'
        )
        new_en = (
            '# Results\n\n'
            '## 3.1 Baseline Characteristics\n'
            '**Clinical summary**\n\n'
            'Cohort A enrolled 120 eyes.\n\n'
            'Training used single-evaluated-seed runs and achieved 91%.\n'
        )
        old_zh = (
            '# 结果\n\n'
            '## 3.1 基线特征\n'
            '**临床汇总**\n\n'
            '队列 A 纳入 120 只眼。\n\n'
            '训练采用单种子运行并达到 91%。\n'
        )
        new_zh = (
            '# 结果\n\n'
            '## 3.1 基线特征\n'
            '**临床汇总**\n\n'
            '队列 A 收录 120 只眼。\n\n'
            '训练采用单次评估种子运行并达到 91%。\n'
        )
        old_ez = (
            '# Results / 结果\n\n'
            '## 3.1 Baseline Characteristics / 基线特征\n'
            '**Clinical summary / 临床汇总**\n\n'
            '**English**\n\n'
            'Cohort A included 120 eyes.\n\n'
            '**中文对照**\n\n'
            '队列 A 纳入 120 只眼。\n\n'
            '**English**\n\n'
            'Training used single-seed runs and achieved 91%.\n\n'
            '**中文对照**\n\n'
            '训练采用单种子运行并达到 91%。\n'
        )
        new_ez = (
            '# Results / 结果\n\n'
            '## 3.1 Baseline Characteristics / 基线特征\n'
            '**Clinical summary / 临床汇总**\n\n'
            '**English**\n\n'
            'Cohort A enrolled 120 eyes.\n\n'
            '**中文对照**\n\n'
            '队列 A 收录 120 只眼。\n\n'
            '**English**\n\n'
            'Training used single-evaluated-seed runs and achieved 91%.\n\n'
            '**中文对照**\n\n'
            '训练采用单次评估种子运行并达到 91%。\n'
        )
        for name, data in [('Results_EN.md', old_en), ('Results_ZH.md', old_zh), ('Results_EN_ZH.md', old_ez)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Results_EN.md', new_en), ('Results_ZH.md', new_zh), ('Results_EN_ZH.md', new_ez)]:
            (self.after / name).write_bytes(data.encode('utf-8'))

        _, _, _, summary = self._run_verify()
        self.assertGreaterEqual(summary['claims'], 2)

    def test_grouped_split_blocks_in_enzh_discussion_layout(self):
        old_en = '# Discussion\n\nPoint one reached 75%. Point two reached 82%.\n'
        new_en = '# Discussion\n\nPoint one achieved 75%.\n\nPoint two achieved 82%.\n'
        old_zh = '# 讨论\n\n第一点达到 75%。第二点达到 82%。\n'
        new_zh = '# 讨论\n\n第一点取得 75%。\n\n第二点取得 82%。\n'
        old_ez = (
            '# Discussion / 讨论\n\n'
            'Point one reached 75%. Point two reached 82%.\n\n'
            '第一点达到 75%。第二点达到 82%。\n'
        )
        new_ez = (
            '# Discussion / 讨论\n\n'
            'Point one achieved 75%.\n\n'
            'Point two achieved 82%.\n\n'
            '第一点取得 75%。\n\n'
            '第二点取得 82%。\n'
        )
        for name, data in [('Discussion_EN.md', old_en), ('Discussion_ZH.md', old_zh), ('Discussion_EN_ZH.md', old_ez)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Discussion_EN.md', new_en), ('Discussion_ZH.md', new_zh), ('Discussion_EN_ZH.md', new_ez)]:
            (self.after / name).write_bytes(data.encode('utf-8'))

        _, _, _, summary = self._run_verify()
        self.assertGreaterEqual(summary['claims'], 1)

    def test_additive_single_evaluated_seed_without_baseline_qualifiers(self):
        old_en = '# Results\n\nConformal coverage reached 0.908 across sites.\n'
        new_en = '# Results\n\nIn the single evaluated seed, conformal coverage reached 0.908 across sites.\n'
        old_zh = '# 结果\n\n各中心保形覆盖率达到 0.908。\n'
        new_zh = '# 结果\n\n在唯一接受评价的种子中，各中心保形覆盖率达到 0.908。\n'
        old_ez = (
            '# Results / 结果\n\n'
            'Conformal coverage reached 0.908 across sites.\n\n'
            '各中心保形覆盖率达到 0.908。\n'
        )
        new_ez = (
            '# Results / 结果\n\n'
            'In the single evaluated seed, conformal coverage reached 0.908 across sites.\n\n'
            '在唯一接受评价的种子中，各中心保形覆盖率达到 0.908。\n'
        )
        for name, data in [('Results_EN.md', old_en), ('Results_ZH.md', old_zh), ('Results_EN_ZH.md', old_ez)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Results_EN.md', new_en), ('Results_ZH.md', new_zh), ('Results_EN_ZH.md', new_ez)]:
            (self.after / name).write_bytes(data.encode('utf-8'))

        with self.assertRaises(ValueError):
            self._run_verify()

    def test_multi_owner_localization_and_shared_citation_consolidation(self):
        old_en = (
            '# Results\n\n'
            'Recall varied across seeds 0–2 (Supplementary Fig. S3A).\n\n'
            'In seed 0, ANCHOR exceeded baseline by +0.007 (Fig. 4C). In seeds 1 and 2, difference was -0.002 (Fig. 4C).\n'
        )
        new_en = (
            '# Results\n\n'
            'Recall varied across seeds 0–2 (Supplementary Fig. S3A).\n\n'
            'In seed 0, ANCHOR exceeded baseline by +0.007; in seeds 1 and 2, difference was -0.002 (Fig. 4C).\n'
        )
        old_zh = (
            '# 结果\n\n'
            '从 seed 0 到 seed 2 召回率变化（补充图 S3A）。在种子 0 为 0.9670，种子 1 为 0.9615，种子 2 为 0.9584。\n\n'
            '在 seed 0 中高 +0.007（图 4C）。在 seed 1 和 seed 2 中为 -0.002（图 4C）。\n'
        )
        new_zh = (
            '# 结果\n\n'
            '从种子0到种子2召回率变化（补充图 S3A）。在种子0为 0.9670，种子1为 0.9615，种子2为 0.9584。\n\n'
            '在种子0中高 +0.007；在种子1和种子2中为 -0.002（图 4C）。\n'
        )
        old_ez = (
            '# Results / 结果\n\n'
            'Recall varied across seeds 0–2 (Supplementary Fig. S3A).\n\n'
            '从 seed 0 到 seed 2 召回率变化（补充图 S3A）。在种子 0 为 0.9670，种子 1 为 0.9615，种子 2 为 0.9584。\n\n'
            'In seed 0, ANCHOR exceeded baseline by +0.007 (Fig. 4C). In seeds 1 and 2, difference was -0.002 (Fig. 4C).\n\n'
            '在 seed 0 中高 +0.007（图 4C）。在 seed 1 和 seed 2 中为 -0.002（图 4C）。\n'
        )
        new_ez = (
            '# Results / 结果\n\n'
            'Recall varied across seeds 0–2 (Supplementary Fig. S3A).\n\n'
            '从种子0到种子2召回率变化（补充图 S3A）。在种子0为 0.9670，种子1为 0.9615，种子2为 0.9584。\n\n'
            'In seed 0, ANCHOR exceeded baseline by +0.007; in seeds 1 and 2, difference was -0.002 (Fig. 4C).\n\n'
            '在种子0中高 +0.007；在种子1和种子2中为 -0.002（图 4C）。\n'
        )
        for name, data in [('Results_EN.md', old_en), ('Results_ZH.md', old_zh), ('Results_EN_ZH.md', old_ez)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Results_EN.md', new_en), ('Results_ZH.md', new_zh), ('Results_EN_ZH.md', new_ez)]:
            (self.after / name).write_bytes(data.encode('utf-8'))

        _, _, _, summary = self._run_verify()
        self.assertGreaterEqual(summary['claims'], 2)

    def _cross_scope(self, bilingual=False):
        en_m = 'Analysis A used a single evaluated seed 0 for MAE measured in px.'
        en_r = 'In the single evaluated seed, Analysis A in seed 0 had MAE 0.72 px and no benefit.'
        en_n = 'Analysis A in seed 0 had MAE 0.72 px and no benefit.'
        zh_m = '分析 A 使用单个评估种子；seed 0 的 MAE 以 px 测量。'
        zh_r = '在单个评估种子中，分析 A 的 seed 0 的 MAE 为 0.72 px，无获益。'
        zh_n = '分析 A 的 seed 0 的 MAE 为 0.72 px，无获益。'
        rows = [('EN', en_m, en_r, en_n)]
        if bilingual:
            rows += [('ZH', zh_m, zh_r, zh_n), ('EN_ZH', en_m+'\n\n'+zh_m, en_r+'\n\n'+zh_r, en_n+'\n\n'+zh_n)]
        requests = []
        for lang, declaration, before, after in rows:
            mk, rk = 'Methods_'+lang+'.md', 'Results_'+lang+'.md'
            for folder, text in [(self.before, before), (self.after, after)]:
                (folder/mk).write_bytes(('# Methods\n\n'+declaration+'\n').encode('utf-8'))
                (folder/rk).write_bytes(('# Results\n\n'+text+'\n').encode('utf-8'))
            selector = lambda file, text: {'file': file, 'text': text}
            removed = []
            for phrase in ('single evaluated seed', '单个评估种子'):
                if phrase in before:
                    removed.append(selector(rk, phrase))
            guards = [{'axis': 'analysis', 'text': 'Analysis A' if lang == 'EN' else '分析 A'},
                      {'axis': 'endpoint', 'text': 'MAE'}, {'axis': 'run', 'text': 'seed 0'}, {'axis': 'unit', 'text': 'px'}]
            requests.append({'id': 'D_'+lang, 'reviewed_by': 'Synthetic test reviewer',
                'rationale': 'Synthetic exact scope declaration explicitly reviewed.',
                'declaration': selector(mk, declaration),
                'bindings': [{'language': lang, 'source': [selector(rk, before)], 'candidate': [selector(rk, after)],
                              'removed': removed, 'guards': guards}]})
        return {'scope_declaration_requests': requests}

    def test_explicit_methods_results_scope_binding_all_languages(self):
        rationale = self._cross_scope(bilingual=True)
        review_p, _, _, _ = self._run_verify(rationale)
        review = json.loads(review_p.read_text(encoding='utf-8'))
        self.assertEqual(len(review['scope_declarations']), 3)
        self.assertTrue(all(b['claim'] == 'C1' for d in review['scope_declarations'] for b in d['bindings']))

    def test_inherited_scope_missing_bilingual_binding_and_stale_slot_rejected(self):
        review_p, _, _, _ = self._run_verify(self._cross_scope(bilingual=True))
        original = json.loads(review_p.read_text(encoding='utf-8'))
        for language in ('ZH', 'EN_ZH'):
            review = copy.deepcopy(original)
            review['scope_declarations'] = [d for d in review['scope_declarations'] if d['id'] != 'D_'+language]
            review_p.write_text(json.dumps(review), encoding='utf-8')
            self.assertIn('bilingual/combined', str(edit.compare_paths(self.before, self.after, review_p)['errors']))
        review = copy.deepcopy(original)
        review['scope_declarations'][0]['bindings'][0]['removed'][0]['start'] += 1
        review_p.write_text(json.dumps(review), encoding='utf-8')
        self.assertTrue(edit.compare_paths(self.before, self.after, review_p)['errors'])

    def test_inherited_scope_wrong_owner_seed_unit_and_changed_values_rejected(self):
        rationale = self._cross_scope()
        for needle, replacement in [('Analysis A', 'Analysis B'), ('seed 0', 'seed 1'), ('px', 'mm')]:
            bad = copy.deepcopy(rationale)
            bad['scope_declaration_requests'][0]['bindings'][0]['guards'][0]['text'] = replacement
            with self.assertRaises(AssertionError):
                self._run_verify(bad)
        for old, new in [('0.72', '0.73'), ('no benefit', 'benefit')]:
            path = self.after/'Results_EN.md'
            original = path.read_bytes()
            path.write_bytes(original.replace(old.encode(), new.encode()))
            bad = copy.deepcopy(rationale)
            bad['scope_declaration_requests'][0]['bindings'][0]['candidate'][0]['text'] = path.read_text(encoding='utf-8').split('\n\n', 1)[1].strip()
            with self.assertRaises(ValueError):
                self._run_verify(bad)
            path.write_bytes(original)

    def test_wrong_declaration_owner_endpoint_and_seed_rejected(self):
        for needle, replacement in [('Analysis A', 'Analysis B'), ('seed 0', 'seed 1'), ('MAE', 'RMSE')]:
            rationale = self._cross_scope()
            request = rationale['scope_declaration_requests'][0]
            request['declaration']['text'] = request['declaration']['text'].replace(needle, replacement)
            for folder in (self.before, self.after):
                path = folder/'Methods_EN.md'
                path.write_bytes(path.read_bytes().replace(needle.encode(), replacement.encode()))
            with self.assertRaises(AssertionError):
                self._run_verify(rationale)

    def test_one_explicit_named_seed_declaration_without_fixed_qualifier(self):
        rationale = self._cross_scope()
        request = rationale['scope_declaration_requests'][0]
        original = request['declaration']['text']
        request['declaration']['text'] = original.replace('a single evaluated seed 0', 'seed 0 once')
        for folder in (self.before, self.after):
            path = folder/'Methods_EN.md'
            path.write_bytes(path.read_bytes().replace(original.encode(), request['declaration']['text'].encode()))
        # The Results clause can refer to the reviewed seed scope without repeating its identifier.
        for side, folder in [('source', self.before), ('candidate', self.after)]:
            path = folder/'Results_EN.md'
            path.write_bytes(path.read_bytes().replace(b' in seed 0', b''))
            request['bindings'][0][side][0]['text'] = request['bindings'][0][side][0]['text'].replace(' in seed 0', '')
        request['bindings'][0]['guards'][2]['location'] = 'declaration'
        self._run_verify(rationale)
        for suffix in (' and seed 1', '–2'):
            bad = copy.deepcopy(rationale)
            declaration = request['declaration']['text']
            changed = declaration.replace('seed 0', 'seed 0'+suffix)
            bad['scope_declaration_requests'][0]['declaration']['text'] = changed
            for folder in (self.before, self.after):
                path = folder/'Methods_EN.md'
                path.write_bytes(path.read_bytes().replace(declaration.encode(), changed.encode()))
            with self.assertRaises(AssertionError):
                self._run_verify(bad)
            for folder in (self.before, self.after):
                path = folder/'Methods_EN.md'
                path.write_bytes(path.read_bytes().replace(changed.encode(), declaration.encode()))

    def test_new_same_analysis_declaration_consolidates_two_existing_qualifiers(self):
        old = '# Results\n\nIn the single evaluated seed, Analysis A had MAE 0.72 px.\n\nIn the single evaluated seed, Analysis A had RMSE 0.74 px.\n'
        new = '# Results\n\nAnalysis A used the single evaluated seed for MAE and RMSE.\n\nAnalysis A had MAE 0.72 px.\n\nAnalysis A had RMSE 0.74 px.\n'
        (self.before/'Results_EN.md').write_bytes(old.encode())
        (self.after/'Results_EN.md').write_bytes(new.encode())
        self._run_verify()

    def test_negated_declarations_in_all_languages_and_not_only_are_rejected(self):
        cases = [('EN', lambda s: s.replace('used a single', 'did not use a single')),
                 ('EN', lambda s: s.replace('used a single', 'never used a single')),
                 ('EN', lambda s: s.replace('used a single', 'had not executed a single')),
                 ('EN', lambda s: s.replace('used a single', "didn't use a single")),
                 ('EN', lambda s: s.replace('used a single', 'didn’t use a single')),
                 ('EN', lambda s: s.replace('used a single', "can't use a single")),
                 ('EN', lambda s: s.replace('used a single', "won't use a single")),
                 ('ZH', lambda s: '分析 A 并未仅用单种子0评价 MAE（px）。'),
                 ('EN_ZH', lambda s: s.replace('使用', '并未使用')),
                 ('EN', lambda s: s.replace('used a single evaluated seed 0', 'used not only a single evaluated seed 0 but seed 1'))]
        for language, change in cases:
            rationale = self._cross_scope(bilingual=True)
            request = next(r for r in rationale['scope_declaration_requests'] if r['id'] == 'D_'+language)
            old = request['declaration']['text']
            changed = change(old)
            request['declaration']['text'] = changed
            for folder in (self.before, self.after):
                path = folder/('Methods_'+language+'.md')
                path.write_bytes(path.read_bytes().replace(old.encode(), changed.encode()))
            with self.assertRaisesRegex(AssertionError, 'must affirm'):
                self._run_verify(rationale)

    def test_mixed_analysis_same_heading_cannot_inherit_a_different_owner(self):
        old = '# Results\n\nIn the single evaluated seed, Analysis A had MAE 0.72 px.\n\nIn the single evaluated seed, Analysis B had MAE 0.74 px.\n'
        new = old.replace('In the single evaluated seed, Analysis B', 'Analysis B')
        (self.before/'Results_EN.md').write_bytes(old.encode())
        (self.after/'Results_EN.md').write_bytes(new.encode())
        with self.assertRaises(ValueError):
            scaffold.build_review_bundle(self.before, self.after)

    def test_scope_without_explicit_cross_file_mapping_fails(self):
        self._cross_scope()
        with self.assertRaises(ValueError):
            scaffold.build_review_bundle(self.before, self.after)

    def test_contradicted_noninferential_label_drops_only_while_the_test_stays(self):
        old = 'Analysis A did not establish a localization advantage in this non-inferential comparison (permutation P = 0.124).'
        kept = 'Analysis A did not establish a localization advantage in this comparison (permutation P = 0.124).'
        self._write_qualifier_triplet(old, kept, '分析 A 在该比较中未建立定位优势（permutation P = 0.124）。', '分析 A 在该比较中未建立定位优势（permutation P = 0.124）。')
        self._run_verify()
        lost = 'Analysis A did not establish a localization advantage in this comparison.'
        self._write_qualifier_triplet(old, lost, '分析 A 在该比较中未建立定位优势（permutation P = 0.124）。', '分析 A 在该比较中未建立定位优势。')
        with self.assertRaises(ValueError):
            scaffold.build_review_bundle(self.before, self.after)
        swapped = 'Analysis A used no inferential testing for localization (permutation P = 0.124).'
        self._write_qualifier_triplet(old, swapped, '分析 A 在该比较中未建立定位优势（permutation P = 0.124）。', '分析 A 未做推断检验（permutation P = 0.124）。')
        with self.assertRaises(ValueError):
            scaffold.build_review_bundle(self.before, self.after)

    def test_same_heading_chain_keeps_one_declaration_for_later_repeats(self):
        old = (
            '# Results\n\n'
            'In the single evaluated seed, Analysis A had MAE 0.72 px.\n\n'
            'In the single evaluated seed, Analysis A had RMSE 0.74 px.\n\n'
            'In the single evaluated seed, Analysis A had bias 0.01 px.\n'
        )
        new = (
            '# Results\n\n'
            'In the single evaluated seed, Analysis A had MAE 0.72 px.\n\n'
            'Analysis A had RMSE 0.74 px.\n\n'
            'Analysis A had bias 0.01 px.\n'
        )
        (self.before/'Results_EN.md').write_bytes(old.encode())
        (self.after/'Results_EN.md').write_bytes(new.encode())
        self._run_verify()

    def test_seed_chain_stops_at_a_different_owner(self):
        old = (
            '# Results\n\n'
            'In the single evaluated seed, Analysis A had MAE 0.72 px.\n\n'
            'In the single evaluated seed, Analysis B had MAE 0.70 px.\n\n'
            'In the single evaluated seed, Analysis A had RMSE 0.74 px.\n'
        )
        new = (
            '# Results\n\n'
            'In the single evaluated seed, Analysis A had MAE 0.72 px.\n\n'
            'Analysis B had MAE 0.70 px.\n\n'
            'Analysis A had RMSE 0.74 px.\n'
        )
        (self.before/'Results_EN.md').write_bytes(old.encode())
        (self.after/'Results_EN.md').write_bytes(new.encode())
        with self.assertRaises(ValueError):
            scaffold.build_review_bundle(self.before, self.after)

    def test_supplementary_prefix_keeps_the_same_figure_or_table_citation(self):
        self.assertEqual(
            edit._canonical_translated_anchor('Fig. S8'),
            edit._canonical_translated_anchor('Supplementary Fig. S8'),
        )
        self.assertEqual(
            edit._canonical_translated_anchor('Table S8'),
            edit._canonical_translated_anchor('Supplementary Table S8'),
        )
        self.assertEqual(
            edit._canonical_translated_anchor('Fig. 2'),
            edit._canonical_translated_anchor('Supplementary Fig. 2'),
        )
        self.assertEqual(
            edit._canonical_translated_anchor('Table 3'),
            edit._canonical_translated_anchor('Supplementary Table 3'),
        )
        en = 'The vocabulary is listed in Table S8. Localization used the map (Fig. S8).'
        new = en.replace('Table S8', 'Supplementary Table S8').replace('(Fig. S8)', '(Supplementary Fig. S8)')
        zh = '词表列于表 S8。定位使用该图（图 S8）。'
        new_zh = zh.replace('表 S8', '补充表 S8').replace('图 S8', '补充图 S8')
        self._write_qualifier_triplet(en, new, zh, new_zh)
        self._run_verify()

    def test_spacing_a_named_seed_keeps_an_unmatched_chinese_single_seed(self):
        en = (
            'In seed 0, Analysis A differed by +0.007 (95% CI, 0.002-0.015). '
            'These seed-specific positive results supported comparable BACC.'
        )
        old_zh = (
            '在种子0中，分析 A 相差 +0.007（95% CI，0.002–0.015）。'
            '这些单种子正向差异支持相近的 BACC。'
        )
        new_zh = old_zh.replace('种子0', '种子 0')
        self._write_qualifier_triplet(en, en, old_zh, new_zh)
        self._run_verify()

    def test_repeated_chinese_seed_opener_is_not_bound_to_interval_tokens(self):
        old_en = (
            '(a) In the single evaluated seed, Analysis A predicted boundaries. '
            '(b) Evaluated in the single evaluated seed, Analysis A had lower error. '
            '(d) In the single evaluated seed, paired boundary error was +0.017 px (95% CI, -0.019 to 0.058 px).'
        )
        new_en = old_en.replace('(b) Evaluated in the single evaluated seed, ', '(b) ')
        old_zh = (
            '(a) 在唯一接受评价的种子中，分析 A 预测边界。'
            '(b) 在唯一接受评价的种子中评估，分析 A 误差更低。'
            '(d) 在唯一接受评价的种子中，配对边界误差为 +0.017 px（95% CI，-0.019 至 0.058 px）。'
        )
        new_zh = old_zh.replace('(b) 在唯一接受评价的种子中评估，', '(b) ')
        self._write_qualifier_triplet(old_en, new_en, old_zh, new_zh)
        self._run_verify()

    def test_repeated_seed_inside_one_paragraph_is_not_bound_to_another_qualifier(self):
        old_en = (
            'In the single evaluated seed, Analysis A showed a paired boundary error of 0.70 px. '
            'Evaluated in the single evaluated seed, Analysis A showed a paired boundary error of 0.80 px.'
        )
        new_en = (
            'In the single evaluated seed, Analysis A showed a paired boundary error of 0.70 px. '
            'Analysis A showed a paired boundary error of 0.80 px.'
        )
        old_zh = '在单个评估种子中，分析 A 显示 paired 边界误差 0.70 px。在单个评估种子中，分析 A 显示 paired 边界误差 0.80 px。'
        new_zh = '在单个评估种子中，分析 A 显示 paired 边界误差 0.70 px。分析 A 显示 paired 边界误差 0.80 px。'
        self._write_qualifier_triplet(old_en, new_en, old_zh, new_zh)
        self._run_verify()

    def test_same_heading_unchanged_declaration_is_included_but_draft(self):
        key = 'Results_EN.md'
        old = '# Results\n\nIn the single evaluated seed, Analysis A achieved 0.72.\n\nIn the single evaluated seed, Analysis A reached 0.74.\n'
        new = old.replace('In the single evaluated seed, Analysis A reached', 'Analysis A reached')
        (self.before/key).write_bytes(old.encode())
        (self.after/key).write_bytes(new.encode())
        draft, _, _ = scaffold.build_review_bundle(self.before, self.after)
        self.assertIn('0.72', draft['claims'][0]['candidate'][0]['text'])
        self.assertEqual(draft['review_status']['state'], 'draft')
        self._run_verify()

    def test_default_never_certifies_deleted_unique_verbal_fact(self):
        (self.before/'Results_EN.md').write_bytes(b'# Results\n\nAnalysis A detected edema and showed no benefit.\n')
        (self.after/'Results_EN.md').write_bytes(b'# Results\n\nAnalysis A showed no benefit.\n')
        result = scaffold.write_review_bundle(self.before, self.after, self.root/'draft.json', self.root/'changes.json', verify=True)
        self.assertIn('generated placeholders', str(result['compare']['errors']))
        draft = json.loads((self.root/'draft.json').read_text(encoding='utf-8'))
        self.assertNotIn('Completed', draft['narrative']['summary'])
        self.assertTrue(all(x.startswith('DRAFT') for x in draft['reviewers'].values()))

    def test_bounded_seed_alias_and_ordinal_paraphrases(self):
        for old, new in [('Analysis A used a single evaluated seed and achieved 0.72.', 'Analysis A used one evaluated seed and achieved 0.72.'),
                         ('Analysis A first achieved 0.72.', 'Analysis A 1st achieved 0.72.')]:
            (self.before/'Results_EN.md').write_bytes(('# Results\n\n'+old+'\n').encode())
            (self.after/'Results_EN.md').write_bytes(('# Results\n\n'+new+'\n').encode())
            self._run_verify()

    def _write_qualifier_triplet(self, old_en, new_en, old_zh, new_zh):
        for folder, en, zh in [(self.before, old_en, old_zh), (self.after, new_en, new_zh)]:
            for lang, body in [('EN', en), ('ZH', zh), ('EN_ZH', en+'\n\n'+zh)]:
                (folder/('Results_'+lang+'.md')).write_bytes(('# Results\n\n'+body+'\n').encode('utf-8'))

    def test_do_not_prespecified_inferential_phrase_matches_without_form(self):
        without_threshold = 'Analysis A reported 0.40 without a prespecified inferential threshold.'
        do_not_threshold = 'Analysis A reported 0.40 and did not use a prespecified inferential threshold.'
        no_testing = 'Analysis A reported 0.40 with no inferential testing.'
        self.assertTrue(edit._evidence_equal(edit._tokens(without_threshold), edit._tokens(do_not_threshold)))
        self.assertFalse(edit._evidence_equal(edit._tokens(without_threshold), edit._tokens(no_testing)))
        self.assertFalse(edit._evidence_equal(edit._tokens('Analysis A reported 0.40.'), edit._tokens('Analysis A reported not 0.40.')))
        old_zh = '分析 A 报告 0.40，无预设推断阈值。'
        new_zh = '分析 A 报告 0.40，且未使用预设推断阈值。'
        self._write_qualifier_triplet(without_threshold, do_not_threshold, old_zh, new_zh)
        self._run_verify()

    def test_multiple_negation_surfaces_collapse_without_exhausting_fact_anchors(self):
        old_en = ('Analysis A did not extend the descriptive comparison, without providing '
                  'a direct substitute for diagnosis-specific validation here.')
        new_en = ('Analysis A did not extend the descriptive comparison and do not provide '
                  'a direct substitute for diagnosis-specific validation here.')
        old_zh = '分析 A 未超出描述性比较，也未直接替代诊断特异性验证。'
        new_zh = '分析 A 仍限于描述性比较，且不能直接替代诊断特异性验证。'
        self._write_qualifier_triplet(old_en, new_en, old_zh, new_zh)
        draft, _, _ = scaffold.build_review_bundle(self.before, self.after)
        self.assertEqual(draft['review_status']['state'], 'draft')
        self.assertTrue(all(x.startswith('DRAFT') for x in draft['reviewers'].values()))
        claim = draft['claims'][0]
        negative = next(f for f in claim['facts'] if {s['text'] for s in f['source']} == {'not', 'without'})
        self.assertEqual([s['text'] for s in negative['candidate']], ['not', 'not'])
        combined = next(t for t in claim['translations'] if t['language'] == 'EN_ZH')
        linked = next(f for f in combined['facts'] if f['fact'] == negative['id'])
        self.assertEqual([s['text'] for s in linked['source']], ['not', 'without'])
        self.assertEqual([s['text'] for s in linked['candidate']], ['not', 'not'])
        self._run_verify()

    def test_native_chinese_qualifier_synonyms_are_all_mapped_with_context(self):
        old_en = 'Analysis A reported single-seed calibration and single evaluated seed discrimination.'
        new_en = 'Analysis A reported single-seed calibration and single-seed discrimination.'
        old_zh = '分析 A 报告单随机种子校准及单个评估种子判别。'
        new_zh = '分析 A 报告单随机种子校准及单随机种子判别。'
        self._write_qualifier_triplet(old_en, new_en, old_zh, new_zh)
        review_path, _, _, _ = self._run_verify()
        claim = json.loads(review_path.read_text(encoding='utf-8'))['claims'][0]
        seed = next(f for f in claim['facts'] if f['kind'] == 'qualifier')
        self.assertEqual([s['text'] for s in seed['source']], ['single-seed', 'single evaluated seed'])
        self.assertEqual([s['text'] for s in seed['candidate']], ['single-seed', 'single-seed'])
        for translation in claim['translations']:
            linked = next(f for f in translation['facts'] if f['fact'] == seed['id'])
            zh_source = [s['text'] for s in linked['source'] if '种子' in s['text']]
            zh_candidate = [s['text'] for s in linked['candidate'] if '种子' in s['text']]
            self.assertEqual(zh_source, ['单随机种子', '单个评估种子'])
            self.assertEqual(zh_candidate, ['单随机种子', '单随机种子'])
            for side in ('source', 'candidate'):
                self.assertTrue(all(edit._inside(s, [c[side] for c in linked['context']]) for s in linked[side]))

    def test_canonical_pairing_rejects_distinct_added_or_deleted_states_in_each_language(self):
        old_en = 'Analysis A reported curves with no inferential testing.'
        old_zh = '分析 A 报告曲线，未进行推断检验（no inferential testing）。'
        for language in ('EN', 'ZH', 'EN_ZH'):
            for replacement in ('no inferential ranking', 'no inferential testing and descriptive', ''):
                with self.subTest(language=language, replacement=replacement):
                    self._write_qualifier_triplet(old_en, old_en, old_zh, old_zh)
                    path = self.after/('Results_'+language+'.md')
                    path.write_bytes(path.read_bytes().replace(b'no inferential testing', replacement.encode()))
                    with self.assertRaisesRegex(ValueError, '[Ee]vidence mismatch'):
                        scaffold.build_review_bundle(self.before, self.after)

    def test_one_evaluated_run_spellings_share_one_state(self):
        state = {(6, 'single-run')}
        for phrase in (
            'single evaluated seed', 'one evaluated seed', 'single run', 'single-run',
            'single evaluated run', 'one evaluated run', 'single evaluated reader',
            'one evaluated fold', '单种子', '单次运行', '单个评估读者',
        ):
            self.assertEqual(edit._tokens(phrase), state, phrase)
        self.assertNotIn((6, 'single-run'), edit._tokens('single fold change'))
        self.assertNotIn((6, 'single-run'), edit._tokens('a single dose'))

    def test_repeated_reader_opener_uses_the_same_run_scope(self):
        old = (
            '# Results\n\n'
            'In the single evaluated reader, Analysis A had sensitivity 0.91.\n\n'
            'In the single evaluated reader, Analysis A had specificity 0.88.\n'
        )
        new = old.replace(
            'In the single evaluated reader, Analysis A had specificity',
            'Analysis A had specificity',
        )
        (self.before/'Results_EN.md').write_bytes(old.encode())
        (self.after/'Results_EN.md').write_bytes(new.encode())
        draft, _, _ = scaffold.build_review_bundle(self.before, self.after)
        self.assertIn('0.91', draft['claims'][0]['candidate'][0]['text'])
        self._run_verify()

    def test_sole_evaluated_seed_chinese_particle_is_a_bounded_alias(self):
        en = 'Analysis A reported single evaluated seed calibration.'
        old_zh = '分析 A 报告唯一接受评价种子中的校准结果。'
        new_zh = '分析 A 在唯一接受评价的种子中报告校准结果。'
        self._write_qualifier_triplet(en, en, old_zh, new_zh)
        self._run_verify()
        for phrase in ('唯一接受评价种子', '唯一接受评价的种子'):
            self.assertEqual(edit._tokens(phrase), {(6, 'single-run')})
            self.assertFalse(edit._evidence_equal(edit._tokens(phrase), edit._tokens('两个接受评价的种子')))

    def test_sole_evaluated_seed_chinese_alias_cannot_govern_multiple_seeds(self):
        for language in ('ZH', 'EN_ZH'):
            for phrase in ('唯一接受评价种子', '唯一接受评价的种子'):
                with self.subTest(language=language, phrase=phrase):
                    rationale = self._cross_scope(bilingual=True)
                    request = next(r for r in rationale['scope_declaration_requests'] if r['id'] == 'D_'+language)
                    old = request['declaration']['text']
                    changed = old.replace('单个评估种子', phrase).replace('seed 0', 'seed 0 和 seed 1')
                    request['declaration']['text'] = changed
                    for folder in (self.before, self.after):
                        path = folder/('Methods_'+language+'.md')
                        path.write_bytes(path.read_bytes().replace(old.encode(), changed.encode()))
                    with self.assertRaisesRegex(AssertionError, 'multiple/ranged seed'):
                        self._run_verify(rationale)

    def test_finalized_gate_rejects_new_negation_and_opposite_qualifier_states(self):
        key = 'Results_EN.md'
        for old, new, anchor in [
                ('Analysis A MAE was 0.4 px.', 'Analysis A MAE was NOT 0.4 px.', '0.4 px'),
                ('Analysis A improved accuracy to 0.9.', 'Analysis A did not improve accuracy to 0.9.', '0.9'),
                ('Analysis A was descriptive.', 'Analysis A was not descriptive.', 'descriptive')]:
            before, after = '# Results\n\n'+old+'\n', '# Results\n\n'+new+'\n'
            (self.before/key).write_bytes(before.encode())
            (self.after/key).write_bytes(after.encode())
            def sp(text, needle):
                return scaffold.resolve_exact_span({key: text}, {'file': key, 'text': needle})
            src, dst = sp(before, old), sp(after, new)
            pair = {'source': sp(before, 'Analysis A'), 'candidate': sp(after, 'Analysis A')}
            reviewer = 'Synthetic final-gate reviewer'
            claim = {'id': 'C1', 'reviewed_by': reviewer, 'source': [src], 'candidate': [dst],
                'scope': [dict(pair, axis='analysis')], 'provenance': [pair], 'translations': [],
                'facts': [{'id': 'value', 'kind': 'result', 'source': [sp(before, anchor)], 'candidate': [sp(after, anchor)],
                           'context': [{'source': src, 'candidate': dst, 'scope': [0]}]}]}
            review = {'schema_version': 1, 'reviewers': dict.fromkeys(('editor', 'scientific', 'bilingual'), reviewer),
                'inventory': {key: {'source_sha256': edit._sha(before.encode()), 'candidate_sha256': edit._sha(after.encode())}},
                'claims': [claim], 'unknowns': [],
                'review_status': {'state': 'reviewed', 'reviewed_by': reviewer, 'rationale': 'Synthetic finalized review negative control.',
                    'facts': [{'claim': 'C1', 'source': [src], 'candidate': [dst], 'reason': 'Synthetic attempted assertion reversal.'}]},
                'narrative': {'reviewed_by': reviewer, 'source': [src], 'candidate': [dst], 'summary': 'Synthetic negative control.',
                    'issues': [{'id': 'N1', 'kind': 'synthetic', 'source': [src], 'candidate': [dst], 'decision': 'resolved',
                                'central': False, 'reviewed_by': reviewer, 'reason': 'Synthetic negative control.'}]}}
            path = self.root/'finalized-negative.json'
            path.write_text(json.dumps(review), encoding='utf-8')
            errors = edit.compare_paths(self.before, self.after, path)['errors']
            self.assertIn('Claim numeric/citation/unit/negative/CI evidence changed', str(errors))

    def test_chinese_enrollment_is_not_group_owner_and_newline_hint(self):
        (self.before/'Results_EN.md').write_bytes(b'# Results\n\nCohort A included 120 eyes.\n')
        (self.after/'Results_EN.md').write_bytes(b'# Results\n\nCohort A enrolled 120 eyes.\n')
        (self.before/'Results_ZH.md').write_bytes('# 结果\n\n队列 A 纳入120只眼。\n'.encode('utf-8'))
        (self.after/'Results_ZH.md').write_bytes('# 结果\n\n队列 A 入组120只眼。\n'.encode('utf-8'))
        self._run_verify()
        self.assertEqual(edit._named_scopes('入组120只眼'), {})
        self.assertEqual(edit._named_scopes('组120为参照组'), {'population': {'group 120'}})
        path = self.after/'Results_EN.md'
        path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        with self.assertRaisesRegex(ValueError, 'LF/CRLF'):
            scaffold.build_review_bundle(self.before, self.after)

    def test_same_heading_folds_across_intervening_paragraph_and_contradicted_noninferential(self):
        old_en = (
            '## Discussion\n\n'
            'In the single evaluated seed, Analysis A preserved boundary accuracy at 0.962 (Fig. 3D).\n\n'
            'Literature context compared prior transfer methods across cohorts (PMID: 12345678).\n\n'
            'In the single evaluated seed, Analysis A did not establish a localization advantage in this non-inferential comparison (permutation P = 0.124).\n'
        )
        new_en = (
            '## Discussion\n\n'
            'In the single evaluated seed, Analysis A preserved boundary accuracy at 0.962 (Fig. 3D).\n\n'
            'Literature context compared prior transfer methods across cohorts (PMID: 12345678).\n\n'
            'Analysis A did not establish a localization advantage in this comparison (permutation P = 0.124).\n'
        )
        old_zh = (
            '## 讨论\n\n'
            '在唯一接受评价的种子中，分析 A 在 0.962 处保持边界准确性（图 3D）。\n\n'
            '文献背景跨队列比较了既有迁移方法（PMID: 12345678）。\n\n'
            '在唯一接受评价的种子中，分析 A 在该非推断性比较（non-inferential）中未建立定位优势（permutation P = 0.124）。\n'
        )
        new_zh = (
            '## 讨论\n\n'
            '在唯一接受评价的种子中，分析 A 在 0.962 处保持边界准确性（图 3D）。\n\n'
            '文献背景跨队列比较了既有迁移方法（PMID: 12345678）。\n\n'
            '分析 A 在该比较中未建立定位优势（permutation P = 0.124）。\n'
        )
        old_ez = (
            '## Discussion / 讨论\n\n'
            'In the single evaluated seed, Analysis A preserved boundary accuracy at 0.962 (Fig. 3D).\n\n'
            '在唯一接受评价的种子中，分析 A 在 0.962 处保持边界准确性（图 3D）。\n\n'
            'Literature context compared prior transfer methods across cohorts (PMID: 12345678).\n\n'
            '文献背景跨队列比较了既有迁移方法（PMID: 12345678）。\n\n'
            'In the single evaluated seed, Analysis A did not establish a localization advantage in this non-inferential comparison (permutation P = 0.124).\n\n'
            '在唯一接受评价的种子中，分析 A 在该非推断性比较（non-inferential）中未建立定位优势（permutation P = 0.124）。\n'
        )
        new_ez = (
            '## Discussion / 讨论\n\n'
            'In the single evaluated seed, Analysis A preserved boundary accuracy at 0.962 (Fig. 3D).\n\n'
            '在唯一接受评价的种子中，分析 A 在 0.962 处保持边界准确性（图 3D）。\n\n'
            'Literature context compared prior transfer methods across cohorts (PMID: 12345678).\n\n'
            '文献背景跨队列比较了既有迁移方法（PMID: 12345678）。\n\n'
            'Analysis A did not establish a localization advantage in this comparison (permutation P = 0.124).\n\n'
            '分析 A 在该比较中未建立定位优势（permutation P = 0.124）。\n'
        )
        for name, data in [('Discussion_EN.md', old_en), ('Discussion_ZH.md', old_zh), ('Discussion_EN_ZH.md', old_ez)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Discussion_EN.md', new_en), ('Discussion_ZH.md', new_zh), ('Discussion_EN_ZH.md', new_ez)]:
            (self.after / name).write_bytes(data.encode('utf-8'))
        self._run_verify()

    def test_same_heading_named_seed_governs_following_single_run_paragraph(self):
        old_en = (
            '### 3.5.1 Representation probe\n\n'
            'Representation comparisons in seed 0 showed BACC 0.953 (Fig. 6A).\n\n'
            'In the same single evaluated seed, source-dataset AUROC was 0.827 (Fig. 6B).\n'
        )
        new_en = (
            '### 3.5.1 Representation probe\n\n'
            'Representation comparisons in seed 0 showed BACC 0.953 (Fig. 6A).\n\n'
            'Source-dataset AUROC was 0.827 (Fig. 6B).\n'
        )
        old_zh = (
            '### 3.5.1 表示探针\n\n'
            '在种子 0 中，表示比较显示 BACC 为 0.953（图 6A）。\n\n'
            '在同一唯一接受评价的种子中，来源数据集 AUROC 为 0.827（图 6B）。\n'
        )
        new_zh = (
            '### 3.5.1 表示探针\n\n'
            '在种子 0 中，表示比较显示 BACC 为 0.953（图 6A）。\n\n'
            '来源数据集 AUROC 为 0.827（图 6B）。\n'
        )
        old_ez = (
            '### 3.5.1 Representation probe\n**3.5.1 表示探针**\n\n'
            'Representation comparisons in seed 0 showed BACC 0.953 (Fig. 6A).\n\n'
            '在种子 0 中，表示比较显示 BACC 为 0.953（图 6A）。\n\n'
            'In the same single evaluated seed, source-dataset AUROC was 0.827 (Fig. 6B).\n\n'
            '在同一唯一接受评价的种子中，来源数据集 AUROC 为 0.827（图 6B）。\n'
        )
        new_ez = (
            '### 3.5.1 Representation probe\n**3.5.1 表示探针**\n\n'
            'Representation comparisons in seed 0 showed BACC 0.953 (Fig. 6A).\n\n'
            '在种子 0 中，表示比较显示 BACC 为 0.953（图 6A）。\n\n'
            'Source-dataset AUROC was 0.827 (Fig. 6B).\n\n'
            '来源数据集 AUROC 为 0.827（图 6B）。\n'
        )
        for name, data in [('Results_EN.md', old_en), ('Results_ZH.md', old_zh), ('Results_EN_ZH.md', old_ez)]:
            (self.before / name).write_bytes(data.encode('utf-8'))
        for name, data in [('Results_EN.md', new_en), ('Results_ZH.md', new_zh), ('Results_EN_ZH.md', new_ez)]:
            (self.after / name).write_bytes(data.encode('utf-8'))
        self._run_verify()


if __name__ == '__main__':
    unittest.main()
