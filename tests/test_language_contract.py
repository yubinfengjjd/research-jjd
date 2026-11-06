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
