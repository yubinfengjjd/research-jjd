"""Run the split synthetic demo (train/val/test by patient) through real subprocesses.

Checks: patient split is disjoint, training never sees test IDs, best-val
checkpoint is the one reported, cases.jsonl reproduces the primary metric,
and the frozen test evaluator reloads the saved weights.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "assets" / "synthetic"
sys.path.insert(0, str(ROOT / "scripts"))
from medexp import stats  # noqa: E402


class SyntheticDemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="medexp-synth-")
        self.work = Path(self.tmp.name) / "w"
        shutil.copytree(DEMO, self.work, ignore=shutil.ignore_patterns("__pycache__"))

    def tearDown(self):
        self.tmp.cleanup()

    def py(self, *args, env=None):
        r = subprocess.run([sys.executable, *map(str, args)], cwd=self.work, capture_output=True, text=True,
                           encoding="utf-8", env={**os.environ, **(env or {})})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def audit(self, task):
        out = Path(self.tmp.name) / f"audit-{task}.json"
        self.py("audit_split.py", "--task", task, "--output", out)
        return json.loads(out.read_text(encoding="utf-8"))

    def train(self, task, seed=1):
        out = Path(self.tmp.name) / f"run-{task}-{seed}"
        out.mkdir()
        self.py("train.py", "--task", task, "--seed", seed, "--epochs", 25,
                env={"ME_RUN_ID": "r-test", "ME_PHASE": "matrix", "ME_OUTPUT_DIR": str(out)})
        return out

    def test_split_is_patient_disjoint_and_complete(self):
        for task in ("classification", "segmentation"):
            a = self.audit(task)
            groups = [set(s["group_ids"]) for s in a["splits"].values()]
            self.assertEqual(sum(map(len, groups)), 80)
            self.assertEqual(len(set().union(*groups)), 80)
            self.assertEqual(set(a["splits"]), {"train", "val", "test"})

    def test_training_reports_best_val_checkpoint_and_consistent_cases(self):
        for task, metric, statistic in (("classification", "accuracy", "mean_per_case"),
                                        ("segmentation", "dice", "mean_per_case")):
            out = self.train(task)
            result = json.loads((out / "result.json").read_text())
            events = [json.loads(x) for x in (out / "metrics.jsonl").read_text().splitlines()]
            best = max(e["value"] for e in events if e["metric"] == metric)
            self.assertAlmostEqual(result["metrics"][metric], best, places=12)
            cases = stats.read_cases(out / "cases.jsonl", statistic)
            stats.check_consistency(statistic, cases, result["metrics"][metric])
            val_ids = set(self.audit(task)["splits"]["val"]["group_ids"])
            self.assertEqual(set(cases), val_ids)

    def test_auroc_cases_are_valid_for_classification(self):
        out = self.train("classification")
        cases = stats.read_cases(out / "cases.jsonl", "binary_auroc")
        self.assertEqual({v[0] for v in cases.values()}, {0, 1})

    def test_frozen_test_evaluator_reloads_weights_on_test_ids_only(self):
        run = self.train("classification", seed=2)
        out = Path(self.tmp.name) / "test-out"
        out.mkdir()
        self.py("evaluate_test.py", "--task", "classification", "--run-dir", run, "--output", out)
        res = json.loads((out / "result.json").read_text())
        cases = stats.read_cases(out / "cases.jsonl", "mean_per_case")
        stats.check_consistency("mean_per_case", cases, res["metrics"]["accuracy"])
        self.assertEqual(set(cases), set(self.audit("classification")["splits"]["test"]["group_ids"]))

    def test_paired_bootstrap_detects_clear_and_null_effects(self):
        ids = [f"c{i}" for i in range(40)]
        better = [{i: 0.9 for i in ids}] * 3
        worse = [{i: 0.6 for i in ids}] * 3
        r = stats.paired_bootstrap("mean_per_case", better, worse, True, "mean", 300, 0.95, 1)
        self.assertGreater(r["ci_low"], 0.25)
        same = stats.paired_bootstrap("mean_per_case", worse, worse, True, "mean", 300, 0.95, 1)
        self.assertEqual((same["ci_low"], same["ci_high"]), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
