#!/usr/bin/env python3
"""Collect static contract observations, clearly separate from Agent performance data."""

import argparse
import json
from pathlib import Path

from run_forward_eval import VARIANTS, load_cases


def observe(case: dict, variant: str) -> dict:
    tags = set(case["tags"])
    risky = bool(tags.intersection({"security", "keyword-trap", "template", "residual", "regression", "D", "B"}))
    integration_risk = bool(tags.intersection({"integration", "regression", "D"}))
    high_level = case["level"] in {"L3", "L4"}
    if variant == "no-skill":
        false_delivery = 1.0 if risky else 0.0
        routing = 0.0
        subagents = 0
        overhead = 0
        regressions = 1 if integration_risk else 0
    else:
        false_delivery = 0.0
        routing = 1.0
        regressions = 0
        if variant == "v1.3-single-auditor":
            subagents = 1 if high_level else 0
        elif variant == "v1.3-multi-angle":
            subagents = 3 if case["level"] == "L4" else (2 if high_level else 0)
        elif variant == "v1.4":
            subagents = 1 if risky and high_level else 0
        else:
            subagents = 0
        overhead = subagents * 400
    return {
        "case_id": case["id"],
        "variant": variant,
        "observation_kind": "static-contract",
        "source": "collect_contract_observations.py",
        "false_delivery_rate": false_delivery,
        "deviation_routing_accuracy": routing,
        "regression_count": regressions,
        "subagent_calls": subagents,
        "context_overhead": overhead,
        "unverified_delivery_allowed": False,
        "template_prediction_counted_as_evidence": False,
        "auditor_write_authority": False,
    }


def main():
    parser = argparse.ArgumentParser(description="采集静态契约消融 observation")
    parser.add_argument("--cases", default=str(Path(__file__).parent / "cases"))
    parser.add_argument("--output", default=str(Path(__file__).parent / "observations" / "contract-harness.jsonl"))
    args = parser.parse_args()
    cases = load_cases(Path(args.cases))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for case in cases:
            for variant in VARIANTS:
                handle.write(json.dumps(observe(case, variant), ensure_ascii=False) + "\n")
    print(json.dumps({"status": "ok", "cases": len(cases), "observations": len(cases) * len(VARIANTS),
                      "kind": "static-contract", "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
