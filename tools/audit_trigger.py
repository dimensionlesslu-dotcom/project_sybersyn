#!/usr/bin/env python3
"""
audit_trigger.py — Project Cybersyn 二阶审计触发器 (v2.0)

跟踪迭代轮次和偏差模式，在满足条件时提醒触发二阶审计，输出审计问题清单。
--auto-conclude: 基于偏差模式自动推荐审计结论。

用法示例:
  audit_trigger.py --state cybersyn_state.json
  audit_trigger.py --state cybersyn_state.json --auto-conclude
"""

import argparse
import json
import os
import sys

# Windows 控制台/管道默认 GBK，统一 UTF-8 输出避免乱码
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"状态文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 触发条件检测 ──────────────────────────────────────────
def check_periodic(state: dict) -> tuple:
    """定时触发。"""
    round_n = state.get("round", 0)
    audit_every = state.get("audit_every", 3)
    if round_n > 0 and round_n % audit_every == 0:
        return True, f"定时触发 (round={round_n}, every={audit_every})"
    return False, ""


def check_same_type_persist(state: dict) -> tuple:
    """同类型偏差持续 2+ 轮。"""
    rounds = state.get("rounds", [])
    if len(rounds) < 2:
        return False, ""
    recent_types = []
    for r in rounds[-3:]:
        dt = r.get("feedback", {}).get("deviation_type")
        if dt:
            recent_types.append(dt)
    if len(recent_types) >= 2 and len(set(recent_types[-2:])) == 1:
        return True, f"偏差类型 {recent_types[-1]} 连续 {recent_types[-2:].count(recent_types[-1])} 轮未消除"
    return False, ""


def check_type_mutation(state: dict) -> tuple:
    """类型突变 A/B → C/D。"""
    rounds = state.get("rounds", [])
    if len(rounds) < 2:
        return False, ""
    prev = rounds[-2].get("feedback", {}).get("deviation_type")
    curr = rounds[-1].get("feedback", {}).get("deviation_type")
    if prev in ("A", "B") and curr in ("C", "D"):
        return True, f"偏差类型从 {prev} 突变为 {curr}"
    return False, ""


def check_stall(state: dict) -> tuple:
    """过半 Nmax 未收敛。"""
    nmax = state.get("nmax", -1)
    if nmax == -1:
        return False, ""
    round_n = state.get("round", 0)
    convergence = state.get("convergence", False)
    if not convergence and round_n > nmax / 2:
        return True, f"已过 Nmax 一半 ({round_n}/{nmax}) 且未收敛"
    return False, ""


def check_env_signals(state: dict) -> tuple:
    """环境变化信号新增。"""
    signals = state.get("_env_change_signals", {})
    audit_log = state.get("audit_log", [])
    last_audit_round = audit_log[-1].get("round", 0) if audit_log else 0
    new_signals = [
        s for s in signals.get("signals", [])
        if s.get("time", "") > ""
    ]
    if len(new_signals) > 0 and state.get("round", 0) > last_audit_round:
        return True, f"自上次审计以来有 {len(new_signals)} 个新环境信号"
    return False, ""


# ── 清单生成 ──────────────────────────────────────────────
def generate_checklist(state: dict) -> list[str]:
    """根据偏差类型定制审计清单。"""
    base = [
        "1. r(t) 假设从哪来？最近验证过吗？若 r(t) 本身错，偏差分析还成立吗？",
        "2. 我是否只选了支持先验的测量方式、回避了不想看的区域？",
        "3. 这是参数误差还是结构问题？需换执行策略形状/增大多样性吗？",
        "4. 实际在做的 vs 声称要做的，差距持续则改行为还是改声明？(POSIWID)",
    ]

    rounds = state.get("rounds", [])
    if not rounds:
        return base

    last_type = rounds[-1].get("feedback", {}).get("deviation_type")
    if last_type == "C":
        base.insert(0, "[!] 当前为 C 型偏差（环境漂移）：r(t) 的哪些核心假设可能已被新输入推翻？")
    elif last_type == "D":
        base.insert(0, "[!] 当前为 D 型偏差（涌现）：哪些子系统的交互假设需要重新检查？")
    elif last_type == "A":
        type_a_count = sum(1 for r in rounds if r.get("feedback", {}).get("deviation_type") == "A")
        if type_a_count >= 3:
            base.insert(0, f"[!] 类型 A 偏差已持续 {type_a_count} 轮：这真的是参数问题还是隐藏的结构问题？")

    return base


