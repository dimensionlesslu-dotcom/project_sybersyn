# Project Cybersyn 配套工具 — 完整编程计划

> 状态：待审批。审批通过后按 P0→P1→P2 顺序实施。

---

## 总体架构

```
控制论skill/
├── Project Cybersyn (重构版).md   # Skill 本体（已有）
├── tools/
│   ├── cybersyn_state.py          # P0 状态管理器（核心，所有工具依赖它）
│   ├── checklist_compare.py       # P0 验收清单对比器
│   ├── convergence_check.py       # P1 收敛检测器
│   ├── audit_trigger.py           # P1 二阶审计触发器
│   ├── handoff_report.py          # P1 移交报告生成器
│   └── complexity_classify.py     # P2 复杂度分类器
└── TOOLING_PLAN.md                # 本文件
```

**设计约束：**
- 仅依赖 Python 3 stdlib（`json`, `pathlib`, `difflib`, `argparse`, `datetime`, `hashlib`）
- 每个脚本 ≤200 行，单文件自包含
- 统一状态格式：JSON 文件 `cybersyn_state.json`，由 Agent 在任务工作目录创建
- 所有脚本通过 argparse 接收参数，输出到 stdout（机器可读）或文件
- 失败时返回非零 exit code + stderr 错误描述

---

## P0-1: `cybersyn_state.py` — 迭代状态管理器

### 用途
跨轮持久化闭环迭代的全部状态。所有其他工具通过它读写任务状态。

### 接口（argparse 子命令）

```
cybersyn_state.py init    --level L3 --task "重构 auth 模块" [--nmax 5] [--audit-every 3]
cybersyn_state.py read    [--field round|level|r_t|history|convergence|all]
cybersyn_state.py update  --stage plan|test1|feedback|modify|test2|output|audit
                          --data '<JSON 字符串或 @file.json>'
cybersyn_state.py reset   # 归档当前状态为 .bak，新建空状态
cybersyn_state.py summary # 人类可读的单段摘要，输出到 stdout
```

### 状态文件结构 (`cybersyn_state.json`)

```json
{
  "_version": "1.0",
  "_created": "2026-07-01T10:00:00",
  "_updated": "2026-07-01T10:15:00",
  "task": "重构 auth 模块",
  "level": "L3",
  "round": 2,
  "nmax": 5,
  "audit_every": 3,
  "audit_counter": 2,
  "convergence": false,
  "verdict": "continuing",

  "r_t": {
    "requirements": [
      "功能：登录/登出/刷新 token 行为不变",
      "质量：所有现有测试通过",
      "约束：不改变公开 API 签名"
    ],
    "core_assumptions": [
      "JWT 密钥轮换策略保持不变",
      "用户表结构暂不修改"
    ],
    "dead_zones": [
      "第三方 OAuth 回调时序依赖外部服务，本地无法完整验证"
    ]
  },

  "rounds": [
    {
      "n": 1,
      "stage": "completed",
      "plan": {
        "f1_strategy": "提取 token 逻辑到独立 service",
        "f2_strategy": "运行现有集成测试 + 手动 curl 验证",
        "vsm": {"s1": "提取+测试", "s3": "单次分配 30min", "s5": "POSIWID: 保持 auth 行为不变"}
      },
      "test1": {
        "y_raw": "提取完成，编译通过，3/5 集成测试失败",
        "tau": 0
      },
      "feedback": {
        "e_missing": [],
        "e_extra": ["新增了未使用的 TokenValidator 类"],
        "e_wrong": ["refresh 端点返回 500（缺少 UserRepository 注入）"],
        "deviation_type": "A",
        "quality": {"stability": "ok", "steady_state_accuracy": "3/5 tests fail"}
      },
      "modify": {
        "path": "A",
        "k": "局部重写",
        "changes": "移除 TokenValidator，补充 UserRepository 注入",
        "single_param_isolation": true
      },
      "test2": {
        "e2_vs_e1": "e_wrong 从 2 项减为 0；e_extra 已消除",
        "environment_drift": "none",
        "verdict": "continuing"
      }
    },
    {
      "n": 2,
      "stage": "in_progress",
      "plan": {},
      "test1": {},
      "feedback": {},
      "modify": {},
      "test2": {}
    }
  ],

  "audit_log": [
    {
      "round": 3,
      "questions": {
        "r_t_still_valid": true,
        "observer_bias": "可能过度关注 token 层而忽略了 session 管理",
        "structural_issue": false,
        "posiwid": "实际行为与目标一致"
      },
      "conclusion": "maintain"
    }
  ],

  "structural_patterns": []
}
```

