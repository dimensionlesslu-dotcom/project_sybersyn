#!/usr/bin/env python3
"""
diversity_generator.py — Project Cybersyn 研讨厅多模型分歧生成器

当系统进入研讨厅模式（L4/持续不收敛）时，对同一问题生成 >=3 个不同结构/策略的备选方案，
计算预测分歧矩阵。不依赖 LLM，只生成策略模板和框架性描述。

用法示例:
  diversity_generator.py --task "重构 auth 模块" --strategies 3
  diversity_generator.py --task "..." --context cybersyn_state.json --strategies 3 --output report.md
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows 控制台/管道默认 GBK，统一 UTF-8 输出避免乱码
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

# ── 策略模板 ──────────────────────────────────────────────
PERSPECTIVES = {
    "conservative": {
        "name": "保守型：局部优化",
        "principles": [
            "在现有模块边界内修改，不引入新抽象层",
            "优先修复偏差中 severity=critical 的项",
            "保持现有接口签名不变",
            "最小化对关联模块的扰动",
        ],
        "effort_profile": {"files": "1-2", "new_abstractions": 0, "risk": "低"},
    },
    "refactor": {
        "name": "重构型：结构优化",
        "principles": [
            "识别并消除 structural_patterns 中的结构性问题",
            "引入必要的抽象层/接口以降低耦合",
            "可能改变内部模块边界，但对外接口兼容",
            "接受短期偏差增加以换取长期可维护性",
        ],
        "effort_profile": {"files": "3-8", "new_abstractions": "1-3", "risk": "中"},
    },
    "exploratory": {
        "name": "探索型：替代方案",
        "principles": [
            "试探新架构假设，探索与当前方案根本不同的路径",
            "可能引入新技术/框架/架构模式",
            "重视长期灵活性而非短期稳定性",
            "方案本身用于验证假设，不一定落地",
        ],
        "effort_profile": {"files": "5-12", "new_abstractions": "2-5", "risk": "高"},
    },
    "decompose": {
        "name": "分解型：降低耦合",
        "principles": [
            "将紧密耦合的模块拆分为独立子系统",
            "每个子系统可独立开发、测试、部署",
            "引入明确的子系统边界和通信协议",
            "优先消除涌现偏差(D)的交互源",
        ],
        "effort_profile": {"files": "3-6", "new_abstractions": "2-4", "risk": "中"},
    },
    "integrate": {
        "name": "整合型：减少冗余",
        "principles": [
            "合并功能重复的模块/接口，消除多余(e_extra)来源",
            "统一配置、日志、错误处理等横切关注点",
            "减少接口数量以降低认知负荷",
            "适用于 extra 项持续增多的场景",
        ],
        "effort_profile": {"files": "2-5", "new_abstractions": "0-1", "risk": "低-中"},
    },
}

# 策略视角自动选择启发式
AUTO_SELECT_RULES = [
    # (条件函数, 推荐视角列表)
    (lambda c: c.get("dominant_type") == "D", ["decompose", "refactor", "conservative"]),
    (lambda c: c.get("dominant_type") == "C" or c.get("env_signal_count", 0) > 1,
     ["exploratory", "refactor", "conservative"]),
    (lambda c: (c.get("type_distribution", {}).get("A", 0) >= 3 and c.get("convergence_trend") in ("stagnant", "diverging")),
     ["refactor", "decompose", "conservative"]),
    (lambda c: c.get("extra_count", 0) > c.get("missing_count", 0) + c.get("wrong_count", 0),
     ["integrate", "refactor", "conservative"]),
    (lambda c: c.get("level") == "L4", ["exploratory", "refactor", "decompose"]),
]


# ── 策略选择 ──────────────────────────────────────────────
def load_context(path: str) -> dict:
    """从状态文件读取偏差历史和结构模式。"""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    ps = state.get("_patterns_summary", {})
    env = state.get("_env_change_signals", {})
    return {
        "level": state.get("level", "L3"),
        "round": state.get("round", 0),
        "dominant_type": ps.get("dominant_type"),
        "type_distribution": ps.get("type_distribution", {}),
        "convergence_trend": ps.get("convergence_trend", "unknown"),
        "persistent_issues": ps.get("persistent_issues", []),
        "structural_patterns": [s.get("description", str(s)) for s in state.get("structural_patterns", [])],
        "env_signal_count": env.get("count", 0),
        "extra_count": ps.get("type_distribution", {}).get("extra", 0),
        "missing_count": ps.get("type_distribution", {}).get("missing", 0),
        "wrong_count": ps.get("type_distribution", {}).get("wrong", 0),
        "upgrade_to_forum": state.get("upgrade_to_forum", False),
    }


def auto_select_perspectives(context: dict, count: int) -> list[str]:
    """基于上下文自动选择最有差异性的策略视角组合。"""
    if not context:
        return ["conservative", "refactor", "exploratory"][:count]

    for condition, perspectives in AUTO_SELECT_RULES:
        if condition(context):
            return perspectives[:count]

    return ["conservative", "refactor", "exploratory"][:count]


# ── 策略生成 ──────────────────────────────────────────────
def generate_strategy(perspective: str, task: str, context: dict, index: int) -> dict:
    """基于视角模板 + 上下文，生成一个策略方案。"""
    tmpl = PERSPECTIVES.get(perspective, PERSPECTIVES["conservative"])
    persistent_str = ", ".join(context.get("persistent_issues", [])[:3]) if context.get("persistent_issues") else "无已知持续问题"
    structural_str = "; ".join(context.get("structural_patterns", [])[:2]) if context.get("structural_patterns") else "无记录的结构性问题"

    # 各视角的预测模板
    predictions = {
        "conservative": f"解决当前偏差列表中的关键项，不改变架构复杂度。预计 {tmpl['effort_profile']['files']} 文件修改。",
        "refactor": f"从结构层面解决: {structural_str}。短期可能引入新偏差，长期降低维护成本。预计 {tmpl['effort_profile']['files']} 文件修改。",
        "exploratory": f"探索与当前方案根本不同的路径，验证新架构假设。短期不确定性大，长期可能获得最高灵活性。预计 {tmpl['effort_profile']['files']} 文件修改 + 可能需要新组件。",
        "decompose": f"将耦合模块拆分为独立子系统，消除交互产生的涌现偏差。预计 {tmpl['effort_profile']['files']} 文件修改，引入 {tmpl['effort_profile']['new_abstractions']} 个新接口。",
        "integrate": f"合并冗余功能，减少接口数量。预计消除 {context.get('extra_count', 0)} 个多余项。预计 {tmpl['effort_profile']['files']} 文件修改。",
    }

    return {
        "name": f"策略 {chr(65 + index)}：{tmpl['name']}",
        "perspective": perspective,
        "description": f"针对任务「{task}」的 {tmpl['name'].split('：')[1] if '：' in tmpl['name'] else tmpl['name']} 策略",
        "principles": tmpl["principles"],
        "estimated_effort": tmpl["effort_profile"]["files"] + " 文件修改" + (
            f" + {tmpl['effort_profile']['new_abstractions']} 新接口/抽象" if tmpl["effort_profile"]["new_abstractions"] else ""
        ),
        "risk": tmpl["effort_profile"]["risk"],
        "predicted_outcome": predictions.get(perspective, predictions["conservative"]),
        "context_notes": {
            "persistent_issues": persistent_str,
            "structural_patterns": structural_str,
            "env_stability": "有环境变化信号" if context.get("env_signal_count", 0) > 0 else "环境稳定",
        },
    }


# ── 分歧分析 ──────────────────────────────────────────────
DIVERGENCE_DIMENSIONS = {
    "conservative": {
        "architecture_change": "无架构变更",
        "coupling": "保持现有耦合度",
        "new_components": "0",
        "test_surface": "小（仅修改区域）",
        "rollback_cost": "低",
    },
    "refactor": {
        "architecture_change": "中等（模块内部重构）",
        "coupling": "降低（引入抽象层）",
        "new_components": "1-3 接口/抽象",
        "test_surface": "中（重构模块全覆盖）",
        "rollback_cost": "中",
    },
    "exploratory": {
        "architecture_change": "大（可能颠覆现有架构）",
        "coupling": "根本性改变耦合关系",
        "new_components": "2-5 新组件",
        "test_surface": "大（新架构需全套测试）",
        "rollback_cost": "高",
    },
    "decompose": {
        "architecture_change": "中-大（模块拆分重组）",
        "coupling": "显著降低（独立子系统）",
        "new_components": "2-4 子系统边界",
        "test_surface": "中（子系统集成测试）",
        "rollback_cost": "中-高",
    },
    "integrate": {
        "architecture_change": "小-中（合并冗余）",
        "coupling": "降低（减少接口数）",
        "new_components": "0-1",
        "test_surface": "小-中（验证合并正确性）",
        "rollback_cost": "低-中",
    },
}


def compute_divergence(strategies: list[dict]) -> dict:
    """比较各策略的关键设计维度，提取分歧矩阵。"""
    perspectives = [s["perspective"] for s in strategies]
    dims = {}
    for dim in ["architecture_change", "coupling", "new_components", "test_surface", "rollback_cost"]:
        vals = {}
        for p in perspectives:
            vals[p] = DIVERGENCE_DIMENSIONS.get(p, {}).get(dim, "未知")
        if len(set(vals.values())) > 1:
            dims[dim] = vals

    # 共享假设
    shared = ["任务目标不变", "对外公开 API 签名最终兼容（除非探索型）"]

    # 关键分歧维度
    disagreements = []
    for dim, vals in dims.items():
        dim_label = {
            "architecture_change": "架构变更范围",
            "coupling": "模块耦合策略",
            "new_components": "新增组件数量",
            "test_surface": "测试影响面",
            "rollback_cost": "回滚成本",
        }.get(dim, dim)
        disagreements.append({"dimension": dim_label, "strategies": vals})

    # 预测分歧定性
    unique_predictions = set(s["predicted_outcome"][:80] for s in strategies)
    pred_div = "各策略预测结果" + ("存在显著差异" if len(unique_predictions) > 1 else "方向基本一致")

    return {
        "shared_assumptions": shared,
        "key_disagreements": disagreements,
        "prediction_divergence": pred_div,
    }


# ── 输出 ──────────────────────────────────────────────────
def render_json(task: str, strategies: list, divergence: dict, context: dict) -> dict:
    return {
        "task": task,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context_from_state": context,
        "strategies": strategies,
        "divergence_matrix": divergence,
        "recommendation": _infer_recommendation(strategies, divergence),
        "human_review_required": True,
    }


def render_markdown(task: str, strategies: list, divergence: dict, context: dict) -> str:
    upgrade_flag = "[!] **研讨厅模式**  \n\n" if context.get("upgrade_to_forum") else ""
    lines = [
        f"# 研讨厅：多模型分歧分析 — {task}",
        "",
        upgrade_flag,
        f"**生成时间**：{datetime.now(timezone.utc).isoformat()}  ",
        f"**复杂度**：{context.get('level', '?')} | **当前轮次**：{context.get('round', '?')} | **主导偏差**：{context.get('dominant_type', '?')}  ",
        "",
        "---",
        "",
    ]

    for i, s in enumerate(strategies):
        risk_icon = {"低": "[L]", "中": "[M]", "高": "[H]", "低-中": "[L][M]", "中-高": "[M][H]"}.get(s["risk"], "⚪")
        lines += [
            f"## {s['name']}",
            "",
            f"**风险**：{risk_icon} {s['risk']} | **预估工作量**：{s['estimated_effort']}",
            "",
            "### 原则",
            *[f"- {p}" for p in s["principles"]],
            "",
            "### 方案描述",
            s["description"],
            "",
            "### 预测结果",
            s["predicted_outcome"],
            "",
            "---",
            "",
        ]

    lines += [
        "## 分歧矩阵",
        "",
        "### 共享假设",
        *[f"- {a}" for a in divergence.get("shared_assumptions", [])],
        "",
    ]

    for d in divergence.get("key_disagreements", []):
        lines.append(f"### {d['dimension']}")
        lines.append("")
        header = "| 策略 | 判断 |"
        sep = "|------|------|"
        rows = [f"| {p} | {v} |" for p, v in d["strategies"].items()]
        lines += [header, sep] + rows + [""]

    lines += [
        f"**关键分歧**：{divergence.get('prediction_divergence', '')}",
        "",
        "---",
        "",
        "## 建议",
        "",
        _infer_recommendation(strategies, divergence),
        "",
        "[!] **需要人工审查后决策。**",
    ]

    return "\n".join(lines)


def _infer_recommendation(strategies: list, divergence: dict) -> str:
    """从分歧中推断建议。"""
    if len(strategies) >= 3:
        mid = strategies[1]
        return (
            f"建议先采用「{mid['name']}」的最低成本第一步验证可行性，"
            f"保留未来升级到「{strategies[-1]['name']}」的灵活性。"
            f"若「{strategies[0]['name']}」可快速解决当前偏差，也可先用保守方案快速收敛。"
        )
    return "建议选择中间风险方案作为起点，保留向更激进方案升级的路径。"


# ── CLI ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Project Cybersyn 研讨厅多模型分歧生成器")
    parser.add_argument("--task", required=True, help="任务描述")
    parser.add_argument("--strategies", type=int, default=3, help="策略数（默认 3）")
    parser.add_argument("--context", help="状态文件路径 (cybersyn_state.json)")
    parser.add_argument("--perspectives", help="手动指定策略视角（逗号分隔）")
    parser.add_argument("--output", help="输出文件路径（默认 stdout）")
    parser.add_argument("--format", default="markdown", choices=["json", "markdown"])

    args = parser.parse_args()

    try:
        if args.strategies < 2:
            print("[!] 研讨厅原则要求至少 3 个不同结构的模型。当前策略数 < 2，输出仅供参考。", file=sys.stderr)

        context = load_context(args.context) if args.context else {}

        if args.perspectives:
            perspectives = [p.strip() for p in args.perspectives.split(",")]
            valid = set(PERSPECTIVES.keys())
            for p in perspectives:
                if p not in valid:
                    print(f"错误: 未知策略视角 '{p}'。可用: {', '.join(valid)}", file=sys.stderr)
                    sys.exit(2)
        else:
            perspectives = auto_select_perspectives(context, args.strategies)

        strategies = [
            generate_strategy(perspectives[i], args.task, context, i)
            for i in range(min(len(perspectives), args.strategies))
        ]
        divergence = compute_divergence(strategies)

        if args.format == "json":
            output = json.dumps(render_json(args.task, strategies, divergence, context), ensure_ascii=False, indent=2)
        else:
            output = render_markdown(args.task, strategies, divergence, context)

        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(json.dumps({"status": "ok", "output": args.output, "strategies": len(strategies)}, ensure_ascii=False))
        else:
            print(output)

    except Exception as e:
        print(json.dumps({"error": str(e), "code": 1}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
