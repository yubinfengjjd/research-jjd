"""Guard against policy contradictions; these tests do not score manuscript prose.

Scientific preservation and scope behavior are tested by the evidence-edit suites.
This file checks that maintained instructions do not reintroduce audited mechanical
writing requirements or contradict the common policy through a second entrypoint.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRITING = tuple(f"medical-sci-{name}" for name in (
    "methods", "results", "legends", "introduction", "discussion", "abstract",
))


def active_documents():
    for skill in (*WRITING, "medical-sci-finalize"):
        yield ROOT / skill / "SKILL.md"
        names = ("polish-rules.md", "journal-style.md", "examples.md") if skill.endswith("finalize") else (
            "writing-rules.md", "journal-style.md", "examples.md",
        )
        for name in names:
            yield ROOT / skill / "references" / name


class LanguageContract(unittest.TestCase):
    def assert_no_policy(self, paths, patterns):
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for pattern in patterns:
                with self.subTest(path=path.relative_to(ROOT), pattern=pattern):
                    self.assertIsNone(re.search(pattern, text, flags=re.I), "Conflicting policy in " + str(path))

    def test_entrypoints_route_to_one_existing_common_policy(self):
        for skill in (*WRITING, "medical-sci-finalize"):
            path = ROOT / skill / "SKILL.md"
            targets = re.findall(r"\]\(([^)]+positioning\.md)(?:#[^)]*)?\)", path.read_text(encoding="utf-8"))
            with self.subTest(skill=skill):
                self.assertTrue(targets, "Missing shared policy route")
                for target in targets:
                    self.assertEqual((path.parent / target).resolve(), (ROOT / "medpaper-pipeline/references/positioning.md").resolve())
                    self.assertTrue((path.parent / target).is_file())

    def test_archived_prompts_are_not_runtime_read_requirements(self):
        for skill in WRITING:
            path = ROOT / skill / "SKILL.md"
            text = path.read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertIsNone(re.search(r"^\d+\. .*\]\(references/original-", text, re.M))
                self.assertRegex(text, r"原始提示词[^\n]*历史[^\n]*不是运行指令")
        self.assert_no_policy(active_documents(), (r"逐条对照原始提示词的要求",))

    def test_generic_style_counts_are_not_hard_gates(self):
        self.assert_no_policy(active_documents(), (
            r"(?:硬上限|硬顶)[^\n]{0,12}60\s*词",
            r"目标平均\s*18[–-]28",
            r"散文分号[^\n]{0,30}(?:为\s*ERROR|须清零)",
            r"散文分号链\s*0\s*处",
            r"保持[^\n]{0,20}平均句长[^\n]{0,20}18[–-]28",
        ))

    def test_citation_counts_do_not_override_support_mapping(self):
        self.assert_no_policy(active_documents(), (
            r"严禁单段[^\n]*引用[^\n]*≥\s*[234]",
            r"同一文献全文一般只[^\n]*一次",
            r"同一文献一般只在最相关处引一次",
            r"一个论断引\s*1[–-]3\s*篇",
        ))

    def test_panel_case_comes_from_the_actual_figure(self):
        self.assert_no_policy(active_documents(), (
            r"panel\s*字母一律大写",
            r"本项目成图(?:用|为)[^\n]*(?:小写|大写)",
        ))

    def test_scope_does_not_require_a_frozen_english_phrase(self):
        self.assert_no_policy(active_documents(), (
            r"(?:必须|须)[^\n]{0,80}(?:明确)?写出\s*`?in the single evaluated seed",
            r"单\s*(?:seed|种子)[^\n]{0,40}(?:口径|范围)写在句内",
        ))

    def test_abstract_content_is_not_selected_by_sentence_or_failure_quotas(self):
        paths = [ROOT / "medical-sci-abstract" / name for name in (
            "SKILL.md", "references/writing-rules.md", "references/journal-style.md",
        )]
        self.assert_no_policy(paths, (
            r"严格保持\s*4[–-]6",
            r"保持\s*`results-sentences`\s*在\s*4[–-]6",
            r"including all underperforming classes/cohorts",
            r"全部低于名义目标的诊断类别",
            r"若[^\n]*无预设统计检验[^\n]*须保留[^\n]*descriptively",
        ))

    def test_verified_full_text_and_text_only_results_are_not_prohibited(self):
        self.assert_no_policy(active_documents(), (
            r"摘要没有的数字不写",
            r"表格中也没有时，不写入正文",
            r"没有任何图表显示时不写",
        ))

    def test_local_document_links_resolve(self):
        for path in active_documents():
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+\.md)(?:#[^)]*)?\)", text):
                if re.match(r"^[a-z]+://", target, flags=re.I):
                    continue
                with self.subTest(path=path.relative_to(ROOT), target=target):
                    self.assertTrue((path.parent / target).is_file(), "Broken local document link")


if __name__ == "__main__":
    unittest.main()