### 核心函数

```python
def load_state(path: str = "cybersyn_state.json") -> dict:
    """读取状态文件。不存在则抛 FileNotFoundError。"""

def save_state(state: dict, path: str = "cybersyn_state.json") -> None:
    """原子写入：先写 .tmp，再 rename。"""

def init_state(task: str, level: str, nmax: int = None, audit_every: int = None) -> dict:
    """创建新状态。按 level 自动设默认 nmax/audit_every：
       L1: nmax=2, audit_every=5
       L2: nmax=3, audit_every=3
       L3: nmax=5, audit_every=3
       L4: nmax=-1 (无限制), audit_every=3
    """

def update_round(state: dict, stage: str, data: dict) -> dict:
    """按 stage 名称更新当前轮次数据。自动处理：
       - feedback 阶段：从 e_missing/e_extra/e_wrong 推断 deviation_type
       - test2 阶段：比较 e2 vs e1，更新 verdict
       - 自动递增 audit_counter
    """

def detect_convergence(state: dict) -> str:
    """判定收敛状态：converged / continuing / handoff"""

def summary(state: dict) -> str:
    """生成人类可读摘要"""
```

### 验证标准
- `init` → 产生有效 JSON，`read` 可正确回读
- `update feedback` 后 `read --field round` 显示当前轮次
- 两个并发 `update` 不会损坏文件（原子写入）
- 缺失状态文件时所有命令给出明确错误信息

---

## P0-2: `checklist_compare.py` — 验收清单对比器

### 用途
对比 r(t) 需求清单与实际产物 y(t)，自动生成 `缺失 / 多余 / 错误` 三项清单。

### 接口

```
checklist_compare.py --requirements <json_array_or_file> --actual <text_or_file> [--mode code|text]
```

### 两种模式

**mode=code（默认）：**
- `--requirements`：JSON 数组，每条是 `{"id": "...", "description": "...", "test_cmd": "pytest test_xxx.py" | null}`
- `--actual`：代码 diff 文本或文件路径
- 逻辑：
  1. 对每条 requirement，若有 `test_cmd`，运行测试并捕获结果
  2. 若无 `test_cmd`，用启发式规则：检查 diff 中是否触及相关模块/函数
  3. 输出 e(t) JSON

**mode=text：**
- `--requirements`：JSON 数组，每条是 `{"id": "...", "criterion": "...", "keywords": [...]}`
- `--actual`：文本内容或文件路径
- 逻辑：
  1. 对每条 criterion，在 actual 中搜索 keywords
  2. 标记：完全匹配（covered） / 部分匹配（partial） / 未匹配（missing）
  3. 检测 actual 中是否有超出 requirements 的段落（extra）

### 输出 JSON

```json
{
  "missing": [
    {"requirement_id": "R3", "description": "刷新 token 端点测试", "severity": "high"}
  ],
  "extra": [
    {"description": "新增 TokenValidator 类", "location": "src/auth/token.py:45-78", "severity": "medium"}
  ],
  "wrong": [
    {"requirement_id": "R2", "description": "refresh 端点返回 500", "expected": "200 + new token pair", "actual": "500 Internal Error", "severity": "critical"}
  ],
  "summary": "3 项未通过 / 5 项总计",
  "suggested_deviation_type": "A"
}
```

### 核心函数

```python
def load_requirements(source: str) -> list[dict]:
    """从 JSON 字符串或文件加载需求列表"""

def parse_actual(source: str) -> str:
    """从文件或直接文本获取 y(t)"""

def compare_code(requirements: list, actual: str) -> dict:
    """代码模式：运行关联测试 + 启发式覆盖检查"""

def compare_text(requirements: list, actual: str) -> dict:
    """文本模式：关键词匹配 + 段落覆盖度"""

def suggest_deviation_type(result: dict) -> str:
    """推断偏差类型：纯缺失/错误→A；重复不一致→B；需求与产物方向不一致→C"""
```

### 边缘情况
- 需求为空 → 返回警告 "无验收标准，无法自动对比"
- 产物文件不存在 → 错误退出，exit code 2
- 测试命令执行超时 → 标记该 requirement 为 "unverified"，不阻塞其余

