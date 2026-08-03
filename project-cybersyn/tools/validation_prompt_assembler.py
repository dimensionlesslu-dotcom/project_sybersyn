#!/usr/bin/env python3
"""Assemble read-only validation PromptPackets; never starts a subagent."""

import argparse
import json
import sys
import uuid
from pathlib import Path


ROLES = {
    "goal-spec": {
        "objective": "检验目标、验收标准和核心假设是否清晰、稳定且无冲突。",
        "failure_criteria": "发现目标漂移、隐含假设未声明或验收标准互相冲突。",
    },
    "measurement": {
        "objective": "检验证据、测试和覆盖范围是否足以支持结论。",
        "failure_criteria": "发现测量误差、覆盖缺口、不可复现输出或把候选匹配当成直接证据。",
    },
    "integration-regression": {
        "objective": "检验局部成功是否破坏接口、集成行为或既有回归约束。",
        "failure_criteria": "发现跨模块耦合、边界条件、回归或 A/B/C/D 偏差未被覆盖。",
    },
    "environment": {
        "objective": "按需检验版本、政策、资源和外部输入是否改变了任务前提。",
        "failure_criteria": "发现外部条件已变化、核心假设失效或结果无法迁移到当前环境。",
    },
}
LEVEL_PACKET_BUDGET = {"L1": 0, "L2": 1, "L3": 2, "L4": 3}
SENSITIVE_FIELDS = {"expected_answer", "primary_diagnosis", "proposed_fix", "peer_outputs"}


def sanitize_context(value, removed=None):
    """Recursively remove excluded context before packet storage or prompt rendering."""
    removed = removed if removed is not None else []
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if key in SENSITIVE_FIELDS:
                removed.append(key)
                continue
            clean[key] = sanitize_context(item, removed)
        return clean
    if isinstance(value, list):
        return [sanitize_context(item, removed) for item in value]
    return value


def _sanitize_inputs(task, acceptance, constraints, raw_artifacts, raw_evidence):
    removed = []
    bundle = sanitize_context({
        "task": task,
        "acceptance": acceptance,
        "constraints": constraints,
        "raw_artifacts": raw_artifacts,
        "raw_evidence": raw_evidence,
    }, removed)
    return bundle, sorted(set(removed))


def select_roles(level: str = None, risk_signals: dict = None, roles=None) -> list[str]:
    """Choose orthogonal views from risk signals, then apply the level budget."""
    explicit_roles = roles is not None
    if explicit_roles:
        selected = list(roles)
    else:
        signals = risk_signals or {}
        scores = {role: 0 for role in ROLES}
        if signals.get("unverified") or signals.get("B"):
            scores["measurement"] += 5
        if signals.get("cross_module") or signals.get("regression") or signals.get("D"):
            scores["integration-regression"] += 5
        if signals.get("goal_conflict") or signals.get("ambiguity"):
            scores["goal-spec"] += 5
        if signals.get("environment") or signals.get("C"):
            scores["environment"] += 5
        fallback = ["goal-spec", "measurement", "integration-regression", "environment"]
        selected = sorted(fallback, key=lambda role: (-scores[role], fallback.index(role)))
    if level is not None:
        if level not in LEVEL_PACKET_BUDGET:
            raise ValueError(f"未知复杂度层级: {level}")
        selected = selected[:LEVEL_PACKET_BUDGET[level]]
    elif not explicit_roles:
        selected = selected[:1]
    return selected


def _load_value(value: str):
    if value.startswith("@"):
        return json.loads(Path(value[1:]).read_text(encoding="utf-8"))
    return json.loads(value)


def build_packet(role: str, task: str, acceptance=None, constraints=None,
                 raw_artifacts=None, raw_evidence=None, max_findings: int = 5) -> dict:
    if role not in ROLES:
        raise ValueError(f"未知验证视角: {role}")
    if max_findings < 1:
        raise ValueError("max_findings 必须大于 0")
    spec = ROLES[role]
    clean, sanitized_fields = _sanitize_inputs(
        task, acceptance or [], constraints or [], raw_artifacts or [], raw_evidence or []
    )
    task = clean["task"]
    acceptance = clean["acceptance"]
    constraints = clean["constraints"]
    raw_artifacts = clean["raw_artifacts"]
    raw_evidence = clean["raw_evidence"]
    return {
        "packet_id": f"packet-{uuid.uuid4().hex[:12]}",
        "role": role,
        "task": task,
        "acceptance": list(acceptance or []),
        "constraints": list(constraints or []),
        "raw_artifacts": list(raw_artifacts or []),
        "raw_evidence": list(raw_evidence or []),
        "authority": "read-only",
        "excluded_context": [
            "expected_answer", "primary_diagnosis", "proposed_fix", "peer_outputs",
        ],
        "output_schema": "Finding[]",
        "budget": {"max_findings": max_findings},
        "sanitized_fields": sanitized_fields,
        "role_objective": spec["objective"],
        "failure_criteria": spec["failure_criteria"],
        "prompt": render_prompt(role, task, acceptance or [], constraints or [],
                                 raw_artifacts or [], raw_evidence or [], max_findings),
    }


