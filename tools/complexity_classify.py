#!/usr/bin/env python3
"""
complexity_classify.py — Project Cybersyn 复杂度分类器 (v2.0)

根据任务描述和上下文辅助判定 L1-L4，生成强制执行约束（--enforce）。

用法示例:
  complexity_classify.py --task "修改单行 bug"
  complexity_classify.py --task "重构 auth 模块" --files auth.py,token.py --dependencies "user,cache" --enforce
"""

import argparse
import json
import re
import sys

# Windows 控制台/管道默认 GBK，统一 UTF-8 输出避免乱码
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


# ── 判定规则 ──────────────────────────────────────────────
VAGUE_KEYWORDS = ["优化", "改进", "合理的", "适当的", "尽可能", "大概", "差不多", "改善", "提升"]
ENV_VOLATILE_KEYWORDS = ["持续变化", "不确定", "探索", "创业", "政策", "策略方向", "是否应该",
                          "研究方向", "长期", "动态", "多变", "试验",
                          "explore", "uncertain", "startup", "policy", "strategy", "dynamic", "volatile", "research direction"]
HOMOGENEOUS_EXTENSIONS = {".test.py", ".test.ts", ".spec.ts", "_test.go", ".spec.js"}


def count_files(task: str, explicit_files: list) -> int:
    if explicit_files:
        return len(explicit_files)
    # 从任务描述推断
    nums = re.findall(r'(\d+)\s*(个|文件|模块)', task)
    if nums:
        return int(nums[0][0])
    return 1


def detect_heterogeneity(files: list, deps: list) -> bool:
    """判断是否异构。"""
    if not files:
        return bool(deps and len(deps) >= 3)
    # 检查文件扩展名多样性
    exts = set()
    for f in files:
        _, ext = (f.rsplit(".", 1) if "." in f else (f, ""))
        exts.add(ext)
    if len(exts) >= 2:
        return True
    # 检查依赖是否跨子系统
    if deps and len(deps) >= 2:
        # 不同领域的依赖（auth/cache/user/db/api）→ 异构
        domains = set(d.split("/")[0].split(".")[0].lower() for d in deps)
        if len(domains) >= 2:
            return True
    return False


def assess_requirement_clarity(task: str) -> str:
    """扫描模糊词。"""
    task_lower = task.lower()
    hits = sum(1 for kw in VAGUE_KEYWORDS if kw in task_lower)
    if hits >= 3:
        return "vague"
    elif hits >= 1:
        return "medium"
    return "clear"


def detect_env_volatility(task: str) -> str:
    """检测环境波动性。"""
    task_lower = task.lower()
    hits = sum(1 for kw in ENV_VOLATILE_KEYWORDS if kw in task_lower)
    if hits >= 2:
        return "volatile"
    elif hits >= 1:
        return "uncertain"
    return "stable"


def is_homogeneous(files: list) -> bool:
    """判断是否同质。"""
    if not files:
        return False
    exts = set()
    for f in files:
        parts = f.rsplit(".", 1)
        ext = "." + parts[-1] if len(parts) > 1 else ""
        base = f.rsplit("_", 1)[0] if "_" in f else f
        exts.add(ext)
        if ext in HOMOGENEOUS_EXTENSIONS:
            return True
    return len(exts) == 1


def generate_enforce(level: str) -> dict:
    """按 level 生成 enforce 配置。"""
    return {
        "L1": {"allow_audit": False, "allow_vsm": False, "allow_positive_feedback": False,
               "allow_handoff_report": False, "allow_forum": False, "minimal_path_only": True,
               "nmax": 2, "audit_every": 5},
        "L2": {"allow_audit": True, "allow_vsm": False, "allow_positive_feedback": False,
               "allow_handoff_report": True, "allow_forum": False, "minimal_path_only": False,
               "nmax": 3, "audit_every": 3},
        "L3": {"allow_audit": True, "allow_vsm": True, "allow_positive_feedback": False,
               "allow_handoff_report": True, "allow_forum": False, "minimal_path_only": False,
               "nmax": 5, "audit_every": 3},
        "L4": {"allow_audit": True, "allow_vsm": True, "allow_positive_feedback": False,
               "allow_handoff_report": True, "allow_forum": True, "minimal_path_only": False,
               "nmax": -1, "audit_every": 3},
    }.get(level, {})


