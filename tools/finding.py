#!/usr/bin/env python3
"""Mechanical validation for read-only audit Finding objects."""

from copy import deepcopy


REQUIRED_FIELDS = {
    "finding_id", "claim", "supporting_evidence", "counterevidence",
    "affected_requirements", "deviation_types", "severity", "confidence",
    "proposed_test", "blocking_delivery",
}
DEVIATION_TYPES = {"A", "B", "C", "D"}
SEVERITIES = {"critical", "high", "medium", "low"}
CONFIDENCE = {"high", "medium", "low"}


def _has_location(item) -> bool:
    if isinstance(item, str):
        return bool(item.strip())
    if not isinstance(item, dict):
        return False
    return any(isinstance(item.get(key), str) and item[key].strip()
               for key in ("source", "location", "path", "uri"))


def validate_finding(finding: dict, requirement_ids=None) -> tuple[dict, list[str]]:
    """Return a normalized finding and issues; no evidence means non-blocking unverified."""
    normalized = deepcopy(finding) if isinstance(finding, dict) else {}
    issues = []
    missing = REQUIRED_FIELDS - set(normalized)
    issues.extend(f"缺少字段: {field}" for field in sorted(missing))

    supporting = normalized.get("supporting_evidence")
    has_support = isinstance(supporting, list) and bool(supporting) and all(
        _has_location(item) for item in supporting
    )
    if not has_support:
        issues.append("supporting_evidence 缺少可定位证据")
        normalized["status"] = "unverified"
        normalized["blocking_delivery"] = False
    else:
        normalized.setdefault("status", "verified")

    affected = normalized.get("affected_requirements", [])
    if requirement_ids is not None:
        unknown = [rid for rid in affected if rid not in set(requirement_ids)]
        issues.extend(f"不存在的 requirement_id: {rid}" for rid in unknown)

    deviation_types = normalized.get("deviation_types", [])
    if not isinstance(deviation_types, list) or any(item not in DEVIATION_TYPES for item in deviation_types):
        issues.append("deviation_types 必须是 A/B/C/D 数组")
    if normalized.get("severity") not in SEVERITIES:
        issues.append(f"无效 severity: {normalized.get('severity')}")
    if normalized.get("confidence") not in CONFIDENCE:
        issues.append(f"无效 confidence: {normalized.get('confidence')}")
    if not isinstance(normalized.get("blocking_delivery"), bool):
        issues.append("blocking_delivery 必须是布尔值")

    if not has_support:
        normalized["blocking_delivery"] = False
    return normalized, issues


def validate_findings(findings, requirement_ids=None) -> tuple[list[dict], list[str]]:
    if not isinstance(findings, list):
        return [], ["Finding[] 必须是数组"]
    normalized = []
    issues = []
    for index, finding in enumerate(findings):
        item, item_issues = validate_finding(finding, requirement_ids)
        normalized.append(item)
        issues.extend(f"Finding[{index}]: {issue}" for issue in item_issues)
    return normalized, issues
