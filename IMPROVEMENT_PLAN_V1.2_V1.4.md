# Project Cybersyn 新一轮改进计划（v1.2–v1.4）

> 状态：提案，作为 v1.1.0 之后的实施基线
> 核心方向：Evidence First → Independent Audit → Measured Adaptation
> 适用范围：Skill 本体、配套工具、subagent 协议与研发评测；不包含生产级分布式调度

## 1. 决策摘要

下一阶段不继续增加控制论符号、固定策略模板或状态管理功能。优先把 Project Cybersyn 从“流程与工具齐全”推进为“基于证据、可独立质疑、可通过对照评测验证”的任务控制策略。

按以下顺序实施：

1. **v1.2 Evidence First**：修复虚假收敛、验收证据和命令执行边界。
2. **v1.3 Independent Audit**：加入只读的假设审计 subagent 和多角度验证 prompt 组装线。
3. **v1.4 Measured Adaptation**：建立前向评测集，再依据数据升级动态风险路由。

本计划不替换 `TOOLING_PLAN_FINAL.md` 的历史规格；后者描述现有工具链，本文件规定后续演进。

## 2. 当前基线

### 2.1 已具备能力

- L1–L4 复杂度路由。
- 计划→测试₁→反馈→修改→测试₂→输出的闭环。
- A/B/C/D 偏差分类、二阶审计、交付验收门和向人移交闸。
- 状态管理、验收比较、收敛检测、审计触发、移交报告和研讨厅模板工具。
- Linux/Windows 冒烟测试；当前 64 项检查通过。

### 2.2 尚未解决的问题

1. **收敛语义不严**：没有新增偏差且无 critical 项时，仍可能带着 high/medium 残留被判定为收敛。
2. **证据粒度不足**：偏差以轮为单位记录单一类型，无法表达同一轮并存的 A/B/C/D。
3. **启发式越权**：关键词、文件名和文本相似度可能被当成语义验收结论。
4. **执行边界过宽**：来自验收数据的 `test_cmd` 可直接交给 shell 执行。
5. **测试层级不足**：现有测试主要证明工具可运行，不能证明 Skill 比无 Skill 基线更可靠。
6. **多角度不等于独立验证**：固定“保守/重构/探索”模板不能保证形成可证伪的分歧。
7. **分发不完整**：缺少标准 `agents/openai.yaml`；中英文触发元数据没有统一进入主入口。

## 3. 目标与非目标

### 3.1 目标

- 任何自动交付结论都能追溯到逐验收项证据。
- 未验证项、测量偏差和结构性偏差不会被“稳定”掩盖。
- 使用 subagent 时形成上下文隔离、职责正交、证据优先的独立审计。
- 通过真实任务的有/无 Skill 对照评测决定功能是否保留。
- L1 保持零 subagent、低流程开销。

### 3.2 非目标

- 不建设 Redis、队列、分布式锁或生产级多 Agent 平台。
- 不让 subagent 直接修改文件、联系用户或改变外部系统。
- 不使用多数投票代替证据判断。
- 不把同模型的多个角色描述成真正统计独立的评审者。
- 不在评测结果出来前扩充更多控制论公式或固定模型模板。

## 4. 目标架构

```text
用户请求 + 原始约束
        ↓
主 Agent 建立 r(t) 与逐项验收标准
        ↓
执行与原始证据采集
        ↓
证据账本 RequirementEvidence[]
        ↓
按风险触发独立审计
  ┌────────────┬────────────┬────────────┐
  │ 假设/目标审计 │ 测量可信度审计 │ 集成/回归审计 │
  └────────────┴────────────┴────────────┘
        ↓
Finding[] 去重与冲突保留
        ↓
交付验收门：converged / residual / stagnant / handoff
        ↓
主 Agent 决策、交付或向用户移交
```

主 Agent 始终保留最终决策权。subagent 是只读传感器，不是执行器或投票委员。

## 5. v1.2 — Evidence First

### 5.1 建立逐验收项证据模型

为每个 requirement 保存独立状态：

