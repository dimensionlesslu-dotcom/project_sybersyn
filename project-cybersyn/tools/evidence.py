#!/usr/bin/env python3
"""Shared evidence and deviation contracts for Project Cybersyn tools."""

from datetime import datetime, timezone


EVIDENCE_KINDS = {"test", "inspection", "source", "user-confirmation"}
REQUIREMENT_STATUSES = {"passed", "failed", "unverified", "blocked"}
DEVIATION_TYPES = {"A", "B", "C", "D"}
SEVERITIES = {"critical", "high", "medium", "low"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def evidence(kind: str, source: str, summary: str, captured_at: str = None) -> dict:
    """Create one traceable evidence record."""
    if kind not in EVIDENCE_KINDS:
        raise ValueError(f"未知 evidence kind: {kind}")
    record = {
        "kind": kind,
        "source": source,
        "summary": summary,
        "captured_at": captured_at or now_iso(),
    }
    issues = validate_evidence(record)
    if issues:
        raise ValueError("无效 evidence: " + "; ".join(issues))
    return record


def validate_evidence(record: dict) -> list[str]:
    """Validate one evidence record, including a parseable ISO-8601 timestamp."""
    if not isinstance(record, dict):
        return ["evidence 必须是对象"]
    issues = []
    if record.get("kind") not in EVIDENCE_KINDS:
        issues.append(f"无效 kind: {record.get('kind')}")
    for field in ("source", "summary", "captured_at"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            issues.append(f"缺少非空 {field}")
    if record.get("captured_at"):
        try:
            datetime.fromisoformat(record["captured_at"].replace("Z", "+00:00"))
        except (TypeError, ValueError):
            issues.append("captured_at 不是有效 ISO-8601 时间")
    return issues


def normalize_deviation(item: dict, default_type: str = "A") -> dict:
    """Normalize a deviation while preserving the original detail."""
    if not isinstance(item, dict):
        item = {"description": str(item)}
    normalized = dict(item)
    normalized.setdefault("type", default_type)
    normalized.setdefault("description", normalized.get("reason", "未命名偏差"))
    normalized.setdefault("severity", "medium")
    normalized.setdefault("confidence", "medium")
    if normalized["type"] not in DEVIATION_TYPES:
        raise ValueError(f"未知 deviation type: {normalized['type']}")
    if normalized["severity"] not in SEVERITIES:
        raise ValueError(f"未知 severity: {normalized['severity']}")
    return normalized


def deviation_types_from_feedback(feedback: dict) -> list[str]:
    """Read canonical plural types, accepting singular only for legacy input."""
    raw = feedback.get("deviation_types")
    if raw is None:
        raw = feedback.get("deviation_type")
    if isinstance(raw, str):
        raw = [raw]
    return list(dict.fromkeys(item for item in (raw or []) if item in DEVIATION_TYPES))


def canonicalize_feedback(feedback: dict) -> dict:
    """Migrate legacy singular deviation_type into the canonical plural field."""
    normalized = dict(feedback or {})
    types = deviation_types_from_feedback(normalized)
    if types:
        normalized["deviation_types"] = types
    normalized.pop("deviation_type", None)
    return normalized


def requirement_record(requirement_id: str, status: str, evidence_items=None,
                       deviations=None) -> dict:
    """Create one RequirementEvidence ledger entry."""
    if status not in REQUIREMENT_STATUSES:
        raise ValueError(f"未知 requirement status: {status}")
    return {
        "requirement_id": requirement_id,
        "status": status,
        "evidence": list(evidence_items or []),
        "deviations": [normalize_deviation(d) for d in (deviations or [])],
    }


def validate_requirement_evidence(records, requirement_ids=None) -> list[str]:
    issues = []
    if records is None:
        records = []
    elif not isinstance(records, list):
        return ["requirement_evidence 必须是数组"]
    expected_ids = list(requirement_ids) if requirement_ids is not None else None
    if not records and expected_ids:
        issues.append("requirement_evidence cannot be empty")
    if expected_ids is not None:
        expected_duplicates = sorted({rid for rid in expected_ids
                                      if expected_ids.count(rid) > 1})
        if expected_duplicates:
            issues.append(f"duplicate configured requirement_id: {expected_duplicates}")

    seen = set()
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            issues.append(f"requirement_evidence[{i}] 必须是对象")
            continue
        rid = record.get("requirement_id")
        if not rid:
            issues.append(f"requirement_evidence[{i}] 缺少 requirement_id")
        elif rid in seen:
            issues.append(f"requirement_evidence 重复 requirement_id: {rid}")
        seen.add(rid)
        status = record.get("status")
        if status not in REQUIREMENT_STATUSES:
            issues.append(f"{rid or i}: 无效 status {status}")
        if expected_ids is not None and rid not in set(expected_ids):
            issues.append(f"{rid or i}: 不存在的 requirement_id")
        if status == "passed" and not record.get("evidence"):
            issues.append(f"{rid or i}: passed 必须至少包含一条 evidence")
        for j, ev in enumerate(record.get("evidence", [])):
            issues.extend(
                f"{rid or i}.evidence[{j}]: {issue}"
                for issue in validate_evidence(ev)
            )
        deviations = record.get("deviations", [])
        if status == "passed" and any(
            d.get("type") in {"B", "C", "D"}
            or d.get("severity", "medium") in {"critical", "high", "medium"}
            for d in deviations if isinstance(d, dict)
        ):
            issues.append(f"{rid or i}: passed 不能同时包含阻断性偏差")
        for j, deviation in enumerate(deviations):
            try:
                normalize_deviation(deviation)
            except ValueError as exc:
                issues.append(f"{rid or i}.deviations[{j}]: {exc}")
    if expected_ids is not None:
        missing_ids = sorted(set(expected_ids) - seen)
        if missing_ids:
            issues.append(f"ledger missing requirement_id: {missing_ids}")
    return issues


def flatten_deviations(records) -> list[dict]:
    return [d for r in (records or []) for d in r.get("deviations", [])]


def blocking_deviations(records) -> list[dict]:
    """Return residuals that must prevent automatic convergence."""
    return [
        d for d in flatten_deviations(records)
        if d.get("type") in {"B", "C", "D"}
        or d.get("severity", "medium") in {"critical", "high", "medium"}
    ]


def evidence_summary(records) -> dict:
    records = records or []
    statuses = {status: 0 for status in REQUIREMENT_STATUSES}
    for record in records:
        status = record.get("status")
        if status in statuses:
            statuses[status] += 1
    return {
        "total": len(records),
        "statuses": statuses,
        "unverified": statuses["unverified"],
        "blocking_deviations": len(blocking_deviations(records)),
    }
