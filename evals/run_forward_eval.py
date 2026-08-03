#!/usr/bin/env python3
"""Run the forward-evaluation catalog against recorded Agent observations.

The runner does not invent task outcomes. With no observations it validates the
catalog and reports readiness. Observations are JSONL records with case_id,
variant, and the measured fields defined by the rubric.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


METRICS = [
    "task_completion_rate", "false_delivery_rate", "deviation_routing_accuracy",
    "regression_count", "user_interruptions", "total_rounds", "subagent_calls",
    "context_overhead",
]
VARIANTS = [
    "no-skill", "v1.2-evidence-only", "v1.3-single-auditor",
    "v1.3-multi-angle", "v1.4",
]
KNOWN_RULES = {
    "unverified_blocks_delivery",
    "template_prediction_is_evidence",
    "l1_subagent_calls",
    "auditor_write_authority",
}


def load_cases(root: Path) -> list[dict]:
    cases = []
    for path in sorted(root.rglob("*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            item = json.loads(line)
            item["_source"] = f"{path}:{line_no}"
            cases.append(item)
    ids = [c.get("id") for c in cases]
    duplicates = [case_id for case_id, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"重复 case id: {duplicates}")
    required = {"id", "level", "prompt", "acceptance", "tags"}
    for case in cases:
        missing = required - set(case)
        if missing:
            raise ValueError(f"{case.get('id', '?')} 缺少字段: {sorted(missing)}")
    return cases


def load_observations(path: Optional[Path]) -> list[dict]:
    if not path:
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def load_rubric(path: Optional[Path]) -> Optional[dict]:
    if not path:
        return None
    rubric = json.loads(path.read_text(encoding="utf-8"))
    required = {"required_metrics", "variants", "rules"}
    missing = required - set(rubric)
    if missing:
        raise ValueError(f"rubric 缺少字段: {sorted(missing)}")
    if not isinstance(rubric["required_metrics"], list) or not rubric["required_metrics"]:
        raise ValueError("rubric.required_metrics 必须是非空列表")
    unknown_metrics = set(rubric["required_metrics"]) - set(METRICS)
    if unknown_metrics:
        raise ValueError(f"rubric 包含未知 metric: {sorted(unknown_metrics)}")
    if rubric["variants"] != VARIANTS:
        raise ValueError("rubric.variants 必须与评测变体顺序一致")
    if not isinstance(rubric["rules"], dict):
        raise ValueError("rubric.rules 必须是对象")
    unknown_rules = set(rubric["rules"]) - KNOWN_RULES
    if unknown_rules:
        raise ValueError(f"rubric contains unknown rule: {sorted(unknown_rules)}")
    return rubric


def evaluate_rules(cases: list[dict], observations: list[dict], rules: dict) -> tuple[list[str], dict]:
    """Apply rubric rules to observations; rule failures block the report."""
    case_by_id = {case["id"]: case for case in cases}
    issues = []
    checks = {}
    boolean_rules = [
        ("unverified_blocks_delivery", "unverified_delivery_allowed",
         not rules["unverified_blocks_delivery"]),
        ("template_prediction_is_evidence", "template_prediction_counted_as_evidence",
         rules["template_prediction_is_evidence"]),
        ("auditor_write_authority", "auditor_write_authority",
         rules["auditor_write_authority"]),
    ]
    for rule_name, field, expected in boolean_rules:
        failures = []
        for row in observations:
            if field not in row:
                failures.append(f"{row.get('case_id')}/{row.get('variant')}: missing {field}")
            elif row[field] is not expected:
                failures.append(
                    f"{row.get('case_id')}/{row.get('variant')}: {field}={row[field]!r}, "
                    f"expected {expected!r}"
                )
        checks[rule_name] = {"passed": not failures, "failures": failures}
        issues.extend(f"rule {rule_name}: {failure}" for failure in failures)

    if "l1_subagent_calls" in rules:
        expected = rules["l1_subagent_calls"]
        failures = []
        checked = 0
        for row in observations:
            case = case_by_id.get(row.get("case_id"))
            if not case or case.get("level") != "L1":
                continue
            checked += 1
            if row.get("subagent_calls") != expected:
                failures.append(
                    f"{row.get('case_id')}/{row.get('variant')}: "
                    f"subagent_calls={row.get('subagent_calls')!r}, expected {expected!r}"
                )
        checks["l1_subagent_calls"] = {
            "passed": not failures, "checked": checked, "failures": failures,
        }
        issues.extend(f"rule l1_subagent_calls: {failure}" for failure in failures)
    return issues, checks


def summarize(cases: list[dict], observations: list[dict], rubric: Optional[dict] = None,
             contract_only: bool = False) -> dict:
    case_ids = {case["id"] for case in cases}
    variants = VARIANTS
    metrics = rubric["required_metrics"] if rubric else METRICS
    by_variant = defaultdict(list)
    issues = []
    for observation in observations:
        missing = {"case_id", "variant", "observation_kind"} - set(observation)
        if missing:
            issues.append(f"观测缺少字段: {sorted(missing)}")
        if observation.get("case_id") not in case_ids:
            issues.append(f"未知 case_id: {observation.get('case_id')}")
        if observation.get("variant") not in variants:
            issues.append(f"未知 variant: {observation.get('variant')}")
        by_variant[observation.get("variant")].append(observation)

    results = {}
    for variant in variants:
        rows = by_variant[variant]
        metric_rows = {}
        for metric in metrics:
            values = [row[metric] for row in rows if metric in row]
            metric_rows[metric] = {
                "observed": len(values),
                "values": values,
                "mean": (sum(values) / len(values) if values and all(isinstance(v, (int, float)) for v in values) else None),
            }
            if rubric and not contract_only and (not rows or len(values) != len(rows)):
                issues.append(
                    f"{variant}: metric {metric} 缺失观测值 "
                    f"({len(values)}/{len(rows)})"
                )
        results[variant] = {"observations": len(rows), "metrics": metric_rows}

    rule_issues, rule_checks = evaluate_rules(
        cases, observations, rubric["rules"] if rubric else {}
    )
    issues.extend(rule_issues)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "catalog": {
            "cases": len(cases),
            "levels": dict(Counter(case["level"] for case in cases)),
            "tags": dict(Counter(tag for case in cases for tag in case["tags"])),
        },
        "variants": results,
        "observations_provided": bool(observations),
        "issues": issues,
        "metrics": metrics,
        "rubric_loaded": rubric is not None,
        "evaluation_mode": "contract-only" if contract_only else "outcome",
        "observation_kinds": dict(Counter(row.get("observation_kind") for row in observations)),
        "rule_checks": rule_checks,
        "interpretation": (
            "仅完成评测目录校验；需要提供 observations 才能比较变体。"
            if not observations else (
                "仅执行显式 contract-only 契约检查；未提供完整结果指标。"
                if contract_only else "已汇总结果观测值；请结合 rubric 检查收益是否覆盖成本。"
            )
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Project Cybersyn v1.4 前向评测目录运行器")
    parser.add_argument("--cases", default=str(Path(__file__).parent / "cases"))
    parser.add_argument("--observations", help="观测结果 JSONL")
    parser.add_argument("--rubric", help="评测 rubric JSON")
    parser.add_argument("--contract-only", action="store_true",
                        help="仅校验契约字段；不要求 rubric 的结果指标齐全")
    parser.add_argument("--output", help="输出 JSON 文件")
    parser.add_argument("--format", default="json", choices=["json", "text"])
    args = parser.parse_args()
    try:
        rubric = load_rubric(Path(args.rubric) if args.rubric else None)
        report = summarize(
            load_cases(Path(args.cases)),
            load_observations(Path(args.observations) if args.observations else None),
            rubric,
            args.contract_only,
        )
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.format == "text":
            print(f"cases={report['catalog']['cases']} observations={report['observations_provided']} mode={report['evaluation_mode']}")
            print(f"levels={report['catalog']['levels']}")
            for variant, data in report["variants"].items():
                print(f"{variant}: {data['observations']} observations")
            if report["rule_checks"]:
                print("rules:")
                for name, check in report["rule_checks"].items():
                    print(f"  {name}: {'PASS' if check['passed'] else 'FAIL'}")
            if report["issues"]:
                print("issues:")
                for issue in report["issues"]:
                    print(f"  - {issue}")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["issues"]:
            sys.exit(1)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "code": 2}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
