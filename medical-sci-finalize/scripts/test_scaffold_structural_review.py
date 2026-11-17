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


if __name__ == '__main__':
    unittest.main()
