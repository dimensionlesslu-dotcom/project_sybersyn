#!/usr/bin/env python3
"""
handoff_report.py — Project Cybersyn 移交报告生成器

当任务不收敛、超 Nmax、或触发向人移交闸时，汇总当前最佳结果和待决策项。

用法示例:
  handoff_report.py --state cybersyn_state.json
  handoff_report.py --state cybersyn_state.json --output report.md --extra '{"artifact_location":"src/auth/"}'
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Windows 控制台/管道默认 GBK，统一 UTF-8 输出避免乱码
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"状态文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 数据提取 ──────────────────────────────────────────────
def collect_unmet(state: dict) -> list[dict]:
    """从未轮 feedback 提取未解决的 e(t) 项。"""
    rounds = state.get("rounds", [])
    if not rounds:
        return []
    last_fb = rounds[-1].get("feedback", {})
    unmet = []
    for cat_name, cat_label in [("e_missing", "缺失"), ("e_wrong", "错误")]:
        for item in last_fb.get(cat_name, []):
            unmet.append({
                "category": cat_label,
                "description": item.get("description", item.get("requirement_id", str(item))),
                "severity": item.get("severity", "medium"),
                "deviation_type": last_fb.get("deviation_type", "?"),
            })
    return unmet


def summarize_history(state: dict) -> list[dict]:
    """轮次级摘要表。"""
    rounds = state.get("rounds", [])
    summary = []
    for r in rounds:
        fb = r.get("feedback", {})
        t2 = r.get("test2", {})
        if not fb:
            continue
        summary.append({
            "round": r["n"],
            "type": fb.get("deviation_type", "?"),
            "e_missing": len(fb.get("e_missing", [])),
            "e_wrong": len(fb.get("e_wrong", [])),
            "e_extra": len(fb.get("e_extra", [])),
            "verdict": t2.get("verdict", r.get("stage", "?")),
        })
    return summary


def detect_structural_patterns(state: dict) -> list[str]:
    patterns = state.get("structural_patterns", [])
    return [p.get("description", str(p)) for p in patterns]


def collect_dead_zones(state: dict) -> list[dict]:
    return state.get("r_t", {}).get("dead_zones", [])


def collect_env_signals(state: dict) -> list[dict]:
    return state.get("_env_change_signals", {}).get("signals", [])


def collect_audit_history(state: dict) -> list[dict]:
    return state.get("audit_log", [])


# ── 建议生成 ──────────────────────────────────────────────
def generate_next_steps(state: dict) -> list[str]:
    steps = []
    unmet = collect_unmet(state)
    dead_zones = collect_dead_zones(state)
    structural = detect_structural_patterns(state)
    nmax = state.get("nmax", -1)
    round_n = state.get("round", 0)

    if nmax != -1 and round_n >= nmax:
        steps.append(f"[!] 已超 Nmax ({nmax})，请决定：接受当前产物 / 扩展 nmax / 放弃任务")

    if dead_zones:
        open_dz = [d for d in dead_zones if isinstance(d, dict) and d.get("status") != "resolved"]
        if open_dz:
            steps.append(f"存在 {len(open_dz)} 个死区：建议用户确认是否接受或调整验收标准")

    if structural:
        steps.append(f"检测到 {len(structural)} 个结构性问题，非调参可解决。建议：重构策略或升级研讨厅。")

    if unmet:
        steps.append(f"尚有 {len(unmet)} 项未通过验收。可继续修改或请用户决策。")

    steps.append("[i] 可使用 cybersyn_state.py pause 暂停任务等待用户决策。")
    return steps


def generate_pending_questions(state: dict) -> list[str]:
    questions = []
    dead_zones = collect_dead_zones(state)
    for dz in dead_zones:
        if isinstance(dz, dict) and dz.get("status") != "resolved":
            questions.append(f"死区「{dz.get('description', dz.get('id', '?'))}」：是否接受当前状态或需补充能力？")

    nmax = state.get("nmax", -1)
    if nmax != -1 and state.get("round", 0) >= nmax:
        questions.append("已超最大轮次限制，是否扩展 nmax 继续迭代？")

    if state.get("paused", {}).get("active"):
        options = state["paused"].get("decision_options", [])
        if options:
            questions.append(f"待决策：{' | '.join(options)}")

    if not questions:
        questions.append("是否接受当前产物作为最终交付？")
    return questions


# ── 渲染 ──────────────────────────────────────────────────
def render_markdown(state: dict, extra: dict) -> str:
    unmet = collect_unmet(state)
    history = summarize_history(state)
    structural = detect_structural_patterns(state)
    dead_zones = collect_dead_zones(state)
    env_signals = collect_env_signals(state)
    audit_history = collect_audit_history(state)
    next_steps = generate_next_steps(state)
    questions = generate_pending_questions(state)

    nmax = state.get("nmax", "∞")
    round_n = state.get("round", "?")
    over_nmax = nmax != -1 and round_n >= nmax

    lines = [
        f"# 移交报告 — {state.get('task', '未命名')}",
        "",
        f"**生成时间**：{datetime.now(timezone.utc).isoformat()}  ",
        f"**状态**：{'[!] 已超 Nmax' if over_nmax else state.get('verdict', '?')} ({round_n}/{nmax})  ",
        f"**复杂度**：{state.get('level', '?')}  ",
        "",
        "---",
        "",
        "## 当前最佳产物",
        "",
    ]

    if extra.get("artifact_location"):
        lines.append(f"- **产物位置**：{extra['artifact_location']}")
    if extra.get("artifact_description"):
        lines.append(f"- **描述**：{extra['artifact_description']}")

    last_fb = state.get("rounds", [{}])[-1].get("feedback", {})
    lines.append(f"- **最终偏差**：e_missing={len(last_fb.get('e_missing',[]))}, e_extra={len(last_fb.get('e_extra',[]))}, e_wrong={len(last_fb.get('e_wrong',[]))}")
    ps = state.get("_patterns_summary", {})
    lines.append(f"- **主导偏差类型**：{ps.get('dominant_type', '?')}")
    lines.append("")

    if unmet:
        lines += [
            "## 未通过的验收项",
            "",
            "| 类别 | 描述 | 严重度 | 偏差类型 |",
            "|------|------|--------|----------|",
        ]
        for u in unmet:
            lines.append(f"| {u['category']} | {u['description'][:60]} | {u['severity']} | {u['deviation_type']} |")
        lines.append("")

    if history:
        lines += [
            "## 偏差历史摘要",
            "",
            "| 轮次 | 类型 | e_missing | e_wrong | e_extra | 判决 |",
            "|------|------|-----------|---------|---------|------|",
        ]
        for h in history:
            lines.append(f"| {h['round']} | {h['type']} | {h['e_missing']} | {h['e_wrong']} | {h['e_extra']} | {h['verdict']} |")
        lines.append("")

    if dead_zones:
        lines += [
            "## 死区",
            "",
            "| ID | 描述 | 状态 |",
            "|----|------|------|",
        ]
        for dz in dead_zones:
            if isinstance(dz, dict):
                lines.append(f"| {dz.get('id','?')} | {dz.get('description','?')[:60]} | {dz.get('status','open')} |")
        lines.append("")

    if structural:
        lines += [
            "## 结构性问题",
            "",
        ]
        for s in structural:
            lines.append(f"- {s}")
        lines.append("")

    if env_signals:
        lines += [
            "## 环境信号",
            "",
        ]
        for es in env_signals:
            lines.append(f"- [{es.get('time','?')}] {es.get('source','?')}: {es.get('description','?')[:100]}")
        lines.append("")

    if audit_history:
        lines += [
            "## 二阶审计历史",
            "",
        ]
        for a in audit_history:
            lines.append(f"- 第 {a.get('round','?')} 轮：{a.get('conclusion','?')}")
        lines.append("")

    if next_steps:
        lines += [
            "## 建议下一步",
            "",
        ]
        for i, s in enumerate(next_steps):
            lines.append(f"{i + 1}. {s}")
        lines.append("")

    if questions:
        lines += [
            "## 待用户回答",
            "",
        ]
        for q in questions:
            lines.append(f"- {q}")
        lines.append("")

    if extra.get("user_notes"):
        lines += ["## 用户备注", "", extra["user_notes"], ""]

    return "\n".join(lines)


def render_json(state: dict, extra: dict) -> dict:
    return {
        "task": state.get("task"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "level": state.get("level"),
        "round": state.get("round"),
        "nmax": state.get("nmax"),
        "verdict": state.get("verdict"),
        "convergence": state.get("convergence", False),
        "unmet_items": collect_unmet(state),
        "history": summarize_history(state),
        "structural_patterns": detect_structural_patterns(state),
        "dead_zones": collect_dead_zones(state),
        "env_signals": collect_env_signals(state),
        "audit_history": collect_audit_history(state),
        "next_steps": generate_next_steps(state),
        "pending_questions": generate_pending_questions(state),
        "extra": extra,
    }


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Project Cybersyn 移交报告生成器")
    parser.add_argument("--state", required=True, help="状态文件路径")
    parser.add_argument("--output", help="输出文件路径（默认 stdout）")
    parser.add_argument("--format", default="markdown", choices=["json", "markdown"])
    parser.add_argument("--extra", default="{}", help="额外信息 JSON")

    args = parser.parse_args()

    try:
        state = load_state(args.state)
        extra = json.loads(args.extra)

        if args.format == "markdown":
            output = render_markdown(state, extra)
        else:
            output = json.dumps(render_json(state, extra), ensure_ascii=False, indent=2)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(json.dumps({"status": "ok", "output": args.output}, ensure_ascii=False))
        else:
            print(output)

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e), "code": 2}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
