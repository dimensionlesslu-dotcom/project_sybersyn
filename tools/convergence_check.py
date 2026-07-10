#!/usr/bin/env python3
"""
convergence_check.py — Project Cybersyn 收敛检测器 (v2.0)

比较当前轮 e(t) 与历史轮次，判定收敛状态。扩展功能：
  --energy   稳定性能量函数（Lyapunov 启发）
  --periodic 偏差周期性检测（极限环）
  --drift    环境漂移检测
  --gain     干预-响应增益分析

用法示例:
  convergence_check.py --state cybersyn_state.json
  convergence_check.py --state cybersyn_state.json --energy --periodic --drift
"""

import argparse
import json
import math
import os
import sys
from collections import Counter
from statistics import mean, stdev


# ── 加载 ──────────────────────────────────────────────────
def load_state(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"状态文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 偏差历史提取 ──────────────────────────────────────────
def extract_deviation_history(state: dict) -> list[dict]:
    """从 rounds 提取每轮 e(t) 摘要。"""
    history = []
    for r in state.get("rounds", []):
        fb = r.get("feedback", {})
        if not fb:
            continue
        history.append({
            "round": r["n"],
            "e_missing": fb.get("e_missing", []),
            "e_extra": fb.get("e_extra", []),
            "e_wrong": fb.get("e_wrong", []),
            "deviation_type": fb.get("deviation_type"),
            "severity_counts": _count_severity(fb),
        })
    return history


def _count_severity(fb: dict) -> dict:
    counts = Counter()
    for cat in ("e_missing", "e_extra", "e_wrong"):
        for item in fb.get(cat, []):
            counts[item.get("severity", "medium")] += 1
    return dict(counts)


# ── 基础收敛判定 ──────────────────────────────────────────
def compare_rounds(current: dict, previous: dict) -> dict:
    """对比两轮偏差。"""
    new_missing = [m for m in current.get("e_missing", [])
                   if m not in previous.get("e_missing", [])]
    new_wrong = [w for w in current.get("e_wrong", [])
                 if w not in previous.get("e_wrong", [])]
    new_extra = [e for e in current.get("e_extra", [])
                 if e not in previous.get("e_extra", [])]
    resolved = (
        len(previous.get("e_wrong", [])) - len(current.get("e_wrong", [])) +
        len(previous.get("e_missing", [])) - len(current.get("e_missing", [])) +
        len(previous.get("e_extra", [])) - len(current.get("e_extra", []))
    )
    return {
        "new_items": len(new_missing) + len(new_wrong) + len(new_extra),
        "resolved_items": resolved,
        "new_details": {
            "missing": [m.get("description", str(m)) for m in new_missing],
            "wrong": [w.get("description", str(w)) for w in new_wrong],
            "extra": [e.get("description", str(e)) for e in new_extra],
        },
    }


def assess_trend(history: list[dict]) -> str:
    """判趋势：converging / stagnant / diverging。"""
    if len(history) < 2:
        return "unknown"
    counts = []
    for h in history:
        counts.append(len(h["e_missing"]) + len(h["e_extra"]) + len(h["e_wrong"]))
    if len(counts) >= 3:
        recent = counts[-3:]
        if all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1)):
            return "converging" if recent[-1] < recent[0] else "stagnant"
    if counts[-1] < counts[-2]:
        return "converging"
    elif counts[-1] == counts[-2]:
        return "stagnant"
    return "diverging"