### 验证标准
- 5 条 requirement、3 条通过、1 条失败、1 条缺失 → `missing=1, wrong=1, summary="2/5 未通过"`
- 无测试命令的 requirement → 状态为 "unverified"，不计入 wrong
- 空产物文本 → 全部 requirement 标记为 missing

---

## P1-1: `convergence_check.py` — 收敛检测器

### 用途
比较当前轮 e(t) 与上一轮 e(t)，判定是否收敛。

### 接口

```
convergence_check.py --state cybersyn_state.json [--verbose]
```

### 判定逻辑

```
输入：state 的 rounds 数组（最近两轮的 feedback.e_*）
输出：{ "status": "converged" | "continuing" | "handoff", "reasons": [...] }

收敛条件（全部满足）：
1. 最近两轮 e_missing、e_extra、e_wrong 三项均无新增项
2. 最近一轮没有任何 critical severity 项
3. 偏差幅度递减（本轮 wrong 数 ≤ 上轮 wrong 数）
4. 无新问题引入（本轮 test2 的 e2 不包含 e1 未见过的项）

继续条件：
- 偏差在减少但未归零
- 有新问题但非 critical

移交条件（任一满足）：
- round >= nmax
- 连续 2 轮偏差同向增大
- 偏差类型从 A/B 突变为 C/D
```

### 输出 JSON

```json
{
  "status": "continuing",
  "round": 2,
  "nmax": 5,
  "trend": {
    "e_missing_count": [1, 0],
    "e_wrong_count": [2, 0],
    "e_extra_count": [1, 0]
  },
  "reasons": [
    "偏差在减少但 e_missing 仍有 1 项未解决"
  ],
  "recommendation": "继续迭代，重点解决残留的 R3 缺失项"
}
```

### 核心函数

```python
def extract_deviation_history(state: dict) -> list[dict]:
    """从 state 中提取每轮的 e(t) 摘要"""

def compare_rounds(current: dict, previous: dict) -> dict:
    """对比两轮偏差，返回新增/消除/持续 三项"""

def assess_trend(history: list) -> str:
    """判趋势：收敛中 / 停滞 / 发散"""

def convergence_verdict(state: dict) -> dict:
    """综合判定，输出最终 verdict JSON"""
```

### 验证标准
- 两轮完全相同 → `converged`
- 本轮比上轮少 1 项 wrong → `continuing`，trend 显示递减
- round=5, nmax=5 → `handoff`，reason 含 "Nmax reached"
- 无上轮数据（第一轮）→ `continuing`，reason="首轮，无对比基准"

---

## P1-2: `audit_trigger.py` — 二阶审计触发器

### 用途
跟踪迭代轮次，在满足条件时提醒触发二阶审计，输出审计问题清单。

### 接口

```
audit_trigger.py --state cybersyn_state.json
```

### 触发条件（任一满足即触发）

1. `round % audit_every == 0`（定时触发，默认每 m=3 轮）
2. 同一偏差类型连续 2 轮未消除
3. 偏差类型从 A/B 突变为 C/D
4. `round > nmax / 2` 且未收敛
5. 手动标记：state 中有 `force_audit: true`

### 输出 JSON

```json
{
  "trigger": true,
  "reasons": ["定时触发 (round=3, every=3)", "偏差类型 A 连续 3 轮未消除"],
  "audit_round": 3,
  "checklist": [
    "1. r(t) 假设从哪来？最近验证过吗？若 r(t) 本身错，偏差分析还成立吗？",
    "2. 我是否只选了支持先验的测量方式、回避了不想看的区域？",
    "3. 这是参数误差还是结构问题？需换执行策略形状/增大多样性吗？",
    "4. 实际在做的 vs 声称要做的，差距持续则改行为还是改声明？(POSIWID)"
  ],
  "previous_audit_conclusion": "maintain（第 3 轮）",
  "warning": "若 r(t) 最近未经审计确认，禁止开启正反馈加速"
}
```

### 核心函数

```python
def check_periodic(state: dict) -> bool:
    """定时触发检测"""

def check_same_type_persist(state: dict) -> bool:
    """同类型偏差持续检测：取最近 2 轮的 deviation_type"""

def check_type_mutation(state: dict) -> bool:
    """类型突变检测：A/B → C/D"""

def check_stall(state: dict) -> bool:
    """过半 Nmax 未收敛检测"""

def generate_checklist(state: dict) -> list[str]:
    """根据当前状态定制审计问题清单"""
```

