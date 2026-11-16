"""Unit tests for scaffold_structural_review.py against evidence_edit gates."""
from __future__ import annotations

import json
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
        summary = scaffold.write_review_bundle(
            self.before, self.after, review_path, changes_path, decisions_path,
            rationales=rationales, verify=True,
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

        _, _, _, summary = self._run_verify()
        self.assertEqual(summary['claims'], 1)

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


if __name__ == '__main__':
    unittest.main()