def convergence_verdict(state: dict) -> dict:
    """基础收敛判定。"""
    history = extract_deviation_history(state)
    if not history:
        return {"status": "continuing", "reasons": ["首轮，无对比基准"], "round": state.get("round", 0)}

    current = history[-1]
    previous = history[-2] if len(history) >= 2 else None
    nmax = state.get("nmax", -1)
    round_n = state["round"]
    comparison = compare_rounds(current, previous) if previous else {"new_items": None, "resolved_items": None}

    reasons = []
    status = "continuing"

    # 收敛条件
    has_critical = current["severity_counts"].get("critical", 0) > 0
    has_new = (comparison.get("new_items") or 0) > 0

    if not has_new and not has_critical:
        if previous and _total(current) <= _total(previous):
            status = "converged"
            reasons.append("连续两轮无新增偏差且无 critical 项")

    # 移交条件
    if nmax != -1 and round_n >= nmax:
        status = "handoff"
        reasons.append(f"Nmax ({nmax}) 已达")

    if previous and current["deviation_type"] != previous.get("deviation_type"):
        prev_type = previous.get("deviation_type")
        curr_type = current.get("deviation_type")
        if prev_type in ("A", "B") and curr_type in ("C", "D"):
            status = "handoff"
            reasons.append(f"偏差类型从 {prev_type} 突变为 {curr_type}")

    if current["deviation_type"] == "D":
        reasons.append("涌现偏差(D)检测到，建议升级研讨厅")

    if not reasons:
        if (comparison.get("resolved_items") or 0) > 0:
            reasons.append(f"偏差在减少（已解决 {comparison['resolved_items']} 项），但尚未完全收敛")
        else:
            reasons.append("偏差未见显著改善")

    trend = assess_trend(history)
    total_counts = []
    for h in history:
        total_counts.append(_total(h))
    trend_data = {
        "e_missing_count": [len(h["e_missing"]) for h in history],
        "e_wrong_count": [len(h["e_wrong"]) for h in history],
        "e_extra_count": [len(h["e_extra"]) for h in history],
    }

    return {
        "status": status,
        "round": round_n,
        "nmax": nmax,
        "trend": trend_data,
        "convergence_trend_label": trend,
        "comparison": comparison,
        "reasons": reasons,
        "recommendation": _basic_recommendation(status, reasons),
    }


def _total(h: dict) -> int:
    return len(h.get("e_missing", [])) + len(h.get("e_extra", [])) + len(h.get("e_wrong", []))


def _basic_recommendation(status: str, reasons: list) -> str:
    if status == "converged":
        return "已收敛，可进入交付验收门。"
    if status == "handoff":
        return f"建议停止迭代并向人移交：{'; '.join(reasons)}"
    return f"继续迭代：{'; '.join(reasons)}"


# ── 增益分析 (P1-1) ──────────────────────────────────────
def infer_k_intensity(modify: dict) -> int:
    if not modify:
        return 2
    k_text = (modify.get("k") or "").lower()
    if "微调" in k_text or "minor" in k_text or "微" in k_text:
        return 1
    if "局部" in k_text or "local" in k_text:
        return 2
    if "整体" in k_text or "全局" in k_text or "full" in k_text or "重构" in k_text:
        return 3
    return 2


def compute_gain_ratio(state: dict) -> dict:
    """计算每轮干预的增益。"""
    rounds = state.get("rounds", [])
    gains = [None]  # 首轮无参考
    total_prev = None

    for i, r in enumerate(rounds):
        fb = r.get("feedback", {})
        if not fb:
            gains.append(None)
            continue
        total_curr = _total(fb)
        if i == 0 or total_prev is None:
            total_prev = total_curr
            continue
        delta = abs(total_prev - total_curr)
        k = infer_k_intensity(r.get("modify", {}))
        gain = delta / k if k > 0 else 0
        gains.append(round(gain, 2))
        total_prev = total_curr

    valid_gains = [g for g in gains if g is not None]
    avg = round(mean(valid_gains), 2) if valid_gains else 0
    trend = "stable"
    if len(valid_gains) >= 2:
        if valid_gains[-1] > valid_gains[-2] + 0.3:
            trend = "improving"
        elif valid_gains[-1] < valid_gains[-2] - 0.3:
            trend = "declining"

    low_gain = len(valid_gains) >= 2 and valid_gains[-1] < 0.3 and valid_gains[-2] < 0.3

    return {
        "gains": gains,
        "avg_gain": avg,
        "trend": trend,
        "low_gain_warning": low_gain,
        "recommendation": "增益递减中，若连续两轮 < 0.3 建议换策略" if low_gain else (
            "增益稳定" if trend == "stable" else "增益在改善" if trend == "improving" else "增益在下降"
        ),
    }


