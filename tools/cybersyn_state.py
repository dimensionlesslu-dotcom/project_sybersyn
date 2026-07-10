#!/usr/bin/env python3
"""
cybersyn_state.py — Project Cybersyn 迭代状态管理器 (v2.0)

跨轮持久化闭环迭代的全部状态。所有其他工具通过它读写任务状态。
子命令: init read update reset query archive apply-audit pause resume migrate lock unlock summary validate

用法示例:
  cybersyn_state.py init --level L3 --task "重构 auth 模块"
  cybersyn_state.py read --field all
  cybersyn_state.py update --stage feedback --data '{"e_missing":[],"e_wrong":[...]}'
  cybersyn_state.py query --pattern "type-A" --scope rounds
  cybersyn_state.py archive
  cybersyn_state.py apply-audit --conclusion restructure
  cybersyn_state.py pause --reason "等待用户确认" --options "继续,重设目标,放弃"
  cybersyn_state.py resume
  cybersyn_state.py migrate --dry-run
"""

import argparse
import json
import os
import re
import sys
import shutil
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────────
STATE_SCHEMA_VERSION = "2.0"
DEFAULT_STATE_PATH = "cybersyn_state.json"


def _default_params(level: str) -> dict:
    """按 level 返回默认控制参数。"""
    return {
        "L1": {"nmax": 2, "audit_every": 5, "allow_forum": False, "allow_vsm": False, "minimal_path_only": True},
        "L2": {"nmax": 3, "audit_every": 3, "allow_forum": False, "allow_vsm": False, "minimal_path_only": False},
        "L3": {"nmax": 5, "audit_every": 3, "allow_forum": False, "allow_vsm": True, "minimal_path_only": False},
        "L4": {"nmax": -1, "audit_every": 3, "allow_forum": True, "allow_vsm": True, "minimal_path_only": False},
    }.get(level, {"nmax": 5, "audit_every": 3, "allow_forum": False, "allow_vsm": True, "minimal_path_only": False})


def _new_state_skeleton(task: str, level: str, nmax: int = None, audit_every: int = None,
                        enforce_from: dict = None) -> dict:
    """创建 v2.0 状态骨架。"""
    dp = _default_params(level)
    now = datetime.now(timezone.utc).isoformat()
    enforce = enforce_from or {
        "allow_audit": level != "L1",
        "allow_vsm": dp["allow_vsm"],
        "allow_positive_feedback": False,
        "allow_handoff_report": level != "L1",
        "allow_forum": dp["allow_forum"],
        "minimal_path_only": dp["minimal_path_only"],
        "nmax": nmax if nmax is not None else dp["nmax"],
        "audit_every": audit_every if audit_every is not None else dp["audit_every"],
    }
    return {
        "_version": STATE_SCHEMA_VERSION,
        "_created": now,
        "_updated": now,
        "_last_modified_by": None,
        "task": task,
        "level": level,
        "round": 0,
        "nmax": nmax if nmax is not None else dp["nmax"],
        "audit_every": audit_every if audit_every is not None else dp["audit_every"],
        "audit_counter": 0,
        "convergence": False,
        "verdict": "continuing",
        "positive_feedback": "off",
        "_audit_confirmed_at": None,
        "upgrade_to_forum": False,
        "paused": {"active": False, "reason": None, "paused_at": None, "deadline": None, "decision_options": []},
        "_lock": {"held_by": None, "acquired_at": None, "expires_at": None},
        "_env_change_signals": {"count": 0, "last_signal": None, "signals": []},
        "_patterns_summary": _empty_patterns_summary(),
        "_enforce": enforce,
        "r_t": {"requirements": [], "core_assumptions": [], "dead_zones": []},
        "rounds": [],
        "archived_rounds": [],
        "audit_log": [],
        "structural_patterns": [],
    }


def _empty_patterns_summary() -> dict:
    return {"dominant_type": None, "type_distribution": {"A": 0, "B": 0, "C": 0, "D": 0},
            "persistent_issues": [], "convergence_trend": "unknown", "dead_zones_resolved": 0, "dead_zones_total": 0}