### 验证标准
- round=3, audit_every=3 → `trigger=true`, reasons含"定时触发"
- round=2, 最近两轮都是类型 A → `trigger=true`, reasons含"同类型持续"
- round=1, 无特殊条件 → `trigger=false`
- state.rounds 为空 → 错误退出，提示"至少需要一轮迭代数据"

---

## P1-3: `handoff_report.py` — 移交报告生成器

### 用途
当任务不收敛、超 Nmax、或触发向人移交闸时，汇总当前最佳结果和待决策项。

### 接口

```
handoff_report.py --state cybersyn_state.json [--output report.md] [--format json|markdown]
```

### 报告内容（Markdown 格式）

```markdown
# 移交报告 — [任务名]

**生成时间：** 2026-07-01 10:30
**状态：** 未收敛，已超 Nmax (5/5)
**复杂度：** L3

## 当前最佳产物
- 产物位置/描述：[由 Agent 在调用时通过 --extra 参数注入]
- 最终偏差：e_missing=1, e_extra=0, e_wrong=0

## 未通过的验收项
| ID | 描述 | 严重度 | 偏差类型 |
|----|------|--------|----------|
| R3 | 刷新 token 端点测试 | high | A |

## 偏差历史摘要
- 轮次 1：类型 A，2 wrong（refresh 500 + 多余 TokenValidator）
- 轮次 2：类型 A，0 wrong，1 missing（R3 未覆盖）
- 轮次 3-5：类型 A，1 missing 持续（R3 需要外部服务桩，属死区）

## 死区
- 第三方 OAuth 回调时序依赖外部服务，本地无法完整验证 → 建议人工验证

## 结构性问题
- 无

## 建议下一步
1. **[用户决策]** R3 验收项属于声明的死区，是否接受当前产物或调整验收标准？
2. **[继续修改]** 若不接受，需先搭建 OAuth mock 服务（补能力缺口）
3. **[重设目标]** 若 OAuth 测试超出当前阶段范围，将 R3 移入下一阶段 r(t)

## 待用户回答
- R3 是必须本阶段完成，还是可推迟？
- 是否需要协助搭建 OAuth mock？
```

### 核心函数

```python
def collect_unmet(state: dict) -> list[dict]:
    """从最后一轮 feedback 中提取未解决的 e(t) 项"""

def summarize_history(state: dict) -> list[str]:
    """轮次级别摘要：每轮一行"""

def detect_structural_patterns(state: dict) -> list[str]:
    """检测 state.structural_patterns 和同类偏差模式"""

def generate_next_steps(state: dict) -> list[str]:
    """根据偏差类型和死区生成建议下一步"""

def render_markdown(state: dict, extra: dict) -> str:
    """渲染完整 Markdown 报告"""

def render_json(state: dict, extra: dict) -> dict:
    """渲染 JSON 格式报告"""
```

### 验证标准
- Nmax 超限 → 报告标题含"已超 Nmax"
- 存在死区 → 建议下一步含"用户决策"
- 连续同类偏差 → 结构性问题区域含相应警告
- `--format json` → 输出合法 JSON，可被其他工具解析

---

## P2-1: `complexity_classify.py` — 复杂度分类器

### 用途
根据任务描述和上下文，辅助判定 L1-L4。

### 接口

```
complexity_classify.py --task "重构 auth 模块" [--files auth.py,token.py,session.py] [--dependencies "user module, cache module"]
```

### 判定规则

```python
def classify(task: str, files: list[str] = None, dependencies: list[str] = None) -> dict:
    """
    L1: ≤2 files, 0 cross-module dependencies, 需求明确
    L2: >2 files but all homogeneous (same type), no cross-subsystem coordination
    L3: ≥3 heterogeneous modules with inter-dependencies, or requirements have implicit assumptions
    L4: requirements/environment continuously changing, needs qualitative discussion to clarify goals
    """

# 具体实现：
# 1. 数文件数 → files ≤ 2 倾向 L1
# 2. 分析依赖 → 跨模块且异构 → 倾向 L3
# 3. 检测需求中是否含模糊词（"优化""改进""合理的"）→ 含则至少 L2
# 4. 检测是否涉及"策略""方向""是否应该"→ 倾向 L4
# 5. 综合判定，给出 L 值和置信度
```

