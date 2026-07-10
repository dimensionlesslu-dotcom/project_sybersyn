# Project Cybersyn — 分级闭环控制系统

> **A Hierarchical Closed-Loop Control System for AI Agents**
>
> 基于控制论的 AI 任务执行协议——让 Agent 像精密伺服系统一样迭代校正，而非一次性猜测。

---

[![License: GPL-3.0](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Docs: CC BY 4.0](https://img.shields.io/badge/Docs-CC%20BY%204.0-green.svg)](docs/LICENSE-CC-BY.md)
[![CI](https://github.com/dimensionlesslu-dotcom/project_sybersyn/actions/workflows/smoke-test.yml/badge.svg)](https://github.com/dimensionlesslu-dotcom/project_sybersyn/actions/workflows/smoke-test.yml)
[![Status: Stable](https://img.shields.io/badge/Status-Stable-brightgreen.svg)]()

---

## 这是什么？ / What is this?

**Project Cybersyn** 是一个面向 AI Agent（如 Reasonix、Claude Code、Kimi 等）的 Skill / 执行协议。它把控制论的核心理念——闭环反馈、偏差分类、二阶审计——转化为 AI 可以直接执行的步骤。

**Project Cybersyn** is a Skill / execution protocol for AI Agents (Reasonix, Claude Code, Kimi, etc.). It translates core cybernetics concepts — closed-loop feedback, deviation classification, second-order auditing — into steps an AI can actually execute.

### 一句话总结 / One-liner

> 不赌计划完美，赌迭代自校正。
>
> *Don't bet on a perfect plan — bet on iterative self-correction.*

### 适用场景 / Use Cases

| 场景 | 复杂度 | 示例 |
|------|--------|------|
| 单文件修改、段落润色 | L1 简单 | 修一个函数 bug |
| 批量重命名、大规模测试 | L2 简单巨 | 统一 50 个文件的命名规范 |
| 多模块重构、方案设计 | L3 复杂巨 | 重构 3 个互相依赖的模块 |
| 创业、研究方向、政策 | L4 开放复杂巨 | 定义新产品方向 |

---

## 核心机制 / Core Mechanism

```
复杂度自检 → 闭环六阶段（计划→测试₁→反馈→修改→测试₂→输出）→ 交付验收门
                    ↑                                      ↓
                    └──── 二阶审计（质疑目标本身）←─────────┘
```

### 偏差四分类 / The Four Deviation Types

| 类型 | 中文 | English | 响应 |
|------|------|---------|------|
| **A** | 执行偏差 | Execution deviation | 常规调参 |
| **B** | 测量偏差 | Measurement deviation | 冻结执行，先校准 |
| **C** | 环境漂移 | Environmental drift | 暂停，重设目标 |
| **D** | 涌现偏差 | Emergent deviation | 退出回路，升级研讨厅 |

### 二阶审计 / Second-Order Audit

不只问"我做得对不对"，还问"**我以为对的东西是不是本身就是错的**"。

Not just "am I doing it right?" but "**is what I think is right, itself wrong?**"

---

## 快速开始 / Quick Start

### 安装为 Reasonix Skill

将仓库克隆到 Reasonix 的 skills 目录，或使用 `install_source` 安装：

```bash
git clone https://github.com/dimensionlesslu-dotcom/project_sybersyn.git
```

### 安装为 Claude Code / 其他 Agent Skill

将 `SKILL.md` 的内容作为系统指令或 Skill 文件导入。核心文件：

- **[SKILL.md](SKILL.md)** — 操作核心（你只需要这个）
- **[examples/](examples/)** — L1 / L3 运行示例
- **[docs/theory.md](docs/theory.md)** — 理论基础（想了解"为什么"时读）
- **[docs/references.md](docs/references.md)** — 参考文献

### 触发方式 / How to Trigger

在对话中使用以下关键词自动触发：

- 迭代优化 / iterative optimization
- 多轮修改 / multi-round revision
- 复杂重构 / complex refactoring
- 方案设计 / solution design
- 交付前对照需求 / pre-delivery requirement check
- 规划下一阶段 / next phase planning

或明确说：**"按 Cybersyn/闭环/控制论流程执行"**。

---

## 仓库结构 / Repository Structure

```
project_sybersyn/
├── SKILL.md                  # 操作核心（Skill 本体）
├── README.md                 # 你正在读的这个
├── LICENSE                   # GPL-3.0（代码）
├── REVIEWS.md                # 审核意见整合
├── CHANGELOG.md              # 版本变更
├── CONTRIBUTING.md           # 贡献指南
├── TOOLING_PLAN.md           # 配套工具规划（原始版）
├── TOOLING_PLAN_FINAL.md     # 配套工具规划（最终版）
├── .github/workflows/        # CI（smoke test，Linux + Windows）
├── docs/
│   ├── theory.md             # 理论基础
│   ├── references.md         # 参考文献
│   └── LICENSE-CC-BY.md      # CC BY 4.0（文档）
├── examples/
│   ├── L1-simple-task.md     # L1 极简路径示例
│   └── L3-complex-task.md    # L3 全流程示例（含工具用法）
├── tools/                    # 配套 Python 工具（已实现，纯 stdlib）
│   ├── README.md             # 工具说明与快速上手
│   ├── cybersyn_state.py     # 迭代状态管理器
│   ├── complexity_classify.py# 复杂度分类器 (L1–L4)
│   ├── checklist_compare.py  # 验收清单对比器
│   ├── convergence_check.py  # 收敛检测器
│   ├── audit_trigger.py      # 二阶审计触发器
│   ├── handoff_report.py     # 移交报告生成器
│   ├── diversity_generator.py# 研讨厅分歧生成器
│   └── smoke_test.py         # 工具链冒烟测试（64 项）
└── notes/                    # 内部审核笔记（不提交到 git）
```

---

## 理论基础 / Theoretical Foundation

Project Cybersyn 整合了以下控制论传统：

- **钱学森、宋健**《工程控制论》第三版（2011）—— 一阶控制回路
- **Norbert Wiener** *Cybernetics* (1948) —— 反馈、信息与控制
- **W. Ross Ashby** *An Introduction to Cybernetics* (1956) —— 必要多样性定律
- **Stafford Beer** *Brain of the Firm* (1972) —— 活系统模型 (VSM)、POSIWID
- **Heinz von Foerster** "二阶控制论" (1974) —— 观察系统
- **Maturana & Varela** *Autopoiesis and Cognition* (1980) —— 自创生、结构耦合
- **Gregory Bateson** *Steps to an Ecology of Mind* (1972) —— 学习层级
- **钱学森** "开放的复杂巨系统" (1980s-1990s) —— 综合集成方法、研讨厅

详见 [docs/references.md](docs/references.md)。

---

## 许可证 / License

- **代码** (tools/ 下的 Python 脚本等): [GPL-3.0](LICENSE)
- **文档** (SKILL.md, README.md, docs/ 下的内容等): [CC BY 4.0](docs/LICENSE-CC-BY.md)

简单说：文档随便用、随便改，只要求署名；代码可自由使用、修改和分发，但衍生作品发布时须保持 GPL-3.0 开源。

---

## 贡献 / Contributing

欢迎贡献！无论是报告问题、提出改进建议、还是直接提交 PR。

请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 致谢 / Acknowledgments

感谢 Claude、Kimi、Gemini、G 老师、D 指导对本文档的深度审核。他们的意见记录在 [REVIEWS.md](REVIEWS.md)。

---

*Project Cybersyn 得名于 Stafford Beer 在 1971-1973 年为智利阿连德政府设计的实时经济控制系统——一个控制论在复杂社会系统中应用的大胆实验。本项目秉承同样的精神：用控制论指导复杂系统的迭代改进。*