# ── 迁移器 ────────────────────────────────────────────────
STATE_MIGRATORS = {
    "1.0": lambda s: {
        **s,
        "_version": "2.0",
        "positive_feedback": "off",
        "_audit_confirmed_at": None,
        "upgrade_to_forum": False,
        "paused": {"active": False, "reason": None, "paused_at": None, "deadline": None, "decision_options": []},
        "_lock": {"held_by": None, "acquired_at": None, "expires_at": None},
        "_last_modified_by": None,
        "_env_change_signals": {"count": 0, "last_signal": None, "signals": []},
        "_patterns_summary": compute_patterns_summary(s),
        "_enforce": _default_enforce(s.get("level", "L3"), s.get("nmax", 5), s.get("audit_every", 3)),
    }
}


def _default_enforce(level: str, nmax: int, audit_every: int) -> dict:
    dp = _default_params(level)
    return {
        "allow_audit": level != "L1", "allow_vsm": dp["allow_vsm"],
        "allow_positive_feedback": False, "allow_handoff_report": level != "L1",
        "allow_forum": dp["allow_forum"], "minimal_path_only": dp["minimal_path_only"],
        "nmax": nmax, "audit_every": audit_every,
    }


# ── 文件 I/O ──────────────────────────────────────────────
def resolve_path() -> str:
    return os.environ.get("CYBERSYN_STATE", DEFAULT_STATE_PATH)


def load_state(path: str = None) -> dict:
    """读取状态文件，自动检测版本并执行迁移链。"""
    path = path or resolve_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"状态文件不存在: {path}。请先 cybersyn_state.py init")
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    ver = state.get("_version", "0.9")
    while ver != STATE_SCHEMA_VERSION:
        if ver not in STATE_MIGRATORS:
            raise ValueError(f"状态文件版本 {ver} 无法迁移到 {STATE_SCHEMA_VERSION}")
        state = STATE_MIGRATORS[ver](state)
        ver = state["_version"]
    return state


def save_state(state: dict, path: str = None) -> None:
    """原子写入：先写 .tmp，再 rename。写入前自动计算 _patterns_summary。"""
    path = path or resolve_path()
    if state.get("_version") != STATE_SCHEMA_VERSION:
        raise ValueError(f"状态版本 {state.get('_version')} != {STATE_SCHEMA_VERSION}，拒绝写入")
    state["_patterns_summary"] = compute_patterns_summary(state)
    state["_updated"] = datetime.now(timezone.utc).isoformat()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ── 状态初始化 ────────────────────────────────────────────
def init_state(task: str, level: str, nmax: int = None, audit_every: int = None,
               enforce_from: str = None, path: str = None) -> dict:
    """创建新状态文件。若文件已存在则报错（除非 --force）。"""
    path = path or resolve_path()
    if os.path.exists(path):
        raise FileExistsError(f"状态文件已存在: {path}。如需覆盖请先 reset 或删除。")
    enforce = None
    if enforce_from:
        with open(enforce_from, "r", encoding="utf-8") as f:
            enforce = json.load(f).get("enforce")
    state = _new_state_skeleton(task, level, nmax, audit_every, enforce)
    save_state(state, path)
    return state


# ── 轮次更新 ──────────────────────────────────────────────
def new_round(state: dict) -> dict:
    """在 rounds 末尾追加新轮次骨架，round 自增。"""
    state["round"] += 1
    state["verdict"] = "continuing"
    state["rounds"].append({
        "n": state["round"], "stage": "in_progress",
        "plan": {}, "test1": {}, "feedback": {}, "modify": {}, "test2": {},
    })
    return state