# ── 自动结论推荐 ──────────────────────────────────────────
def recommend_conclusion(state: dict) -> dict:
    """基于偏差模式推荐审计结论。"""
    rounds = state.get("rounds", [])
    if not rounds:
        return {"recommended_conclusion": "maintain", "confidence": 0.5, "reasoning": "无迭代数据"}

    last_type = rounds[-1].get("feedback", {}).get("deviation_type")
    env_signals = state.get("_env_change_signals", {}).get("count", 0)
    structural = state.get("structural_patterns", [])

    # D 型 → upgrade-forum
    if last_type == "D":
        return {
            "recommended_conclusion": "upgrade-forum",
            "confidence": 0.9,
            "reasoning": "涌现偏差(D)表明子系统交互存在非预期行为，需研讨厅级别分析。",
        }

    # C 型 + 环境信号 → reset-rt
    if last_type == "C" and env_signals > 0:
        return {
            "recommended_conclusion": "reset-rt",
            "confidence": 0.8,
            "reasoning": "C 型偏差 + 环境变化信号，r(t) 核心假设可能已被推翻。",
        }

    # 结构性问题 + 同类偏差 ≥3 轮 → restructure
    type_a_count = sum(1 for r in rounds if r.get("feedback", {}).get("deviation_type") == "A")
    if structural and type_a_count >= 3:
        return {
            "recommended_conclusion": "restructure",
            "confidence": 0.75,
            "reasoning": f"结构性问题记录 + 类型 A 偏差持续 {type_a_count} 轮，调参已不够。",
        }

    # C 型但无环境信号 → reset-rt（轻微置信度）
    if last_type == "C":
        return {
            "recommended_conclusion": "reset-rt",
            "confidence": 0.6,
            "reasoning": "C 型偏差提示 r(t) 可能不再匹配，建议复核目标。",
        }

    # 默认 → maintain
    return {
        "recommended_conclusion": "maintain",
        "confidence": 0.7,
        "reasoning": "偏差在改善中或数据不足以支持更激进的结论。",
    }


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Project Cybersyn 二阶审计触发器 v2.0")
    parser.add_argument("--state", required=True, help="状态文件路径")
    parser.add_argument("--auto-conclude", action="store_true", help="自动推荐审计结论")
    parser.add_argument("--force", action="store_true", help="强制执行审计")
    parser.add_argument("--format", default="json", choices=["json", "text"])

    args = parser.parse_args()

    try:
        state = load_state(args.state)
        audit_counter = state.get("audit_counter", 0)
        round_n = state.get("round", 0)

        reasons = []
        triggers = [
            ("periodic", check_periodic),
            ("same_type", check_same_type_persist),
            ("type_mutation", check_type_mutation),
            ("stall", check_stall),
            ("env_signals", check_env_signals),
        ]

        if args.force:
            reasons.append("手动强制执行")

        triggered = args.force
        for name, func in triggers:
            hit, reason = func(state)
            if hit:
                reasons.append(reason)
                triggered = True

        prev_audit = state.get("audit_log", [])
        prev_conclusion = None
        if prev_audit:
            last = prev_audit[-1]
            prev_conclusion = f"{last.get('conclusion', '?')}（第 {last.get('round', '?')} 轮）"

        checklist = generate_checklist(state)

        result = {
            "trigger": triggered,
            "reasons": reasons or ["无需审计"],
            "audit_round": round_n,
            "audit_counter": audit_counter,
            "checklist": checklist if triggered else [],
            "previous_audit_conclusion": prev_conclusion,
            "warning": "若 r(t) 最近未经审计确认，禁止开启正反馈加速" if triggered else None,
        }

        if args.auto_conclude and triggered:
            rec = recommend_conclusion(state)
            result["recommended_conclusion"] = rec["recommended_conclusion"]
            result["confidence"] = rec["confidence"]
            result["reasoning"] = rec["reasoning"]
            result["suggested_actions"] = [
                f"cybersyn_state.py apply-audit --conclusion {rec['recommended_conclusion']}",
            ]
            if rec["recommended_conclusion"] in ("upgrade-forum", "restructure"):
                result["suggested_actions"].append(
                    f"diversity_generator.py --task '{state.get('task','')}' --context {args.state} --strategies 3"
                )

        if args.format == "text":
            print(f"触发: {'是' if triggered else '否'}  |  轮次: {round_n}  |  审计计数: {audit_counter}")
            if reasons:
                print("原因:")
                for r in reasons:
                    print(f"  - {r}")
            if triggered and checklist:
                print("\n审计清单:")
                for c in checklist:
                    print(f"  {c}")
            if result.get("recommended_conclusion"):
                print(f"\n推荐结论: {result['recommended_conclusion']} (置信度: {result['confidence']})")
                print(f"理由: {result['reasoning']}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e), "code": 2}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