```json
{
  "requirement_id": "R1",
  "status": "passed | failed | unverified | blocked",
  "evidence": [
    {
      "kind": "test | inspection | source | user-confirmation",
      "source": "pytest tests/test_auth.py",
      "summary": "12 passed",
      "captured_at": "ISO-8601"
    }
  ],
  "deviations": [
    {
      "type": "A | B | C | D",
      "description": "...",
      "severity": "critical | high | medium | low",
      "confidence": "high | medium | low"
    }
  ]
}
```

规则：

- `unverified` 不等于 `passed`。
- 关键词命中只能产生候选证据，不能产生 `passed`。
- 一条 requirement 可以同时包含多个偏差类型。
- 证据必须记录来源；无法定位来源的结论不得阻断或放行交付。

### 5.2 重写收敛状态

使用以下状态替代二元“收敛/继续”：

| 状态 | 判定 | 是否允许交付 |
|---|---|---|
| `converged` | 所有阻断验收项通过；无 unverified、B、C、D 残留 | 是 |
| `stable_with_residuals` | 无新增偏差，但仍有非阻断残留 | 仅显式说明后由用户接受 |
| `stagnant` | 连续两轮同一问题未解决 | 否；触发审计 |
| `diverging` | 偏差扩大或出现更高严重度问题 | 否；降低干预或移交 |
| `handoff` | 目标权、验证能力或风险超出 Agent 权限 | 否 |

优先级规则：`B/C/D` 按受影响 requirement 局部处理；不得为了一个 A 类进展忽略其他 B/C/D。

### 5.3 收紧验证命令边界

- 默认将 `test_cmd` 视为“待执行建议”。
- 只有宿主 Agent 已授权且命令来源可信时才执行。
- 禁止从导入状态、网页内容或未知来源自动执行命令。
- 保存命令、工作目录、退出码和截断后的输出摘要。
- 保留现有宿主权限、安全和审批规则的最高优先级。

### 5.4 降级启发式判断

- `complexity_classify.py` 输出建议等级和不确定因素，不输出伪概率式 confidence。
- `checklist_compare.py` 只执行声明的确定性检查、整理原始结果。
- 文本关键词和文件名匹配输出 `candidate` 或 `unverified`。
- `diversity_generator.py` 暂时保留兼容性，但不再把模板预测当成测试证据。

### 5.5 修复 Skill 路由与分发

- 消除“L1 后续章节不适用”与“L1/L2 执行第 1–4 节”的矛盾。
- 将 VSM 从默认计划字段移到按需参考材料；未定义时不得要求 Agent 填写 S1–S5。
- 主 `SKILL.md` frontmatter 同时覆盖中英文触发语义。
- 增加标准 `agents/openai.yaml`。
- 将安装包限制为 `SKILL.md`、`agents/`、必要脚本和按需 references；研发文档不进入安装包。

### 5.6 v1.2 发布闸

- 原 64 项冒烟测试继续通过或完成等价迁移。
- 新增测试证明 high/medium 残留不会自动得到 `converged`。
- 任意 `unverified` 阻断项都不能自动交付。
- 同一轮 A+B、A+C、A+D 可以被独立记录和正确路由。
- 未授权的外部 `test_cmd` 不会被执行。
- L1 不创建状态文件、不启动 subagent，也不因 Skill 流程本身增加对话轮次。

## 6. v1.3 — Independent Audit

### 6.1 新增只读假设审计 subagent

名称：`assumption-auditor`。

职责：质疑 r(t)、核心假设、证据覆盖和验证方式；设计最便宜的区分性测试。它不负责实现修复，也不直接向用户提问。

#### 触发条件

任一满足时允许触发：

- L3/L4 到达二阶审计点。
- 同类偏差连续两轮。
- 准备宣布收敛但存在推断性证据。
- A/B 突变为 C/D。
- 核心假设没有来源或最近验证时间。
- 修改不可逆、影响面大或失败成本高。
- 验收项之间发生冲突。

以下情况禁止触发：

- 明确、可逆且验证充分的 L1 任务。
- 只是为了增加“评审数量”。
- 无法提供原始产物或原始证据，只能提供主 Agent 的结论。

#### 权限边界