def update_round(state: dict, stage: str, data: dict, round_n: int = None) -> dict:
    """按 stage 更新当前（或指定）轮次数据。"""
    rounds = state["rounds"]
    if not rounds:
        state = new_round(state)
        rounds = state["rounds"]

    idx = -1
    if round_n is not None:
        for i, r in enumerate(rounds):
            if r["n"] == round_n:
                idx = i
                break
        if idx == -1:
            raise ValueError(f"轮次 {round_n} 不存在")
    current = rounds[idx]

    stage_map = {
        "plan": "plan", "test1": "test1", "feedback": "feedback",
        "modify": "modify", "test2": "test2", "output": None, "audit": None,
    }
    if stage in stage_map and stage_map[stage]:
        current[stage_map[stage]] = data
    elif stage == "output":
        state["verdict"] = data.get("verdict", state["verdict"])
        state["convergence"] = data.get("convergence", False)
    elif stage == "audit":
        state["audit_log"].append(data)
        state["audit_counter"] = 0

    # 自动副作用
    if stage == "feedback":
        state["audit_counter"] = state.get("audit_counter", 0) + 1

    if stage in ("modify", "test1", "test2"):
        enforce_safety_boundaries(state, stage)

    return state


# ── 模式摘要 ──────────────────────────────────────────────
def compute_patterns_summary(state: dict) -> dict:
    rounds = state.get("rounds", [])
    if not rounds:
        return _empty_patterns_summary()

    dist = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in rounds:
        dt = r.get("feedback", {}).get("deviation_type")
        if dt in dist:
            dist[dt] += 1
    dominant = max(dist, key=dist.get) if any(dist.values()) else None
    persistent = _find_persistent_issues(rounds)
    trend = _assess_convergence_trend(rounds)
    dead_zones = state.get("r_t", {}).get("dead_zones", [])
    resolved = sum(1 for d in dead_zones if isinstance(d, dict) and d.get("status") == "resolved")
    return {
        "dominant_type": dominant, "type_distribution": dist,
        "persistent_issues": persistent, "convergence_trend": trend,
        "dead_zones_resolved": resolved, "dead_zones_total": len(dead_zones),
    }


def _total_e_count(feedback: dict) -> int:
    return (len(feedback.get("e_missing", [])) +
            len(feedback.get("e_extra", [])) +
            len(feedback.get("e_wrong", [])))


def _assess_convergence_trend(rounds: list) -> str:
    recent = rounds[-3:]
    counts = []
    for r in recent:
        fb = r.get("feedback", {})
        if fb:
            counts.append(_total_e_count(fb))
    if len(counts) < 2:
        return "unknown"
    if all(counts[i] >= counts[i + 1] for i in range(len(counts) - 1)):
        return "converging" if counts[-1] < counts[0] else "stagnant"
    return "diverging"


def _find_persistent_issues(rounds: list) -> list[str]:
    if len(rounds) < 2:
        return []
    issues = []
    descs_by_round = []
    for r in rounds:
        fb = r.get("feedback", {})
        descs = set()
        for cat in ("e_missing", "e_extra", "e_wrong"):
            for item in fb.get(cat, []):
                d = item.get("description") or item.get("requirement_id") or str(item)
                descs.add(d)
        descs_by_round.append(descs)
    for desc in descs_by_round[-1]:
        count = sum(1 for d_set in descs_by_round if desc in d_set)
        if count >= 2:
            issues.append(desc)
    return issues


# ── 安全边界 ──────────────────────────────────────────────
class SafetyBoundaryError(Exception):
    """触发安全边界时抛出。"""
    pass


def enforce_safety_boundaries(state: dict, action: str) -> None:
    """在 modify/test1/test2 前检查安全边界。L1 极简路径跳过。"""
    enforce = state.get("_enforce", {})
    if enforce.get("minimal_path_only"):
        return

    nmax = state.get("nmax", -1)
    if nmax != -1 and state["round"] > nmax:
        raise SafetyBoundaryError(
            f"Nmax ({nmax}) 已超限（当前第 {state['round']} 轮）。"
            "请使用 handoff_report.py 向人移交，或 reset 后重新开始。禁止继续修改。"
        )

    rounds = state.get("rounds", [])
    if action == "modify" and len(rounds) >= 2:
        last_two = rounds[-2:]
        f0 = last_two[0].get("feedback", {})
        f1 = last_two[1].get("feedback", {})
        if f0.get("deviation_type") == f1.get("deviation_type") == "A":
            if _total_e_count(f1) > _total_e_count(f0):
                raise SafetyBoundaryError(
                    "连续两轮偏差同向增大（近临界状态），禁止增大干预强度 k。建议触发二阶审计。"
                )

    if action == "modify":
        pf = state.get("positive_feedback", "off")
        audit_confirmed = state.get("_audit_confirmed_at")
        if pf == "on_after_audit" and not audit_confirmed:
            print("[!] 正反馈加速已开启，但 r(t) 最近未经审计确认。建议先执行审计。", file=sys.stderr)