# ── 能量函数 (P2-3) ──────────────────────────────────────
def compute_energy(state: dict) -> dict:
    """Lyapunov 启发的偏差能量函数。"""
    SEVERITY_WEIGHTS = {"critical": 8, "high": 4, "medium": 2, "low": 1}
    rounds = state.get("rounds", [])
    series = []

    for r in rounds:
        fb = r.get("feedback", {})
        if not fb:
            series.append(0)
            continue
        e_val = 0
        for cat in ("e_missing", "e_extra", "e_wrong"):
            for item in fb.get(cat, []):
                sev = item.get("severity", "medium")
                e_val += SEVERITY_WEIGHTS.get(sev, 2)
        series.append(e_val)

    if not series:
        return {"current": 0, "series": [], "delta": 0, "delta_trend": "unknown", "limit_cycle_detected": False, "suggestion": None}

    current = series[-1]
    delta = series[-1] - series[-2] if len(series) >= 2 else 0
    delta_trend = "unknown"
    if len(series) >= 3:
        deltas = [series[i] - series[i - 1] for i in range(1, len(series))]
        recent_deltas = deltas[-2:]
        if all(d <= 0 for d in recent_deltas):
            delta_trend = "decreasing"
        elif all(d >= 0 for d in recent_deltas):
            delta_trend = "increasing"
        else:
            delta_trend = "flat"

    # 极限环检测：最近 3 轮 E 在均值 ±10% 内振荡且无单调下降
    limit_cycle = False
    if len(series) >= 3:
        recent = series[-3:]
        avg = mean(recent)
        try:
            dev = stdev(recent) if len(recent) >= 3 else 0
        except Exception:
            dev = 0
        if avg > 0 and dev / avg < 0.1:
            if not all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1)):
                limit_cycle = True

    return {
        "current": current,
        "series": series,
        "delta": delta,
        "delta_trend": delta_trend,
        "limit_cycle_detected": limit_cycle,
        "suggestion": "偏差能量振荡不降，可能存在极限环。建议触发二阶审计检查结构性问题。" if limit_cycle else (
            "能量在下降中，干预有效" if delta_trend == "decreasing" else None
        ),
    }


# ── 周期性检测 (P2-1) ────────────────────────────────────
def detect_periodicity(state: dict) -> dict:
    """检测偏差序列的周期性模式（自相关法）。"""
    rounds = state.get("rounds", [])
    if len(rounds) < 4:
        return {"detected": False, "period": None, "pattern": None, "confidence": None, "severity": None}

    # 提取 e_wrong 计数序列
    counts = []
    for r in rounds:
        fb = r.get("feedback", {})
        if fb:
            counts.append(len(fb.get("e_wrong", [])) + len(fb.get("e_missing", [])))
        else:
            counts.append(0)

    n = len(counts)
    max_lag = n // 2
    best_lag, best_corr = None, 0

    for lag in range(2, max_lag + 1):
        x = counts[:-lag]
        y = counts[lag:]
        if len(x) < 3:
            continue
        corr = _pearson(x, y)
        if corr is not None and abs(corr) > best_corr:
            best_corr = abs(corr)
            best_lag = lag

    if best_lag and best_corr > 0.7:
        return {
            "detected": True,
            "period": best_lag,
            "pattern": f"每 {best_lag} 轮出现偏差波动（自相关={best_corr:.2f}）",
            "confidence": round(best_corr, 2),
            "severity": "high" if best_corr > 0.9 else "medium",
            "recommendation": "周期性偏差提示结构性问题，建议触发二阶审计检查执行策略。",
        }
    return {"detected": False, "period": None, "pattern": None, "confidence": None, "severity": None}


def _pearson(x: list, y: list) -> float:
    if len(x) < 2:
        return None
    try:
        mx, my = mean(x), mean(y)
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        dy = math.sqrt(sum((yi - my) ** 2 for yi in y))
        return num / (dx * dy) if dx * dy > 0 else 0
    except Exception:
        return None


# ── 环境漂移检测 (P1-3) ──────────────────────────────────
def detect_env_drift(state: dict) -> dict:
    """检测核心假设是否仍与环境匹配。"""
    assumptions = state.get("r_t", {}).get("core_assumptions", [])
    signals = state.get("_env_change_signals", {})
    rounds = state.get("rounds", [])

    dimensions = []
    drift_score = 0.0
    n = len(assumptions) if assumptions else 1

    for a in assumptions:
        # 检查是否被环境信号推翻（简化：关键词匹配）
        contradicted = False
        for sig in signals.get("signals", []):
            desc = sig.get("description", "").lower()
            a_lower = a.lower()
            if any(kw in desc for kw in a_lower.split() if len(kw) > 3):
                contradicted = True
                break
        if contradicted:
            dimensions.append({"assumption": a, "status": "contradicted_by_input",
                               "evidence": "环境变化信号中包含相关描述"})
            drift_score += 1.0 / n
        else:
            dimensions.append({"assumption": a, "status": "still_valid"})

    # C 型偏差连续 2+ 轮额外加分
    c_count = sum(1 for r in rounds if r.get("feedback", {}).get("deviation_type") == "C")
    if c_count >= 2:
        drift_score += 0.3

    # 环境信号计数加分
    drift_score += min(0.5, signals.get("count", 0) * 0.1)
    drift_score = min(drift_score, 1.0)

    return {
        "drift_detected": drift_score > 0.5,
        "confidence": round(drift_score, 2),
        "drift_score": round(drift_score, 2),
        "threshold": 0.5,
        "dimensions": dimensions,
        "recommendation": (
            "核心假设可能已被新输入推翻，建议暂停并重设 r(t)。"
            if drift_score > 0.5 else "环境稳定，核心假设成立。"
        ),
    }