- 默认只读。
- 不修改仓库、状态文件或外部系统。
- 不直接发送消息给用户。
- 如必须用户决策，只向主 Agent 返回一个最小必要问题。
- 不读取主 Agent 的预期答案、怀疑点或拟议修复。

#### 输出契约

```json
{
  "assumption": "...",
  "evidence_for": [],
  "evidence_against": [],
  "unverified_gap": "...",
  "cheapest_discriminating_test": "...",
  "affected_requirements": ["R1"],
  "deviation_types": ["B", "C"],
  "decision": "continue | recalibrate | reset-goal | restructure | ask-user",
  "confidence": "high | medium | low"
}
```

### 6.2 新增多角度验证 prompt 组装线

新增建议资源：

```text
references/subagent-validation.md
tools/validation_prompt_assembler.py
```

组装器只生成 prompt packet，不负责启动 subagent。是否能启动以及如何并发由宿主 Agent 决定。

#### 默认正交视角

| 视角 | 目标 | 主要检查 |
|---|---|---|
| `goal-spec` | 判断目标和验收标准是否成立 | 隐含假设、目标漂移、冲突约束 |
| `measurement` | 判断证据与测试是否可信 | 测量误差、覆盖缺口、伪通过 |
| `integration-regression` | 判断局部成功是否破坏整体 | 边界条件、接口耦合、回归、D 偏差 |
| `environment` | 按需判断外部条件是否变化 | 版本、政策、资源、时效性 |

不要用三个仅名称不同、任务相同的角色模拟多样性。

#### PromptPacket 契约

```json
{
  "packet_id": "...",
  "role": "goal-spec | measurement | integration-regression | environment",
  "task": "用户原始请求",
  "acceptance": [],
  "constraints": [],
  "raw_artifacts": [],
  "raw_evidence": [],
  "authority": "read-only",
  "excluded_context": ["expected_answer", "primary_diagnosis", "proposed_fix", "peer_outputs"],
  "output_schema": "Finding[]",
  "budget": {"max_findings": 5}
}
```

#### 组装算法

```text
1. 从原始请求、验收项、约束、产物和未经解释的测试输出建立公共事实包。
2. 删除主 Agent 的诊断、预期答案、拟议修复和其他审计结果。
3. 根据风险信号选择视角：
   - 目标或假设不清 → goal-spec
   - 测试矛盾、不可重复或覆盖不足 → measurement
   - 跨模块、接口或回归风险 → integration-regression
   - 外部信息可能变化 → environment
4. 为每个视角注入不同的审计目标、可用证据和失败判据。
5. 强制只读权限、Finding[] 输出契约和发现数量上限。
6. 并行发送；所有结果返回后再汇总，运行中不互相传递结果。
```

通用 prompt 外壳：

```text
你是独立的 {role} 验证者。仅根据下面的原始任务、产物和证据进行检查。
不要假设主执行者的判断正确，也不要为了反对而制造问题。
每个结论必须引用可定位证据；无直接证据时标为待验证并给出成本最低的区分性测试。
你只有只读权限，不修改产物、不联系用户、不读取或猜测其他验证者的输出。
严格按 Finding[] 契约返回；最多输出 {max_findings} 项。

任务：{task}
验收项：{acceptance}
约束：{constraints}
原始产物：{raw_artifacts}
原始证据：{raw_evidence}
本视角目标：{role_objective}
本视角失败判据：{failure_criteria}
```

#### Finding 契约

```json
{
  "finding_id": "...",
  "claim": "...",
  "supporting_evidence": [],
  "counterevidence": [],
  "affected_requirements": [],
  "deviation_types": [],
  "severity": "critical | high | medium | low",
  "confidence": "high | medium | low",
  "proposed_test": "...",
  "blocking_delivery": true
}
```

### 6.3 上下文隔离规则

每个验证 subagent：

1. 接收相同的原始任务与必要约束。
2. 只接收该视角需要的最小原始产物和证据。
3. 不接收主 Agent 的诊断、预期答案或修改意图。
4. 不接收其他验证 subagent 的输出。
5. 独立完成后才进入汇总阶段。
6. 若只能看到加工后的摘要，必须降低 confidence 并声明证据缺口。