# ── 审计结论反馈 ──────────────────────────────────────────
def apply_audit_conclusion(state: dict, conclusion: str, new_rt: dict = None) -> dict:
    """根据审计结论修改控制参数。"""
    if conclusion == "maintain":
        state["audit_counter"] = 0
    elif conclusion == "reset-rt":
        if not new_rt:
            raise ValueError("reset-rt 需要 --new-rt 参数指定新的 r(t)")
        state["archived_rounds"].extend(state["rounds"])
        state["rounds"] = []
        state["round"] = 1
        state["r_t"] = new_rt
        state["verdict"] = "continuing"
        state["convergence"] = False
    elif conclusion == "restructure":
        state["nmax"] = (state["nmax"] or 5) + 2
        state["audit_every"] = max(2, state.get("audit_every", 3) - 1)
        state["positive_feedback"] = "off"
        ps = state.get("_patterns_summary", {})
        if ps.get("dominant_type"):
            state.setdefault("structural_patterns", []).append({
                "description": f"审计结论 restructure：主导偏差 {ps['dominant_type']} 持续 {ps.get('type_distribution', {}).get(ps['dominant_type'], 0)} 轮",
                "round": state["round"],
            })
    elif conclusion == "upgrade-forum":
        state["upgrade_to_forum"] = True
        print("→ 研讨厅模式已激活。转至 diversity_generator.py 执行研讨厅流程。", file=sys.stderr)
    else:
        raise ValueError(f"未知审计结论: {conclusion}，可选: maintain|reset-rt|restructure|upgrade-forum")
    return state


# ── HITL 暂停/恢复 ────────────────────────────────────────
def pause_state(state: dict, reason: str, options: list[str], deadline: str = None) -> dict:
    state["paused"] = {
        "active": True, "reason": reason,
        "paused_at": datetime.now(timezone.utc).isoformat(),
        "deadline": deadline, "decision_options": options,
    }
    return state


def resume_state(state: dict) -> dict:
    if not state.get("paused", {}).get("active"):
        print("[!] 状态未处于暂停中。", file=sys.stderr)
    state["paused"] = {"active": False, "reason": None, "paused_at": None, "deadline": None, "decision_options": []}
    return state


# ── 查询 ──────────────────────────────────────────────────
def query_state(state: dict, pattern: str, scope: str = "all", last_n: int = None) -> list[dict]:
    """在状态文件内做结构化正则搜索。"""
    matches = []
    regex = re.compile(pattern, re.IGNORECASE)
    rounds = state.get("rounds", [])
    if last_n:
        rounds = rounds[-last_n:]

    if scope in ("rounds", "all"):
        for r in rounds:
            text = json.dumps(r, ensure_ascii=False)
            for m in regex.finditer(text):
                matches.append({"round": r["n"], "field": "rounds", "snippet": m.group()[:120], "severity": "info"})

    if scope in ("audit_log", "all"):
        for a in state.get("audit_log", []):
            text = json.dumps(a, ensure_ascii=False)
            for m in regex.finditer(text):
                matches.append({"round": a.get("round", "?"), "field": "audit_log", "snippet": m.group()[:120], "severity": "info"})

    if scope in ("structural_patterns", "all"):
        for sp in state.get("structural_patterns", []):
            text = json.dumps(sp, ensure_ascii=False)
            for m in regex.finditer(text):
                matches.append({"round": sp.get("round", "?"), "field": "structural_patterns", "snippet": m.group()[:120], "severity": "info"})

    return matches


