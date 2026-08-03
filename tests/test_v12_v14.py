import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from audit_trigger import check_same_type_persist, recommend_conclusion  # noqa: E402
from checklist_compare import compare_code, run_test  # noqa: E402
from complexity_classify import classify  # noqa: E402
from convergence_check import convergence_verdict  # noqa: E402
from evidence import (canonicalize_feedback, evidence, requirement_record,
                      validate_requirement_evidence)  # noqa: E402
from finding import validate_finding  # noqa: E402
from validation_prompt_assembler import build_packet, select_roles  # noqa: E402


class ImprovementPlanTests(unittest.TestCase):
    def test_test_cmd_is_not_executed_by_default(self):
        passed, output = run_test("python -c \"raise SystemExit(9)\"", 2)
        self.assertIsNone(passed)
        self.assertIn("NOT_EXECUTED", output)

    def test_test_cmd_rejects_shell_control(self):
        passed, output = run_test("pytest tests ; echo unsafe", 2,
                                 execute=True, authorized=True, trusted_source=True)
        self.assertIsNone(passed)
        self.assertIn("REJECTED", output)

    def test_unexecuted_command_has_non_timeout_reason(self):
        result = compare_code(
            [{"id": "R1", "description": "run tests", "test_cmd": "pytest tests"}],
            "artifact", None, 2,
        )
        reason = result["unverified"][0]["reason"]
        self.assertIn("待宿主授权执行", reason)
        self.assertNotIn("测试超时", reason)

    def test_keyword_match_is_unverified(self):
        result = compare_code(
            [{"id": "R1", "description": "token refresh", "test_cmd": None}],
            "token refresh is mentioned", None, 2,
        )
        self.assertEqual(result["summary"]["covered"], 0)
        self.assertEqual(result["summary"]["unverified"], 1)
        self.assertEqual(result["requirement_evidence"][0]["status"], "unverified")

    def test_convergence_requires_evidence_ledger(self):
        state = {"round": 2, "nmax": 5, "rounds": [
            {"n": 1, "feedback": {"e_missing": [], "e_extra": [], "e_wrong": []}},
            {"n": 2, "feedback": {"e_missing": [], "e_extra": [], "e_wrong": []}},
        ]}
        result = convergence_verdict(state)
        self.assertNotEqual(result["status"], "converged")
        self.assertFalse(result["delivery_allowed"])

    def test_high_residual_cannot_converge(self):
        state = {
            "round": 1, "nmax": 5,
            "rounds": [{"n": 1, "feedback": {"e_missing": [], "e_extra": [], "e_wrong": []}}],
            "requirement_evidence": [requirement_record(
                "R1", "passed", [evidence("test", "ci", "pass")],
                [{"type": "A", "description": "API regression", "severity": "high"}],
            )],
        }
        self.assertNotEqual(convergence_verdict(state)["status"], "converged")

    def test_passed_without_evidence_is_invalid(self):
        issues = validate_requirement_evidence([
            {"requirement_id": "R1", "status": "passed", "evidence": [], "deviations": []}
        ])
        self.assertTrue(any("至少包含一条 evidence" in issue for issue in issues))

    def test_empty_ledger_is_invalid(self):
        for ledger in (None, []):
            issues = validate_requirement_evidence(ledger, ["R1"])
            self.assertTrue(issues)

    def test_init_requirements_file_populates_rt(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            requirements_path = directory / "requirements.json"
            state_path = directory / "state.json"
            requirements_path.write_text(
                json.dumps([{"id": "R1", "description": "pass the check"}]),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(TOOLS / "cybersyn_state.py"), "init",
                 "--level", "L3", "--task", "requirements test",
                 "--requirements", str(requirements_path),
                 "--output", str(state_path)],
                cwd=ROOT, env=os.environ.copy(), capture_output=True, text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["r_t"]["requirements"],
                             [{"id": "R1", "description": "pass the check"}])

    def test_partial_ledger_coverage_is_invalid(self):
        ledger = [requirement_record("R1", "passed", [evidence("test", "ci", "pass")])]
        issues = validate_requirement_evidence(ledger, ["R1", "R2"])
        self.assertTrue(any("R2" in issue for issue in issues))

    def test_duplicate_and_unknown_requirement_ids_are_invalid(self):
        record = requirement_record("R1", "passed", [evidence("test", "ci", "pass")])
        duplicate_issues = validate_requirement_evidence([record, record], ["R1"])
        self.assertTrue(any("R1" in issue for issue in duplicate_issues))
        unknown = requirement_record("R9", "passed", [evidence("test", "ci", "pass")])
        unknown_issues = validate_requirement_evidence([unknown], ["R1"])
        self.assertTrue(any("R9" in issue for issue in unknown_issues))

    def test_partial_ledger_blocks_convergence_and_delivery(self):
        state = {
            "round": 1, "nmax": 5, "rounds": [],
            "r_t": {"requirements": [{"id": "R1"}, {"id": "R2"}]},
            "requirement_evidence": [
                requirement_record("R1", "passed", [evidence("test", "ci", "pass")])
            ],
        }
        result = convergence_verdict(state)
        self.assertFalse(result["ledger_valid"])
        self.assertFalse(result["delivery_allowed"])
        self.assertNotEqual(result["status"], "converged")

    def test_evidence_requires_source_summary_and_timestamp(self):
        issues = validate_requirement_evidence([
            {"requirement_id": "R1", "status": "passed", "evidence": [{
                "kind": "test", "source": "", "summary": "", "captured_at": "bad-time"
            }], "deviations": []}
        ])
        self.assertGreaterEqual(len(issues), 3)

    def test_passed_with_blocking_deviation_is_invalid(self):
        issues = validate_requirement_evidence([
            {"requirement_id": "R1", "status": "passed",
             "evidence": [{"kind": "test", "source": "ci", "summary": "ok",
                           "captured_at": "2026-01-01T00:00:00+00:00"}],
             "deviations": [{"type": "B", "severity": "high", "description": "coverage gap"}]}
        ])
        self.assertTrue(any("阻断性偏差" in issue for issue in issues))

    def test_invalid_ledger_forces_delivery_false(self):
        state = {
            "round": 1, "nmax": 5, "rounds": [],
            "requirement_evidence": [{"requirement_id": "R1", "status": "passed",
                                       "evidence": [], "deviations": []}],
        }
        result = convergence_verdict(state)
        self.assertFalse(result["ledger_valid"])
        self.assertFalse(result["delivery_allowed"])

    def test_multiple_deviation_types_are_preserved(self):
        state = {
            "round": 1, "nmax": 5, "rounds": [],
            "requirement_evidence": [requirement_record(
                "R1", "unverified", [evidence("inspection", "log", "candidate")],
                [{"type": "B", "description": "coverage"},
                 {"type": "C", "description": "environment"}],
            )],
        }
        result = convergence_verdict(state)
        self.assertIn("unverified", result["reasons"][0])

    def test_legacy_singular_is_migrated_to_plural(self):
        feedback = canonicalize_feedback({"deviation_type": "A"})
        self.assertEqual(feedback, {"deviation_types": ["A"]})

    def test_stagnant_same_type_does_not_recommend_maintain(self):
        state = {"round": 2, "nmax": 5, "rounds": [
            {"n": 1, "feedback": {"e_wrong": [{"description": "same"}], "deviation_types": ["A"]}},
            {"n": 2, "feedback": {"e_wrong": [{"description": "same"}], "deviation_types": ["A"]}},
        ]}
        live = convergence_verdict(state)
        self.assertEqual(live["status"], "stagnant")
        self.assertTrue(check_same_type_persist(state)[0])
        self.assertEqual(recommend_conclusion(state, live)["recommended_conclusion"], "restructure")

    def test_classifier_has_uncertainty_not_probability(self):
        result = classify("improve the dynamic strategy", ["a.py", "b.js", "c.py"], [])
        self.assertNotIn("confidence", result)
        self.assertIn("uncertainties", result)

    def test_prompt_packet_excludes_peer_context_and_is_read_only(self):
        packet = build_packet(
            "measurement", "check output", ["R1"], [],
            [{"nested": {
                "expected_answer": "SECRET_EXPECTED",
                "primary_diagnosis": {"value": "SECRET_DIAGNOSIS"},
                "proposed_fix": [{"value": "SECRET_FIX"}],
                "peer_outputs": [{"claim": "SECRET_PEER"}],
                "keep": "artifact",
            }}],
            [{"nested": {
                "expected_answer": "SECRET_EXPECTED_2",
                "primary_diagnosis": "SECRET_DIAGNOSIS_2",
                "proposed_fix": "SECRET_FIX_2",
                "peer_outputs": [{"claim": "SECRET_PEER_2"}],
                "keep": "evidence",
            }}],
        )
        serialized = json.dumps(packet, ensure_ascii=False)
        self.assertEqual(packet["authority"], "read-only")
        self.assertEqual(
            packet["excluded_context"],
            ["expected_answer", "primary_diagnosis", "proposed_fix", "peer_outputs"],
        )
        for secret in (
            "SECRET_EXPECTED", "SECRET_DIAGNOSIS", "SECRET_FIX", "SECRET_PEER",
            "SECRET_EXPECTED_2", "SECRET_DIAGNOSIS_2", "SECRET_FIX_2", "SECRET_PEER_2",
        ):
            self.assertNotIn(secret, serialized)
        self.assertEqual(sorted(packet["sanitized_fields"]), sorted(packet["excluded_context"]))

    def test_audit_confidence_uses_evidence_quality_labels(self):
        states = [
            {"round": 0, "rounds": []},
            {"round": 1, "rounds": [{"n": 1, "feedback": {"deviation_types": ["D"]}}]},
            {"round": 1, "rounds": [{"n": 1, "feedback": {"deviation_types": ["C"]}}]},
        ]
        for state in states:
            confidence = recommend_conclusion(state)["confidence"]
            self.assertIn(confidence, {"high", "medium", "low"})

    def test_finding_without_evidence_cannot_block_delivery(self):
        finding, issues = validate_finding({
            "finding_id": "F1", "claim": "claim", "supporting_evidence": [],
            "counterevidence": [], "affected_requirements": ["R1"],
            "deviation_types": ["B"], "severity": "high", "confidence": "high",
            "proposed_test": "test", "blocking_delivery": True,
        }, ["R1"])
        self.assertTrue(issues)
        self.assertEqual(finding["status"], "unverified")
        self.assertFalse(finding["blocking_delivery"])

    def test_l2_risk_selects_measurement(self):
        self.assertEqual(select_roles("L2", {"unverified": True}), ["measurement"])

    def test_finding_unknown_requirement_is_preserved_as_issue(self):
        _, issues = validate_finding({
            "finding_id": "F2", "claim": "claim",
            "supporting_evidence": [{"source": "log:1"}], "counterevidence": [],
            "affected_requirements": ["R9"], "deviation_types": [], "severity": "low",
            "confidence": "medium", "proposed_test": "test", "blocking_delivery": False,
        }, ["R1"])
        self.assertTrue(any("R9" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
