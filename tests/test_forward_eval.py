import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "evals"))

from run_forward_eval import load_cases, load_observations, load_rubric, summarize  # noqa: E402


EVAL = ROOT / "evals" / "run_forward_eval.py"
CASES = ROOT / "evals" / "cases"
OBSERVATIONS = ROOT / "evals" / "observations" / "contract-harness.jsonl"
RUBRIC = ROOT / "evals" / "rubrics" / "default.json"


class ForwardEvalTests(unittest.TestCase):
    def test_missing_required_metrics_fails_outcome_mode(self):
        result = subprocess.run(
            [sys.executable, str(EVAL), "--cases", str(CASES),
             "--observations", str(OBSERVATIONS), "--rubric", str(RUBRIC),
             "--format", "text"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("task_completion_rate", result.stdout)
        self.assertIn("issues:", result.stdout)

    def test_contract_only_mode_is_explicit(self):
        result = subprocess.run(
            [sys.executable, str(EVAL), "--cases", str(CASES),
             "--observations", str(OBSERVATIONS), "--rubric", str(RUBRIC),
             "--contract-only", "--format", "json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"evaluation_mode": "contract-only"', result.stdout)

    def test_rubric_rule_failure_blocks_report(self):
        cases = load_cases(CASES)
        observations = load_observations(OBSERVATIONS)
        observations[0]["auditor_write_authority"] = True
        report = summarize(cases, observations, load_rubric(RUBRIC), contract_only=True)
        self.assertTrue(any("rule auditor_write_authority" in issue for issue in report["issues"]))
        self.assertFalse(report["rule_checks"]["auditor_write_authority"]["passed"])


if __name__ == "__main__":
    unittest.main()