# ── 归档 ──────────────────────────────────────────────────
def archive_state(state: dict, target_dir: str, overwrite: bool = False) -> str:
    """将摘要追加到 archive.ndjson。"""
    os.makedirs(target_dir, exist_ok=True)
    archive_path = os.path.join(target_dir, "archive.ndjson")
    record = {
        "task": state["task"], "level": state["level"],
        "total_rounds": len(state["rounds"]), "final_verdict": state.get("verdict"),
        "patterns_summary": state.get("_patterns_summary", {}),
        "archived_at": datetime.now(timezone.utc).isoformat(),
    }
    if overwrite and os.path.exists(archive_path):
        lines = []
        with open(archive_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    if json.loads(line).get("task") != state["task"]:
                        lines.append(line)
                except json.JSONDecodeError:
                    lines.append(line)
        with open(archive_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    with open(archive_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return archive_path


# ── 迁移 ──────────────────────────────────────────────────
def migrate_state(path: str, dry_run: bool = False) -> dict:
    """执行版本迁移。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"状态文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    ver = state.get("_version", "0.9")
    if ver == STATE_SCHEMA_VERSION:
        print(f"已是 {STATE_SCHEMA_VERSION} 版本，无需迁移。")
        return state
    orig_ver = ver
    while ver != STATE_SCHEMA_VERSION:
        if ver not in STATE_MIGRATORS:
            raise ValueError(f"状态文件版本 {ver} 无法迁移到 {STATE_SCHEMA_VERSION}")
        state = STATE_MIGRATORS[ver](state)
        ver = state["_version"]
    if not dry_run:
        bak = f"{path}.v{orig_ver}.bak"
        shutil.copy2(path, bak)
        save_state(state, path)
        print(f"已迁移 {orig_ver} → {STATE_SCHEMA_VERSION}，备份: {bak}")
    else:
        print(f"[dry-run] 将迁移 {orig_ver} → {STATE_SCHEMA_VERSION}")
    return state


# ── 并发锁 ────────────────────────────────────────────────
class LockHeldError(Exception):
    pass


def acquire_lock(state: dict, holder: str, timeout_sec: int = 300) -> dict:
    lock = state.get("_lock", {})
    now = datetime.now(timezone.utc).isoformat()
    if lock.get("held_by") and lock.get("expires_at", "0") > now:
        raise LockHeldError(f"状态文件被 {lock['held_by']} 锁定至 {lock['expires_at']}")
    state["_lock"] = {
        "held_by": holder,
        "acquired_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=timeout_sec)).isoformat(),
    }
    state["_last_modified_by"] = holder
    return state


def release_lock(state: dict, holder: str, force: bool = False) -> dict:
    lock = state.get("_lock", {})
    if lock.get("held_by") != holder and not force:
        raise LockHeldError(f"锁由 {lock.get('held_by')} 持有，{holder} 无权释放")
    state["_lock"] = {"held_by": None, "acquired_at": None, "expires_at": None}
    return state


# ── 重置 ──────────────────────────────────────────────────
def reset_state(state: dict, hard: bool = False, path: str = None) -> dict:
    path = path or resolve_path()
    if not hard:
        bak = path + ".bak"
        shutil.copy2(path, bak)
        print(f"已备份至 {bak}")
    task = state["task"]
    level = state["level"]
    nmax = state["nmax"]
    audit_every = state["audit_every"]
    enforce = state.get("_enforce")
    return init_state(task, level, nmax, audit_every, enforce_from=None, path=path)


# ── 摘要 ──────────────────────────────────────────────────
def summary_text(state: dict) -> str:
    ps = state.get("_patterns_summary", {})
    lines = [
        f"任务: {state['task']} | 层级: {state['level']} | 轮次: {state['round']}/{state.get('nmax', '∞')}",
        f"判定: {state.get('verdict', '?')} | 收敛: {state.get('convergence', False)}",
        f"主导偏差: {ps.get('dominant_type', '无')} | 趋势: {ps.get('convergence_trend', '?')}",
        f"偏差分布: A={ps.get('type_distribution',{}).get('A',0)} B={ps.get('type_distribution',{}).get('B',0)} C={ps.get('type_distribution',{}).get('C',0)} D={ps.get('type_distribution',{}).get('D',0)}",
        f"审计计数: {state.get('audit_counter',0)}/{state.get('audit_every',3)}",
        f"暂停: {'是' if state.get('paused',{}).get('active') else '否'} | 研讨厅: {'是' if state.get('upgrade_to_forum') else '否'}",
    ]
    if ps.get("persistent_issues"):
        lines.append(f"持续问题: {', '.join(ps['persistent_issues'][:3])}")
    return "\n".join(lines)


def validate_state(state: dict) -> list[str]:
    issues = []
    required = ["_version", "task", "level", "round", "nmax", "r_t", "rounds", "audit_log"]
    for k in required:
        if k not in state:
            issues.append(f"缺少必需字段: {k}")
    if state.get("_version") != STATE_SCHEMA_VERSION:
        issues.append(f"版本不匹配: {state.get('_version')} != {STATE_SCHEMA_VERSION}")
    for r in state.get("rounds", []):
        if not isinstance(r, dict):
            issues.append(f"rounds 中包含非 dict 元素: {r}")
    return issues


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Project Cybersyn 迭代状态管理器 v2.0")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p = sub.add_parser("init", help="创建新状态文件")
    p.add_argument("--level", required=True, choices=["L1", "L2", "L3", "L4"])
    p.add_argument("--task", required=True)
    p.add_argument("--nmax", type=int)
    p.add_argument("--audit-every", type=int, dest="audit_every")
    p.add_argument("--enforce-from")
    p.add_argument("--output")

    # read
    p = sub.add_parser("read", help="读取状态")
    p.add_argument("--field", default="all")
    p.add_argument("--last-round", action="store_true")
    p.add_argument("--format", default="json", choices=["json", "text"])

    # update
    p = sub.add_parser("update", help="更新轮次数据")
    p.add_argument("--stage", required=True, choices=["plan", "test1", "feedback", "modify", "test2", "output", "audit"])
    p.add_argument("--data", required=True)
    p.add_argument("--round", type=int, dest="round_n")

    # reset
    p = sub.add_parser("reset", help="重置状态")
    p.add_argument("--hard", action="store_true")

    # query
    p = sub.add_parser("query", help="搜索状态")
    p.add_argument("--pattern", required=True)
    p.add_argument("--scope", default="all", choices=["rounds", "audit_log", "structural_patterns", "all"])
    p.add_argument("--last", type=int)
    p.add_argument("--format", default="json", choices=["json", "text"])

    # archive
    p = sub.add_parser("archive", help="归档摘要")
    p.add_argument("--target", default="./cybersyn_archive")
    p.add_argument("--overwrite", action="store_true")

    # apply-audit
    p = sub.add_parser("apply-audit", help="应用审计结论")
    p.add_argument("--conclusion", required=True, choices=["maintain", "reset-rt", "restructure", "upgrade-forum"])
    p.add_argument("--new-rt")
    p.add_argument("--dry-run", action="store_true")

    # pause
    p = sub.add_parser("pause", help="暂停任务（HITL）")
    p.add_argument("--reason", required=True)
    p.add_argument("--options", required=True)
    p.add_argument("--deadline")

    # resume
    sub.add_parser("resume", help="恢复任务")

    # migrate
    p = sub.add_parser("migrate", help="迁移状态版本")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--state", dest="state_path")

    # lock
    p = sub.add_parser("lock", help="获取协作式锁")
    p.add_argument("--by", required=True, dest="holder")
    p.add_argument("--timeout", type=int, default=300)

    # unlock
    p = sub.add_parser("unlock", help="释放协作式锁")
    p.add_argument("--by", required=True, dest="holder")
    p.add_argument("--force", action="store_true")

    # summary
    sub.add_parser("summary", help="人类可读摘要")

    # validate
    sub.add_parser("validate", help="校验状态文件格式")

    args = parser.parse_args()

    try:
        if args.command == "init":
            state = init_state(args.task, args.level, args.nmax, args.audit_every,
                               args.enforce_from, args.output)
            print(json.dumps({"status": "ok", "path": args.output or resolve_path()}, ensure_ascii=False))

        elif args.command == "read":
            state = load_state()
            if args.last_round and state["rounds"]:
                output = state["rounds"][-1]
            elif args.field == "all":
                output = state
            else:
                output = state.get(args.field)
            if args.format == "text":
                if isinstance(output, dict):
                    print(json.dumps(output, ensure_ascii=False, indent=2))
                else:
                    print(output)
            else:
                print(json.dumps(output, ensure_ascii=False, indent=2))

        elif args.command == "update":
            state = load_state()
            data = json.loads(args.data) if not args.data.startswith("@") else \
                   json.loads(Path(args.data[1:]).read_text(encoding="utf-8"))
            state = update_round(state, args.stage, data, args.round_n)
            save_state(state)
            print(json.dumps({"status": "ok", "round": state["round"]}, ensure_ascii=False))

        elif args.command == "reset":
            path = resolve_path()
            if not os.path.exists(path):
                raise FileNotFoundError(f"状态文件不存在: {path}")
            state = load_state(path)
            state = reset_state(state, args.hard, path)
            print(json.dumps({"status": "ok", "message": "状态已重置"}, ensure_ascii=False))

        elif args.command == "query":
            state = load_state()
            matches = query_state(state, args.pattern, args.scope, args.last)
            if args.format == "text":
                for m in matches:
                    print(f"[轮次 {m['round']}] [{m['field']}] {m['snippet']}")
                print(f"--- 共 {len(matches)} 条匹配 ---")
            else:
                print(json.dumps({"matches": matches}, ensure_ascii=False, indent=2))

        elif args.command == "archive":
            state = load_state()
            p = archive_state(state, args.target, args.overwrite)
            print(json.dumps({"status": "ok", "archive_path": p}, ensure_ascii=False))

        elif args.command == "apply-audit":
            state = load_state()
            new_rt = json.loads(args.new_rt) if args.new_rt else None
            if args.dry_run:
                preview = deepcopy(state)
                preview = apply_audit_conclusion(preview, args.conclusion, new_rt)
                changes = {k: v for k, v in preview.items() if k in state and state[k] != v}
                print(json.dumps({"dry_run": True, "conclusion": args.conclusion, "changes": changes}, ensure_ascii=False, indent=2, default=str))
            else:
                state = apply_audit_conclusion(state, args.conclusion, new_rt)
                save_state(state)
                print(json.dumps({"status": "ok", "conclusion": args.conclusion}, ensure_ascii=False))

        elif args.command == "pause":
            state = load_state()
            options = [o.strip() for o in args.options.split(",")]
            state = pause_state(state, args.reason, options, args.deadline)
            save_state(state)
            print(json.dumps({"status": "ok", "paused": True}, ensure_ascii=False))

        elif args.command == "resume":
            state = load_state()
            state = resume_state(state)
            save_state(state)
            print(json.dumps({"status": "ok", "paused": False}, ensure_ascii=False))

        elif args.command == "migrate":
            path = args.state_path or resolve_path()
            migrate_state(path, args.dry_run)

        elif args.command == "lock":
            state = load_state()
            state = acquire_lock(state, args.holder, args.timeout)
            save_state(state)
            print(json.dumps({"status": "ok", "locked_by": args.holder}, ensure_ascii=False))

        elif args.command == "unlock":
            state = load_state()
            state = release_lock(state, args.holder, args.force)
            save_state(state)
            print(json.dumps({"status": "ok", "unlocked": True}, ensure_ascii=False))

        elif args.command == "summary":
            state = load_state()
            print(summary_text(state))

        elif args.command == "validate":
            state = load_state()
            issues = validate_state(state)
            if issues:
                print(json.dumps({"valid": False, "issues": issues}, ensure_ascii=False, indent=2))
                sys.exit(1)
            else:
                print(json.dumps({"valid": True}, ensure_ascii=False))

    except (FileNotFoundError, FileExistsError, ValueError, SafetyBoundaryError, LockHeldError) as e:
        print(json.dumps({"error": str(e), "code": 1}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"JSON 解析错误: {e}", "code": 2}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