### 6.4 汇总与裁决规则

- 汇总器可去重、关联 requirement、检查引用是否存在。
- 汇总器不得通过多数投票制造事实。
- 高严重度但低证据的 finding 进入“待验证”，不能直接阻断交付。
- 单个有直接证据的 finding 可以推翻多个无证据的同意意见。
- Agent 间分歧必须保留，并转化为区分性测试或用户待决问题。
- 主 Agent 依据验收规则裁决；subagent 不拥有最终交付权。

### 6.5 调用预算

| 层级 | 默认 subagent 数 | 上限 | 说明 |
|---|---:|---:|---|
| L1 | 0 | 0 | 保持极简路径 |
| L2 | 0 | 1 | 仅批量风险或验证异常时启用 |
| L3 | 2 | 3 | 假设审计 + 最相关的验证视角 |
| L4 | 3 | 3 | 三个正交视角；环境视角按需替换 |

每个审计点最多执行一轮并行验证。没有新增证据时不得重复调用；转为区分性测试或向人移交。

### 6.6 降级路径

- 宿主不支持 subagent：主 Agent 按三个视角串行检查，并明确“不具备上下文独立性”。
- 某个 subagent 失败：保留其他结果，标记覆盖缺口，不自动重试超过一次。
- 预算不足：优先 `measurement`；验证不可信时，其他判断没有可靠基础。
- 产物可能影响生产系统：验证 subagent 保持只读，需要写操作时返回主 Agent 请求授权。

### 6.7 v1.3 发布闸

- L1 永不启动 subagent。
- 所有 PromptPacket 都显式包含只读权限和排除上下文字段。
- 自动测试证明主 Agent 的诊断和拟议修复不会进入验证 prompt。
- 三种默认视角的任务目标和判定标准不同，而非只改角色名称。
- Finding 缺少 supporting evidence 时不能直接将验收项标为 failed。
- 分歧会被保留为测试或待决项，不会被多数票抹平。
- subagent 不可用或失败时，闭环可安全降级。

## 7. v1.4 — Measured Adaptation

### 7.1 建立研发评测目录

评测材料属于研发基础设施，不进入 Skill 安装包：

```text
evals/
├── cases/
│   ├── l1/
│   ├── l2/
│   ├── l3/
│   ├── l4/
│   └── adversarial/
├── rubrics/
├── run_forward_eval.py
└── results/                 # 默认不提交运行时敏感内容
```

### 7.2 最小评测集

建立 30–50 个任务，至少覆盖：

- 明确的小修改及过度流程风险。
- 大量同质任务中的抽样与漏检。
- 三个以上异构模块的接口回归。
- 错误测试、随机测试和不可重复结果（B）。
- 用户中途改变需求或外部约束（C）。
- 各模块独立通过但集成失败（D）。
- 错误目标、冲突验收项、验证工具缺失。
- 无 Python、无 subagent、预算受限的降级环境。

### 7.3 前向测试纪律

- 使用新鲜上下文或独立任务。
- 给测试 Agent 原始请求和原始产物，不给修改意图与预期答案。
- 测试 Prompt 采用真实用户表达，不写“请评审这个 Skill”。
- 每轮重新构建上下文，避免发现上一次评测残留文件。
- 高成本、需额外审批或可能改动真实系统的测试先取得用户同意。

### 7.4 对照与消融

每个代表性案例至少比较：

1. 无 Project Cybersyn。
2. v1.2，仅 Evidence First。
3. v1.3，加入假设审计。
4. v1.3，加入完整多角度验证。

通过消融判断收益来自证据模型、单一审计员还是多 Agent，而不是默认把全部收益归因于 subagent 数量。

### 7.5 指标

- 任务完成率。
- 错误交付和虚假收敛率。
- 注入 A/B/C/D 的检出与正确路由率。
- 回归数量及严重度。
- 必要与不必要的用户打断次数。
- 总轮次、subagent 调用数、时间和上下文开销。
- 主 Agent 与审计 Agent 的分歧率及分歧解决方式。

### 7.6 动态风险路由

只有当 v1.2/v1.3 通过评测后，才将固定 L1–L4 内部实现升级为风险向量：