def render_prompt(role: str, task: str, acceptance: list, constraints: list,
                  raw_artifacts: list, raw_evidence: list, max_findings: int) -> str:
    clean, _ = _sanitize_inputs(task, acceptance, constraints, raw_artifacts, raw_evidence)
    task = clean["task"]
    acceptance = clean["acceptance"]
    constraints = clean["constraints"]
    raw_artifacts = clean["raw_artifacts"]
    raw_evidence = clean["raw_evidence"]
    spec = ROLES[role]
    return (
        f"你是独立的 {role} 验证者。仅根据下面的原始任务、产物和证据进行检查。\n"
        "不要假设主 Agent 的诊断正确，不要为了反对而制造问题。每个结论必须引用可定位证据；"
        "没有直接证据时标记为待验证，并给出成本最低的区分性测试。\n"
        "你只有只读权限：不修改产物、不联系用户、不读取其他验证者的输出。\n\n"
        f"本视角目标：{spec['objective']}\n"
        f"失败判据：{spec['failure_criteria']}\n"
        f"原始任务：{task}\n"
        f"验收项：{json.dumps(acceptance, ensure_ascii=False)}\n"
        f"约束：{json.dumps(constraints, ensure_ascii=False)}\n"
        f"原始产物：{json.dumps(raw_artifacts, ensure_ascii=False)}\n"
        f"原始证据：{json.dumps(raw_evidence, ensure_ascii=False)}\n\n"
        "严格返回 Finding[]，每项包含 finding_id、claim、supporting_evidence、"
        "counterevidence、affected_requirements、deviation_types、severity、confidence、"
        f"proposed_test、blocking_delivery；最多 {max_findings} 项。"
    )


def assemble(task: str, acceptance, constraints, raw_artifacts, raw_evidence,
             roles=None, max_findings: int = 5, level: str = None,
             risk_signals: dict = None) -> list[dict]:
    selected = select_roles(level, risk_signals, roles)
    if len(selected) > 4:
        raise ValueError("最多组装 4 个正交视角")
    return [build_packet(role, task, acceptance, constraints, raw_artifacts,
                         raw_evidence, max_findings) for role in selected]


def main():
    parser = argparse.ArgumentParser(description="只读验证 PromptPacket 组装器")
    parser.add_argument("--task", required=True)
    parser.add_argument("--acceptance", default="[]", help="JSON 数组或 @file")
    parser.add_argument("--constraints", default="[]", help="JSON 数组或 @file")
    parser.add_argument("--raw-artifacts", default="[]", dest="raw_artifacts")
    parser.add_argument("--raw-evidence", default="[]", dest="raw_evidence")
    parser.add_argument("--roles", help="逗号分隔；默认 goal-spec,measurement,integration-regression")
    parser.add_argument("--max-findings", type=int, default=5, dest="max_findings")
    parser.add_argument("--level", choices=["L1", "L2", "L3", "L4"],
                        help="按预算限制 packet 数；L1 为 0")
    parser.add_argument("--risk-signals", default="{}", dest="risk_signals",
                        help="JSON 对象；例如 {\"unverified\":true,\"D\":true}")
    parser.add_argument("--format", default="json", choices=["json", "text"])
    args = parser.parse_args()
    try:
        roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
        packets = assemble(args.task, _load_value(args.acceptance), _load_value(args.constraints),
                           _load_value(args.raw_artifacts), _load_value(args.raw_evidence),
                           roles, args.max_findings, args.level, _load_value(args.risk_signals))
        output = {"packets": packets, "subagents_started": 0, "parallelism": "host-controlled"}
        if args.format == "text":
            print(f"PromptPacket: {len(packets)} 个；subagent_started=0")
            for packet in packets:
                print(f"- {packet['role']}: {packet['packet_id']} (authority=read-only)")
        else:
            print(json.dumps(output, ensure_ascii=False, indent=2))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "code": 2}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