# ── 稳态/暂态区分 (P2-2) ─────────────────────────────────
def detect_transient_steady(state: dict) -> dict:
    """区分当前偏差是过渡过程还是已达稳态。"""
    rounds = state.get("rounds", [])
    if len(rounds) < 2:
        return {"phase": "unknown", "evidence": [], "recommendation": "数据不足"}

    history = extract_deviation_history(state)
    counts = [_total(h) for h in history]
    recent = counts[-3:] if len(counts) >= 3 else counts

    # 计算减少速率
    deltas = [counts[i] - counts[i - 1] for i in range(1, len(counts))]
    recent_deltas = deltas[-2:] if len(deltas) >= 2 else deltas

    phase = "transient"
    evidence = []
    if len(recent) >= 2 and recent[-1] == recent[-2] and recent[-2] > 0:
        phase = "steady"
        evidence.append("连续两轮偏差总数不变，已达当前策略极限")
    elif all(d >= 0 for d in recent_deltas) and recent_deltas[-1] > -0.5:
        phase = "approaching_steady"
        evidence.append("偏差减少速率趋近零")
    elif any(d < -1 for d in recent_deltas):
        phase = "transient"
        evidence.append("偏差每轮显著减少，处于过渡过程")

    return {
        "phase": phase,
        "evidence": evidence,
        "recommendation": (
            "已达稳态，继续迭代可能无效，建议考虑换策略或审计。"
            if phase == "steady" else "继续迭代，当前策略有效。"
        ),
    }


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Project Cybersyn 收敛检测器 v2.0")
    parser.add_argument("--state", required=True, help="状态文件路径")
    parser.add_argument("--energy", action="store_true", help="计算偏差能量函数")
    parser.add_argument("--periodic", action="store_true", help="检测偏差周期性")
    parser.add_argument("--drift", action="store_true", help="检测环境漂移")
    parser.add_argument("--gain", action="store_true", help="计算干预增益")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--format", default="json", choices=["json", "text"])

    args = parser.parse_args()

    try:
        state = load_state(args.state)
        result = convergence_verdict(state)

        if args.gain:
            result["gain_analysis"] = compute_gain_ratio(state)
            # 增益低收敛条件扩展
            ga = result["gain_analysis"]
            if ga.get("low_gain_warning") and result["status"] == "continuing":
                result.setdefault("reasons", []).append("连续两轮增益 < 0.3，干预效果不足")
                result["recommendation"] += " 考虑换策略（增益过低）。"

        if args.energy:
            result["energy"] = compute_energy(state)
            # 极限环触发移交
            if result["energy"].get("limit_cycle_detected") and result["status"] == "continuing":
                result["reasons"].append("检测到极限环（能量振荡不降）")
                result["recommendation"] += " 检测到极限环，建议触发二阶审计。"

        if args.periodic:
            result["periodic"] = detect_periodicity(state)

        if args.drift:
            result["env_drift"] = detect_env_drift(state)

        if args.gain or args.energy:
            result["transient_steady"] = detect_transient_steady(state)

        if args.format == "text":
            print(f"状态: {result['status']}  |  轮次: {result['round']}/{result.get('nmax', '?')}")
            print(f"趋势: {result.get('convergence_trend_label', '?')}")
            for r in result.get("reasons", []):
                print(f"  - {r}")
            print(f"建议: {result.get('recommendation', '')}")
            if "gain_analysis" in result:
                ga = result["gain_analysis"]
                print(f"\n增益: avg={ga['avg_gain']}, trend={ga['trend']}, warning={ga['low_gain_warning']}")
            if "energy" in result:
                en = result["energy"]
                print(f"能量: E={en['current']}, delta={en['delta']}, limit_cycle={en['limit_cycle_detected']}")
            if "env_drift" in result:
                ed = result["env_drift"]
                print(f"环境漂移: detected={ed['drift_detected']}, score={ed['drift_score']}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e), "code": 2}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