```text
scope                 任务范围
heterogeneity         异构与耦合
requirement_ambiguity 需求歧义
verification_quality  验证可信度
environment_volatility 环境波动
reversibility         修改可逆性
failure_impact        失败影响
```

L1–L4 继续作为面向用户的可读标签；内部根据风险信号动态升降级。不得把启发式分数描述成统计概率。

### 7.7 v1.4 发布闸

- 关键安全案例不存在 critical 虚假交付。
- 相比无 Skill 基线，L3/L4 的错误交付率下降。
- L1 不因新机制增加 subagent 调用。
- 多角度验证带来的缺陷检出收益能够覆盖其时间和上下文成本。
- 若完整多 Agent 方案没有优于单一假设审计员，则默认回退为单审计员方案。

## 8. 实施任务与依赖

| ID | 任务 | 依赖 | 主要文件 |
|---|---|---|---|
| E1 | 定义 RequirementEvidence 与逐项偏差 | 无 | 状态模型、Skill |
| E2 | 修复收敛状态机 | E1 | `convergence_check.py` |
| E3 | 收紧 `test_cmd` 执行规则 | E1 | `checklist_compare.py` |
| E4 | 降级关键词和模板结论 | E1 | classifier、compare、diversity |
| E5 | 修复 L1/VSM/双语触发与分发 | 无 | `SKILL.md`、`agents/openai.yaml` |
| E6 | 扩展回归与安全测试 | E1–E5 | `smoke_test.py`、新测试夹具 |
| A1 | 编写假设审计协议 | E1–E2 | `references/subagent-validation.md` |
| A2 | 定义 PromptPacket 与 Finding | A1 | reference、状态模型 |
| A3 | 实现 prompt 组装器 | A2 | `tools/validation_prompt_assembler.py` |
| A4 | 接入触发、预算与降级路由 | A1–A3 | `SKILL.md` |
| A5 | 测试上下文泄漏和权限边界 | A3–A4 | 测试夹具 |
| V1 | 建立真实任务与对抗案例 | E6 | `evals/cases/` |
| V2 | 实现有/无 Skill 对照与消融 | V1、A5 | `evals/run_forward_eval.py` |
| V3 | 汇总指标并做保留/回退决策 | V2 | 评测结果 |
| R1 | 实现动态风险路由 | V3 通过 | classifier、Skill |

推荐按 `E1→E2/E3→E4/E5→E6→A1/A2→A3/A4→A5→V1/V2/V3→R1` 推进。

## 9. 风险登记

| 风险 | 表现 | 控制措施 |
|---|---|---|
| 虚假多样性 | 三个 Agent 给出同质意见 | 正交职责、不同证据重点、互不可见 |
| 提示泄漏 | 审计员复述主 Agent 诊断 | PromptPacket 排除字段与自动化泄漏测试 |
| 幻觉式反对 | 无证据也生成高严重度问题 | 强制 supporting evidence；否则降为待验证 |
| 多数投票偏误 | 多个弱意见压过直接证据 | 证据优先，禁止按票数裁决 |
| 成本失控 | 每轮启动多个 Agent | 层级预算、每审计点最多一轮、无新证据不重试 |
| 决策权扩散 | subagent 修改产物或问用户 | 只读权限，所有动作返回主 Agent |
| 审计死锁 | 持续反问但没有新信息 | 生成区分性测试；仍不可得则向人移交 |
| 评测污染 | Agent 看见预期答案或历史产物 | 新鲜上下文、原始材料、清理残留 |

## 10. 完成定义

本轮改进完成不是指“增加了两个 subagent”，而是同时满足：

1. 收敛结论由逐验收项证据支持。
2. 假设审计能够发现目标、测量或结构层问题，但不越权执行。
3. 多角度验证具备上下文隔离和正交判据。
4. 有/无 Skill 及消融评测能够显示收益来源。
5. 如果多 Agent 没有稳定净收益，系统会回退到更简单的单审计员或无审计路径。

最终原则：**先提高可观测性，再增加控制强度；先证明独立审计有效，再扩大 subagent 数量。**
