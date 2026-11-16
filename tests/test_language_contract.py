"""Policy contradiction regression only; does not assess generated prose quality."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class LanguageContract(unittest.TestCase):
    def test_no_forced_paragraph_endings(self):
        for p in ROOT.glob("medical-sci-*/references/journal-style.md"):
            self.assertNotIn("段末句引出下一节点", p.read_text(encoding="utf-8"), str(p))
    def test_abstract_core_priority(self):
        s=(ROOT/"medical-sci-abstract/references/journal-style.md").read_text(encoding="utf-8")
        self.assertNotIn("族不能让",s)
        self.assertNotIn("其余族分句级简述",s)
        self.assertIn("不得省略会改变主结论的不利结果",s)
    def test_final_delivery_freshness_and_small_counts(self):
        s=(ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["SHA256","小于10","历史失败与当前候选失败分开报告","carried-forward"]:
            self.assertIn(phrase,s)
    def test_claim_strength_protected(self):
        s=(ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["no clear reduction","observed-class BACC","独有计数"]:
            self.assertIn(phrase,s)

    def test_review_version_binding(self):
        s=(ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["版本未核实", "已修复", "正式源稿未接入", "不得据此判定 AI 来源"]:
            self.assertIn(phrase, s)
        entry=(ROOT/"medical-sci-finalize/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("版本绑定与处置", entry)

    def test_abstract_checker_guidance_matches_priority(self):
        s=(ROOT/"medical-sci-abstract/scripts/check_abstract.py").read_text(encoding="utf-8")
        self.assertNotIn("whole families must not be dropped", s)
        self.assertIn("decisive adverse findings", s)
        self.assertIn("internal coverage table", s)

    def test_headline_first_and_meta_jargon_contract(self):
        polish = (ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["Headline-First", "structured method", "method carrier", "Highlights"]:
            self.assertIn(phrase, polish)
        abstract_rules = (ROOT/"medical-sci-abstract/references/writing-rules.md").read_text(encoding="utf-8")
        self.assertIn("Highlights 必须随摘要和正文同步重写打磨", abstract_rules)
        results_rules = (ROOT/"medical-sci-results/references/writing-rules.md").read_text(encoding="utf-8")
        self.assertIn("合并至单元或句末共享引用", results_rules)
        discussion_rules = (ROOT/"medical-sci-discussion/references/writing-rules.md").read_text(encoding="utf-8")
        self.assertIn("requiring prospective validation", discussion_rules)

    def test_cycle2_cross_cohort_structural_and_localization_contract(self):
        polish = (ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["Cross-Cohort & Classwise Audit", "append_only_author_files", "bilingual_sync_only"]:
            self.assertIn(phrase, polish)
        sr = (ROOT/"medical-sci-finalize/references/structural-review.md").read_text(encoding="utf-8")
        for phrase in ["heading_edits", "bilingual_sync_only", "append_only_author_files"]:
            self.assertIn(phrase, sr)
        results_rules = (ROOT/"medical-sci-results/references/writing-rules.md").read_text(encoding="utf-8")
        self.assertIn("跨队列与逐类别数据核对清单", results_rules)
        self.assertNotIn("不设机械引用密度或降幅配额", results_rules)
        for phrase in ["优先采用去重后的独立队列分母", "citation-adjacent-repeat", "citation-redundant-parent"]:
            self.assertIn(phrase, results_rules)

    def test_cycle3_parent_heading_atomic_review_and_zh_hygiene_contract(self):
        polish = (ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["performs on par", "five of six independent cohort groups", "seed-0", "atomic `facts`/`provenance` pairs", "所有可修复的 `WARN`"]:
            self.assertIn(phrase, polish)
        abstract_rules = (ROOT/"medical-sci-abstract/references/writing-rules.md").read_text(encoding="utf-8")
        for phrase in ["descriptively lower", "remained unresolved", "five of six independent cohort groups"]:
            self.assertIn(phrase, abstract_rules)
        discussion_rules = (ROOT/"medical-sci-discussion/references/writing-rules.md").read_text(encoding="utf-8")
        self.assertIn("seed-0", discussion_rules)

    def test_cycle4_mixed_seed_table_and_sentence_hygiene_contract(self):
        polish = (ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["分列标明", "Coverage point estimates exceed target...", "Stage-1", "18–28", "retrospective", "绝不按裸 `.` 截断小数"]:
            self.assertIn(phrase, polish)
        results_rules = (ROOT/"medical-sci-results/references/writing-rules.md").read_text(encoding="utf-8")
        for phrase in ["分列标明种子范围", "Stage-1", "AURC", "≥4 次"]:
            self.assertIn(phrase, results_rules)
        discussion_rules = (ROOT/"medical-sci-discussion/references/writing-rules.md").read_text(encoding="utf-8")
        for phrase in ["in the single evaluated seed", "sentence-average"]:
            self.assertIn(phrase, discussion_rules)

    def test_cycle5_single_seed_split_mapping_and_all_legends_contract(self):
        polish = (ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["在唯一接受评价的种子中", "不得只跑 `Figure_Legends`", "[para_1, para_2]", "without a prespecified inferential threshold"]:
            self.assertIn(phrase, polish)
        sr = (ROOT/"medical-sci-finalize/references/structural-review.md").read_text(encoding="utf-8")
        for phrase in ["[para_1, ..., para_k]", "in the single evaluated seed"]:
            self.assertIn(phrase, sr)

    def test_cycle9_column_mapping_all_subnominal_and_highlight_contract(self):
        polish = (ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["02_figures/out/tables/*.md", "pooled AURC", "0.5 像素 非劣效界值", "logit", "bootstrap", "Safe/clinical deployment requires prospective..."]:
            self.assertIn(phrase, polish)
        abstract_rules = (ROOT/"medical-sci-abstract/references/writing-rules.md").read_text(encoding="utf-8")
        for phrase in ["Abstract_EN_ZH.md", "Safe/clinical deployment requires prospective..."]:
            self.assertIn(phrase, abstract_rules)
        legends_rules = (ROOT/"medical-sci-legends/references/writing-rules.md").read_text(encoding="utf-8")
        for phrase in ["*.source.json", "pooled AURC", "and outline"]:
            self.assertIn(phrase, legends_rules)

    def test_cycle10_abstract_nouns_all_strata_and_merged_legend_scope(self):
        polish = (ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["negative differences with intervals crossing zero", "ST09.csv", "transport conditions", "learned_per_row.parquet"]:
            self.assertIn(phrase, polish)
        abstract_rules = (ROOT/"medical-sci-abstract/references/writing-rules.md").read_text(encoding="utf-8")
        self.assertIn("negative differences with intervals crossing zero", abstract_rules)
        legends_rules = (ROOT/"medical-sci-legends/references/writing-rules.md").read_text(encoding="utf-8")
        self.assertIn("(c, d)", legends_rules)

    def test_cycle11_point_estimate_modifier_scope_and_panel_attribution(self):
        polish = (ROOT/"medical-sci-finalize/references/polish-rules.md").read_text(encoding="utf-8")
        for phrase in ["same-backbone", "点估计", "前置统领修饰语"]:
            self.assertIn(phrase, polish)
        abstract_rules = (ROOT/"medical-sci-abstract/references/writing-rules.md").read_text(encoding="utf-8")
        for phrase in ["coverage point estimates exceeded 0.900", "总体 X 以及 [队列]的 Y", "同骨干"]:
            self.assertIn(phrase, abstract_rules)
        legends_rules = (ROOT/"medical-sci-legends/references/writing-rules.md").read_text(encoding="utf-8")
        self.assertIn("stacked-bar panel", legends_rules)