### 输出 JSON

```json
{
  "level": "L3",
  "confidence": 0.85,
  "factors": {
    "file_count": {"value": 5, "tendency": "L3"},
    "heterogeneity": {"value": true, "tendency": "L3"},
    "requirement_clarity": {"value": "medium", "tendency": "L2"},
    "env_stability": {"value": "stable", "tendency": "L1"}
  },
  "recommended": {
    "path": "全流程 + 四分类 + 二阶审计",
    "nmax": 5,
    "audit_every": 3,
    "vsm": true,
    "positive_feedback": "关"
  },
  "warnings": [],
  "explanation": "5 个异构模块，存在跨模块依赖（auth→user, auth→cache），需求明确但集成复杂度高 → L3"
}
```

### 核心函数

```python
def count_files(task: str, explicit_files: list[str]) -> int:
    """从显式列表或任务描述中推断涉及文件数"""

def detect_heterogeneity(files: list[str], deps: list[str]) -> bool:
    """判断是否异构（不同模块/层级/语言）"""

def assess_requirement_clarity(task: str) -> str:
    """扫描模糊词，返回 clear / medium / vague"""

def detect_env_volatility(task: str) -> str:
    """检测"持续变化""不确定""探索"等环境不稳定信号"""

def classify(task: str, files: list[str], deps: list[str]) -> dict:
    """综合分类"""
```

### 边缘情况
- 无文件列表 → 从 task 文本推断，confidence 降低
- 任务描述为空 → 错误退出
- 各项指标矛盾（如 files 少但 deps 多）→ 取最高 L 值，warnings 中记录矛盾

### 验证标准
- "修改单行 bug" → L1, confidence ≥ 0.8
- "重构 auth/user/cache 三个模块" → L3, confidence ≥ 0.7
- "批量重命名 50 个文件" → L2, heterogeneity=false
- "帮我规划创业方向" → L4, env_stability=volatile

---

## 实施顺序

```
Phase 1（本计划审批后立即开始）
├── [1] cybersyn_state.py     ← 所有工具的基础
├── [2] checklist_compare.py   ← 闭环核心：测试₁/反馈 阶段用
└── [3] 更新 Skill 文档        ← 在相应阶段引用工具

Phase 2
├── [4] convergence_check.py   ← 测试₂ 阶段用
├── [5] audit_trigger.py       ← 二阶审计入口
└── [6] handoff_report.py      ← 移交闸 / 输出 阶段用

Phase 3
└── [7] complexity_classify.py ← 第 0 节自检辅助
```

## 与 Skill 文档的集成点

每个工具在 Skill 的第 2 节（闭环六阶段）中有明确调用位置：

| 阶段 | 调用工具 | 参数 |
|------|----------|------|
| 0 自检 | `complexity_classify.py` | 任务描述 + 文件列表 |
| 1 计划 | `cybersyn_state.py init` | level + task + nmax |
| 2 测试₁ | `checklist_compare.py` | r(t) + y(t) |
| 3 反馈 | `checklist_compare.py` 输出 + 人工判定类型 |
| 4 修改 | `cybersyn_state.py update --stage modify` | 修改内容 |
| 5 测试₂ | `convergence_check.py` | state 文件 |
| 5 判决 | `audit_trigger.py` | 判定是否需要二阶审计 |
| 5 移交 | `handoff_report.py` | 不收敛或超 Nmax 时 |
| 6 输出 | `cybersyn_state.py summary` | 最终状态 |
| 5 二阶 | `cybersyn_state.py update --stage audit` | 审计结论 |

---

## 设计决策记录

1. **为什么 JSON 而非 YAML/TOML？** JSON 是 Python stdlib 原生支持，零依赖。状态文件约 5-20KB，可读性足够。
2. **为什么不在脚本内直接调用 LLM？** 判定（偏差类型、POSIWID 等）需要语义理解，由 Agent 执行；工具只做机械化操作。
3. **为什么不改写现有 Skill 文档？** Skill 文档保持"操作协议"角色，工具是"仪表盘"。两者松耦合，工具失败不影响 Skill 手动执行。
4. **状态文件放在哪？** 由 Agent 在任务工作目录创建，路径通过环境变量 `CYBERSYN_STATE` 或默认 `./cybersyn_state.json`。