def classify(task: str, files: list, deps: list) -> dict:
    """综合分类。"""
    file_count = count_files(task, files)
    heterogeneity = detect_heterogeneity(files, deps)
    clarity = assess_requirement_clarity(task)
    volatility = detect_env_volatility(task)
    homogeneous = is_homogeneous(files)

    # 判定
    level = "L1"
    confidence = 0.8
    factors = {
        "file_count": {"value": file_count, "tendency": "L1" if file_count <= 2 else ("L2" if file_count <= 5 else "L3")},
        "heterogeneity": {"value": heterogeneity, "tendency": "L3" if heterogeneity else "L1"},
        "requirement_clarity": {"value": clarity, "tendency": "L1" if clarity == "clear" else "L2"},
        "env_stability": {"value": volatility, "tendency": "L4" if volatility == "volatile" else ("L2" if volatility == "uncertain" else "L1")},
        "homogeneity": {"value": homogeneous, "tendency": "L2" if homogeneous and file_count > 2 else "N/A"},
    }

    # 投票加权
    if volatility == "volatile":
        level = "L4"
    elif heterogeneity and file_count >= 3:
        level = "L3"
    elif file_count > 2 and homogeneous:
        level = "L2"
    elif file_count > 2 and not homogeneous:
        level = "L3"
    elif clarity in ("vague", "medium") and volatility == "uncertain":
        level = "L2"
    elif deps and len(deps) >= 2 and file_count <= 2:
        level = "L2"
    else:
        level = "L1" if file_count <= 2 else "L2"

    if deps and len(deps) >= 3 and not homogeneous:
        level = "L3"

    # 置信度
    consistent = sum(1 for v in factors.values()
                     if v.get("tendency") == level or v.get("tendency") == "N/A")
    total = len([v for v in factors.values() if v.get("tendency") != "N/A"])
    confidence = round(min(consistent, total) / total, 2) if total > 0 else 0.5

    path_map = {
        "L1": "极简路径：计划 → 改 → 对照 → 交付",
        "L2": "一阶闭环 + 统计采样",
        "L3": "全流程 + 四分类 + 二阶审计",
        "L4": "全流程 + 环境检测 + 研讨厅",
    }

    result = {
        "level": level,
        "confidence": confidence,
        "factors": factors,
        "recommended": {
            "path": path_map.get(level, ""),
            "nmax": {"L1": 2, "L2": 3, "L3": 5, "L4": -1}[level],
            "audit_every": {"L1": 5, "L2": 3, "L3": 3, "L4": 3}[level],
            "vsm": level in ("L3", "L4"),
            "positive_feedback": "off",
        },
        "warnings": [],
        "explanation": _build_explanation(level, factors),
    }

    if clarity == "vague":
        result["warnings"].append("需求模糊度高，建议先澄清再执行。")
    if volatility == "volatile":
        result["warnings"].append("环境波动性高，建议人工确认 L4 判定。")
    if level == "L4":
        result["warnings"].append("L4 建议人工确认。")

    # 矛盾检测
    tendencies = [v.get("tendency") for v in factors.values() if v.get("tendency") != "N/A"]
    if len(set(tendencies)) >= 3:
        result["warnings"].append(f"各因子倾向不一致: {set(tendencies)}，取最高复杂度。")

    return result


def _build_explanation(level: str, factors: dict) -> str:
    parts = []
    fc = factors.get("file_count", {})
    if fc.get("value", 0) > 0:
        parts.append(f"{fc['value']} 文件")
    het = factors.get("heterogeneity", {})
    if het.get("value"):
        parts.append("异构模块")
    env = factors.get("env_stability", {})
    if env.get("value") != "stable":
        parts.append(f"环境{env.get('value','?')}")
    clarity = factors.get("requirement_clarity", {})
    if clarity.get("value") != "clear":
        parts.append(f"需求{clarity.get('value','?')}")
    return f"{', '.join(parts) if parts else '简单任务'} → {level}"


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Project Cybersyn 复杂度分类器 v2.0")
    parser.add_argument("--task", required=True, help="任务描述")
    parser.add_argument("--files", help="涉及文件（逗号分隔）")
    parser.add_argument("--dependencies", help="依赖模块（逗号分隔）")
    parser.add_argument("--enforce", action="store_true", help="输出 enforce 配置")
    parser.add_argument("--format", default="json", choices=["json", "text"])

    args = parser.parse_args()

    try:
        files = [f.strip() for f in args.files.split(",")] if args.files else []
        deps = [d.strip() for d in args.dependencies.split(",")] if args.dependencies else []

        result = classify(args.task, files, deps)

        if args.enforce:
            result["enforce"] = generate_enforce(result["level"])

        if args.format == "text":
            print(f"复杂度: {result['level']} (置信度: {result['confidence']})")
            print(f"建议路径: {result['recommended']['path']}")
            print(f"推荐参数: nmax={result['recommended']['nmax']}, audit_every={result['recommended']['audit_every']}")
            print(f"解释: {result['explanation']}")
            for w in result.get("warnings", []):
                print(f"  [!] {w}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e), "code": 1}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
