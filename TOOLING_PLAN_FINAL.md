# Project Cybersyn 配套工具 — 完整编程计划（最终版）

> **融合来源**：`TOOLING_PLAN.md`（原计划） + `notes/TOOLING_PLAN_修订意见.md`（基于《工程控制论》《Agentic Design Patterns》《The Founder's Playbook》的审计修订）
>
> **状态**：待审批。审批通过后按 Phase 1→2→3 顺序实施。
>
> **版本**：2.0

---

## 目录

1. [总体架构](#1-总体架构)
2. [状态文件规范 v2.0](#2-状态文件规范-v20)
3. [Phase 1 工具规范](#3-phase-1-工具规范)
   - [3.1 `cybersyn_state.py` — 状态管理器（核心）](#31-cybersyn_statepy--状态管理器核心)
   - [3.2 `checklist_compare.py` — 验收清单对比器](#32-checklist_comparepy--验收清单对比器)
   - [3.3 `diversity_generator.py` — 研讨厅多模型分歧生成器](#33-diversity_generatorpy--研讨厅多模型分歧生成器)
4. [Phase 2 工具规范](#4-phase-2-工具规范)
   - [4.1 `convergence_check.py` — 收敛检测器（含增益/能量/周期/漂移）](#41-convergence_checkpy--收敛检测器含增益能量周期漂移)
   - [4.2 `audit_trigger.py` — 二阶审计触发器（含自动结论推荐）](#42-audit_triggerpy--二阶审计触发器含自动结论推荐)
   - [4.3 `handoff_report.py` — 移交报告生成器](#43-handoff_reportpy--移交报告生成器)
5. [Phase 3 工具规范](#5-phase-3-工具规范)
   - [5.1 `complexity_classify.py` — 复杂度分类器（含 enforce 模式）](#51-complexity_classifypy--复杂度分类器含-enforce-模式)
6. [实施顺序](#6-实施顺序)
7. [与 Skill 文档的集成点](#7-与-skill-文档的集成点)
8. [设计决策记录](#8-设计决策记录)
9. [全局验证标准](#9-全局验证标准)

---

## 1. 总体架构

```
控制论skill/
├── Project Cybersyn (重构版).md     # Skill 本体（已有）
├── tools/
│   ├── cybersyn_state.py            # P0 状态管理器（核心，所有工具依赖）
│   ├── checklist_compare.py         # P0 验收清单对比器
│   ├── diversity_generator.py       # P0 研讨厅多模型分歧生成器（★新增）
│   ├── convergence_check.py         # P1 收敛检测器（含增益/能量/周期/漂移）
│   ├── audit_trigger.py             # P1 二阶审计触发器（含自动结论推荐）
│   ├── handoff_report.py            # P1 移交报告生成器
│   └── complexity_classify.py       # P2 复杂度分类器（含 enforce 模式）
├── cybersyn_state.json              # 运行时状态（由 Agent 创建于任务工作目录）
├── cybersyn_archive/                # 跨会话归档目录
│   └── archive.ndjson               # 追加式归档日志
├── TOOLING_PLAN.md                  # 原计划（保留为历史参考）
└── TOOLING_PLAN_FINAL.md            # 本文件
```

### 设计约束

1. **仅依赖 Python 3 stdlib**：`json`, `pathlib`, `difflib`, `argparse`, `datetime`, `hashlib`, `re`, `subprocess`, `os`, `sys`, `uuid`, `copy`, `math`, `statistics`
2. **每个脚本 ≤350 行**（原为 200，因功能扩展放宽），**单文件自包含**
3. **统一状态格式**：JSON 文件 `cybersyn_state.json`（规范见第 2 节），由 Agent 在任务工作目录创建
4. **所有脚本通过 argparse 接收参数**，输出到 stdout（机器可读 JSON）或指定文件（Markdown）
5. **失败时返回非零 exit code + stderr JSON 错误描述**：`{"error": "描述", "code": 2}`
6. **工具不做语义判断**：偏差类型 A/B/C/D、POSIWID 等留给 Agent；工具只做机械化操作（统计、比较、正则匹配、阈值判定）
7. **与 Skill 文档松耦合**：工具失败不影响 Skill 手动执行
8. **状态文件路径**：默认 `./cybersyn_state.json`，可通过环境变量 `CYBERSYN_STATE` 覆盖

---

## 2. 状态文件规范 v2.0

### 完整 JSON Schema

```jsonc
{
  // ========== 元数据 ==========
  "_version": "2.0",                           // 状态文件版本（用于迁移）
  "_created": "2026-07-01T10:00:00",           // ISO 8601 创建时间
  "_updated": "2026-07-10T14:30:00",           // ISO 8601 最后更新时间
  "_last_modified_by": null,                   // 最后修改者标识（多 Agent 场景）

  // ========== 任务标识 ==========
  "task": "重构 auth 模块",                    // 任务名（必需）
  "level": "L3",                               // L1 | L2 | L3 | L4

  // ========== 控制参数 ==========
  "round": 3,                                  // 当前轮次（1-based）
  "nmax": 5,                                   // 最大轮次（L4=-1 无限制）
  "audit_every": 3,                            // 二阶审计间隔（轮）
  "audit_counter": 2,                          // 距上次审计的累计轮次
  "convergence": false,                        // 全局收敛标志
  "verdict": "continuing",                     // converged | continuing | handoff | reset

  // ========== 正反馈控制 ==========
  "positive_feedback": "off",                  // off | on_after_audit（仅 r(t) 经审计确认后开启）
  "_audit_confirmed_at": null,                 // r(t) 最近一次审计确认时间

  // ========== 研讨厅 ==========
  "upgrade_to_forum": false,                   // 是否升级到研讨厅模式

  // ========== HITL 暂停/恢复 ==========
  "paused": {
    "active": false,
    "reason": null,                            // 暂停原因
    "paused_at": null,                         // ISO 8601
    "deadline": null,                          // 预期恢复时间（可选）
    "decision_options": []                     // ["选项A", "选项B", ...]
  },

  // ========== 并发控制（协作式锁） ==========
  "_lock": {
    "held_by": null,                           // 锁持有者标识
    "acquired_at": null,                       // ISO 8601
    "expires_at": null                         // ISO 8601（超时自动释放）
  },

  // ========== 环境信号 ==========
  "_env_change_signals": {
    "count": 0,                                // 累计环境变化信号数
    "last_signal": null,                       // 最近一次信号时间
    "signals": []                              // [{time, source, description}]
  },

  // ========== 自动摘要 ==========
  "_patterns_summary": {
    "dominant_type": null,                     // A | B | C | D | null
    "type_distribution": {"A": 0, "B": 0, "C": 0, "D": 0},
    "persistent_issues": [],                   // 持续出现的偏差描述列表
    "convergence_trend": "unknown",            // converging | stagnant | diverging | unknown
    "dead_zones_resolved": 0,
    "dead_zones_total": 0
  },

  // ========== 强制执行约束（由 complexity_classify --enforce 生成） ==========
  "_enforce": {
    "allow_audit": true,
    "allow_vsm": true,
    "allow_positive_feedback": false,
    "allow_handoff_report": true,
    "allow_forum": false,
    "minimal_path_only": false,
    "nmax": 5,
    "audit_every": 3
  },

  // ========== 参照输入 ==========
  "r_t": {
    "requirements": [
      {"id": "R1", "description": "功能：登录/登出/刷新 token 行为不变", "test_cmd": "pytest tests/test_auth.py", "severity": "critical"},
      {"id": "R2", "description": "质量：所有现有测试通过", "test_cmd": "pytest", "severity": "critical"},
      {"id": "R3", "description": "约束：不改变公开 API 签名", "test_cmd": null, "severity": "high"}
    ],
    "core_assumptions": [
      "JWT 密钥轮换策略保持不变",
      "用户表结构暂不修改"
    ],
    "dead_zones": [
      {"id": "DZ1", "description": "第三方 OAuth 回调时序依赖外部服务，本地无法完整验证", "status": "open"}
    ]
  },

  // ========== 迭代历史 ==========
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
        "tau": 0,
        "measurement_method": "运行 pytest + 检查 diff"
      },
      "feedback": {
        "e_missing": [],
        "e_extra": [{"description": "新增了未使用的 TokenValidator 类", "location": "src/auth/token.py:45-67", "severity": "medium"}],
        "e_wrong": [{"requirement_id": "R2", "description": "refresh 端点返回 500", "expected": "200 + new token pair", "actual": "500 Internal Error", "severity": "critical"}],
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
    }
  ],

  // ========== 已归档轮次（r(t) 重设时） ==========
  "archived_rounds": [],

  // ========== 二阶审计日志 ==========
  "audit_log": [
    {
      "round": 3,
      "triggered_by": ["定时触发 (round=3, every=3)"],
      "questions": {
        "r_t_still_valid": true,
        "r_t_source": "JWT 轮换策略来自已批准的 API 规范 v2.1",
        "observer_bias": "可能过度关注 token 层而忽略了 session 管理",
        "structural_vs_parametric": "参数误差——缺了 UserRepository 是局部遗漏",
        "posiwid": "实际行为与目标一致"
      },
      "conclusion": "maintain",
      "actions_taken": []
    }
  ],

  // ========== 结构性问题 ==========
  "structural_patterns": [
    {
      "description": "连续 3 轮出现类型 A 偏差（e_wrong），均在 token 刷新逻辑",
      "recommendation": "考虑重构 token 刷新子系统的结构，不仅仅是调参"
    }
  ]
}
```

### 迁移路径 `1.0 → 2.0`

`migrate` 子命令自动执行以下步骤：

```
1. 设置 _version = "2.0"
2. 设置 positive_feedback = "off"、_audit_confirmed_at = null
3. 设置 upgrade_to_forum = false
4. 设置 paused = {active: false, reason: null, paused_at: null, deadline: null, decision_options: []}
5. 设置 _lock = {held_by: null, acquired_at: null, expires_at: null}
6. 设置 _last_modified_by = null
7. 设置 _env_change_signals = {count: 0, last_signal: null, signals: []}
8. 基于现有 rounds/feedback 计算 _patterns_summary（如果不是 null）
9. 基于 level 计算 _enforce（如果不是 null）
10. 原文件备份为 cybersyn_state.json.v1.0.bak
```

### `_patterns_summary` 自动计算规则

`save_state()` 每次写入前自动计算并写入：

```python
def compute_patterns_summary(state: dict) -> dict:
    rounds = state.get("rounds", [])
    if not rounds:
        return {"dominant_type": None, "type_distribution": {"A":0,"B":0,"C":0,"D":0},
                "persistent_issues": [], "convergence_trend": "unknown",
                "dead_zones_resolved": 0, "dead_zones_total": 0}

    # 偏差类型分布
    dist = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in rounds:
        dt = r.get("feedback", {}).get("deviation_type")
        if dt in dist:
            dist[dt] += 1
    dominant = max(dist, key=dist.get) if any(dist.values()) else None

    # 持续问题：出现在连续 2 轮以上的 e_wrong 或 e_missing 项
    persistent = _find_persistent_issues(rounds)

    # 收敛趋势
    trend = _assess_convergence_trend(rounds)

    # 死区
    dz = state.get("r_t", {}).get("dead_zones", [])
    resolved = sum(1 for d in dz if d.get("status") == "resolved")

    return {
        "dominant_type": dominant,
        "type_distribution": dist,
        "persistent_issues": persistent,
        "convergence_trend": trend,
        "dead_zones_resolved": resolved,
        "dead_zones_total": len(dz)
    }
```

---

## 3. Phase 1 工具规范

---

### 3.1 `cybersyn_state.py` — 状态管理器（核心）

**优先级**：P0  **预计行数**：≤350

#### 3.1.1 用途

跨轮持久化闭环迭代的全部状态。所有其他工具通过它读写任务状态。同时负责：
- 版本迁移（自动 + 手动）
- 短期记忆检索（`query`）
- 长期记忆归档（`archive`）
- HITL 暂停/恢复（`pause` / `resume`）
- 审计结论自动反馈到控制参数（`apply-audit`）
- 工具层安全边界强制执行

#### 3.1.2 完整接口

```text
# ===== 状态生命周期 =====
cybersyn_state.py init
    --level L1|L2|L3|L4
    --task "<描述>"
    [--nmax <N>]              # 默认按 level 自动设置
    [--audit-every <N>]       # 默认按 level 自动设置
    [--enforce-from <path>]   # 读取 complexity_classify --enforce 的 JSON 输出，设置 _enforce
    [--output <path>]         # 写入指定路径（默认 ./cybersyn_state.json）

cybersyn_state.py read
    [--field round|level|r_t|rounds|audit_log|convergence|verdict|
            patterns_summary|enforce|structural_patterns|paused|all]
    [--last-round]            # 只返回最后一轮
    [--format json|text]      # text=人类可读单段摘要

cybersyn_state.py update
    --stage plan|test1|feedback|modify|test2|output|audit
    --data '<JSON>'           # 或 @file.json 从文件读取
    [--round <N>]             # 指定更新哪一轮（默认当前轮）

cybersyn_state.py reset
    [--hard]                  # 不备份直接清空（谨慎）

# ===== 记忆与检索 =====
cybersyn_state.py query
    --pattern "<regex>"       # 搜索模式
    [--scope rounds|audit_log|structural_patterns|all]  # 默认 all
    [--last <N>]              # 只在最近 N 轮搜索
    [--format json|text]      # text=人类可读匹配摘要

cybersyn_state.py archive
    [--target <dir>]          # 归档目录（默认 ./cybersyn_archive/）
    [--overwrite]             # 覆盖已归档的同名任务

# ===== 审计结论反馈 =====
cybersyn_state.py apply-audit
    --conclusion maintain|reset-rt|restructure|upgrade-forum
    [--new-rt '<JSON>']       # 仅 reset-rt 时必需：新的 r(t) 定义
    [--dry-run]               # 只打印变更不写入

# ===== HITL 暂停/恢复 =====
cybersyn_state.py pause
    --reason "<描述>"
    --options "<选项A>","<选项B>",...
    [--deadline <ISO 8601>]

cybersyn_state.py resume

# ===== 版本管理 =====
cybersyn_state.py migrate
    [--dry-run]               # 预览变更不写入
    [--state <path>]          # 指定状态文件（默认 ./cybersyn_state.json）

# ===== 并发控制 =====
cybersyn_state.py lock
    --by "<agent-id>"         # 锁持有者标识
    [--timeout <seconds>]     # 超时自动释放（默认 300）

cybersyn_state.py unlock
    --by "<agent-id>"         # 必须与持锁者一致
    [--force]                 # 强制释放（管理员用）

# ===== 工具 =====
cybersyn_state.py summary     # 人类可读摘要（同 read --format text）
cybersyn_state.py validate    # 校验状态文件格式合法性
```

#### 3.1.3 `init` 默认参数表

| Level | nmax | audit_every | positive_feedback | allow_forum | allow_vsm | minimal_path_only |
|-------|------|-------------|-------------------|-------------|-----------|-------------------|
| L1    | 2    | 5           | off               | false       | false     | true              |
| L2    | 3    | 3           | off               | false       | false     | false             |
| L3    | 5    | 3           | off               | false       | true      | false             |
| L4    | -1   | 3           | off               | true        | true      | false             |

#### 3.1.4 `update` 阶段行为

| stage    | 写入字段                    | 自动副作用 |
|----------|----------------------------|-----------|
| plan     | `rounds[-1].plan`          | — |
| test1    | `rounds[-1].test1`         | — |
| feedback | `rounds[-1].feedback`      | 自动递增 `audit_counter`；调用 `enforce_safety_boundaries()` |
| modify   | `rounds[-1].modify`        | 调用 `enforce_safety_boundaries()` |
| test2    | `rounds[-1].test2`         | 调用 `enforce_safety_boundaries()` |
| output   | `convergence`, `verdict`   | — |
| audit    | `audit_log[]`              | 重置 `audit_counter = 0` |

#### 3.1.5 `apply-audit` 动作映射表

| conclusion      | 自动动作 |
|-----------------|---------|
| `maintain`      | 重置 `audit_counter = 0`；不变更 `nmax` / `audit_every` |
| `reset-rt`      | 归档当前 `rounds` → `archived_rounds`；清空 `rounds` 数组；`round` 置 1；`--new-rt` 参数写入 `r_t` |
| `restructure`   | `nmax += 2`；`audit_every = max(2, audit_every - 1)`；`positive_feedback = "off"`；将当前偏差模式追加到 `structural_patterns` |
| `upgrade-forum` | 设置 `upgrade_to_forum = true`；输出提示"转至 diversity_generator.py 执行研讨厅流程" |

#### 3.1.6 安全边界强制执行

```python
class SafetyBoundaryError(Exception):
    """触发安全边界时抛出。调用者应捕获并触发向人移交闸。"""
    pass

def enforce_safety_boundaries(state: dict, action: str) -> None:
    """
    在 update 的 modify/test1/test2 阶段自动调用。
    若 state._enforce.minimal_path_only == true，跳过（L1 极简路径）。
    """

    # 1. Nmax 检查
    nmax = state.get("nmax", -1)
    if nmax != -1 and state["round"] > nmax:
        raise SafetyBoundaryError(
            f"Nmax ({nmax}) 已超限（当前第 {state['round']} 轮）。"
            "请使用 handoff_report.py 向人移交，或 reset 后重新开始。禁止继续修改。"
        )

    # 2. 时滞检查：连续两轮偏差同向增大 → 近临界，禁止增大 k
    rounds = state.get("rounds", [])
    if len(rounds) >= 2 and action == "modify":
        last_two = rounds[-2:]
        f0 = last_two[0].get("feedback", {})
        f1 = last_two[1].get("feedback", {})
        if f0.get("deviation_type") == f1.get("deviation_type") == "A":
            e_count_0 = _total_e_count(f0)
            e_count_1 = _total_e_count(f1)
            if e_count_1 > e_count_0:
                raise SafetyBoundaryError(
                    "连续两轮偏差同向增大（近临界状态），禁止增大干预强度 k。"
                    "建议触发二阶审计。"
                )

    # 3. 正反馈加速检查
    if action == "modify":
        pf = state.get("positive_feedback", "off")
        audit_confirmed = state.get("_audit_confirmed_at")
        if pf == "on_after_audit" and not audit_confirmed:
            # 输出警告但不禁用（Agent 自行判断）
            import sys
            print("⚠ 正反馈加速已开启，但 r(t) 最近未经审计确认。建议先执行审计。", file=sys.stderr)

    # 4. enforce 字段检查
    enforce = state.get("_enforce", {})
    if enforce.get("minimal_path_only") and action in ("modify", "test2", "audit"):
        # L1 极简路径：不允许复杂操作
        pass  # L1 极简在 update 层面处理，不抛异常
```

#### 3.1.7 并发控制（协作式锁）

```python
def acquire_lock(state: dict, holder: str, timeout_sec: int = 300) -> dict:
    """获取协作式锁。若已有锁且未过期，抛 LockHeldError。"""
    lock = state.get("_lock", {})
    now = datetime.now(timezone.utc).isoformat()
    if lock.get("held_by") and lock.get("expires_at", "0") > now:
        raise LockHeldError(f"状态文件被 {lock['held_by']} 锁定至 {lock['expires_at']}")
    state["_lock"] = {
        "held_by": holder,
        "acquired_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=timeout_sec)).isoformat()
    }
    state["_last_modified_by"] = holder
    return state

def release_lock(state: dict, holder: str, force: bool = False) -> dict:
    """释放锁。force=True 跳过持有者检查。"""
    lock = state.get("_lock", {})
    if lock.get("held_by") != holder and not force:
        raise LockHeldError(f"锁由 {lock['held_by']} 持有，{holder} 无权释放")
    state["_lock"] = {"held_by": None, "acquired_at": None, "expires_at": None}
    return state
```

#### 3.1.8 核心函数清单

```python
# ---- 文件 I/O ----
def load_state(path: str) -> dict
    """读取状态文件，自动检测版本并执行迁移链。"""

def save_state(state: dict, path: str) -> None
    """原子写入：先写 .tmp，再 rename。写入前调用 compute_patterns_summary。"""

def resolve_path() -> str
    """解析状态文件路径：$CYBERSYN_STATE 环境变量 > ./cybersyn_state.json"""

# ---- 生命周期 ----
def init_state(task: str, level: str, nmax: int = None, audit_every: int = None,
               enforce_from: str = None) -> dict
    """创建新状态。按 level 自动设置默认参数。若 --enforce-from 指定文件，读取并设置 _enforce。"""

def update_round(state: dict, stage: str, data: dict, round_n: int = None) -> dict
    """按 stage 更新轮次数据。自动处理副作用（审计计数器、安全边界等）。"""

def new_round(state: dict) -> dict
    """在 rounds 数组末尾追加新轮次骨架，round 自增。"""

def reset_state(state: dict, hard: bool = False) -> dict
    """重置。非 hard 模式先备份原文件为 .bak。"""

# ---- 记忆与检索 ----
def query_state(state: dict, pattern: str, scope: str = "all", last_n: int = None) -> list[dict]
    """在状态文件内做结构化正则搜索。返回 [{round, field, snippet, severity}]。"""

def archive_state(state: dict, target_dir: str, overwrite: bool = False) -> str
    """将 _patterns_summary + 任务名/L 级/总轮次 追加到 archive.ndjson。返回归档文件路径。"""

# ---- 审计反馈 ----
def apply_audit_conclusion(state: dict, conclusion: str, new_rt: dict = None) -> dict
    """根据审计结论修改控制参数。"""

# ---- HITL ----
def pause_state(state: dict, reason: str, options: list[str], deadline: str = None) -> dict
    """设置暂停标记和待决策选项。"""

def resume_state(state: dict) -> dict
    """清除暂停标记。"""

# ---- 版本管理 ----
def migrate_state(state: dict, dry_run: bool = False) -> dict
    """执行 1.0→2.0 迁移。非 dry_run 模式先备份原文件。"""

# ---- 并发 ----
def acquire_lock(state: dict, holder: str, timeout_sec: int) -> dict
def release_lock(state: dict, holder: str, force: bool) -> dict

# ---- 安全 ----
def enforce_safety_boundaries(state: dict, action: str) -> None

# ---- 摘要 ----
def compute_patterns_summary(state: dict) -> dict
    """自动计算 _patterns_summary。在 save_state 前自动调用。"""

def summary(state: dict) -> str
    """生成人类可读单段摘要。"""

def validate_state(state: dict) -> list[str]
    """校验状态文件格式合法性，返回问题列表。空列表=合法。"""

# ---- 内部辅助 ----
def _total_e_count(feedback: dict) -> int
    """统计 e_missing + e_extra + e_wrong 总条数。"""

def _assess_convergence_trend(rounds: list) -> str
    """根据最近 3 轮的偏差计数判趋势：converging | stagnant | diverging | unknown。"""

def _find_persistent_issues(rounds: list) -> list[str]
    """发现出现在连续 2+ 轮中的同一偏差描述。"""

def _ensure_round_exists(state: dict, round_n: int) -> None
    """确保 rounds 数组中存在指定轮次，不存在则自动创建骨架。"""
```

#### 3.1.9 边缘情况

| 情况 | 行为 |
|------|------|
| `read` 状态文件不存在 | stderr: `{"error": "状态文件不存在: ./cybersyn_state.json", "code": 1}` |
| `update` 状态文件不存在 | stderr: `{"error": "状态文件不存在。请先 cybersyn_state.py init", "code": 1}` |
| `init` 文件已存在 | 提示确认覆盖，或通过 `--force` 跳过确认（交互式由 Agent 判断） |
| `update --round N` 指定不存在的轮次 | 自动填充中间轮次的空白骨架，不报错 |
| 两个进程同时 `update` | 原子写入（.tmp→rename）保证不损坏；协作式锁提供额外保护 |
| `migrate` 目标版本已是当前版本 | 输出 "已是 2.0 版本，无需迁移"，exit code 0 |
| `query` 无匹配 | 输出 `{"matches": []}`，exit code 0 |
| `archive --overwrite` | 覆盖 ndjson 中同 task 名的记录行 |
| `pause` 时已暂停 | 更新 reason/options/deadline（覆盖旧值） |
| `resume` 时未暂停 | 输出警告但不报错 |

#### 3.1.10 验证标准

- [ ] `init` → 产生有效 v2.0 JSON，`validate` 无报错
- [ ] `read --field all` → 可正确回读所有字段
- [ ] `update feedback` 后 `read --field round` → 显示当前轮次
- [ ] 两个并发 `update` 不会损坏文件（原子写入）
- [ ] 状态文件缺失时所有命令给出明确错误信息
- [ ] `migrate` 将 v1.0 文件转为 v2.0，备份原文件
- [ ] `query --pattern "refresh"` → 仅在匹配字段中返回结果
- [ ] `archive` → ndjson 文件追加一行有效 JSON
- [ ] `apply-audit --conclusion restructure` → nmax+2, audit_every-1
- [ ] `apply-audit --conclusion reset-rt --new-rt` → 旧 rounds 归档，新 r_t 生效
- [ ] `pause --reason` → paused.active=true, 后续 modify 操作被安全边界警告
- [ ] `lock --by agent-1` + 另一进程 `lock --by agent-2` → 抛 LockHeldError
- [ ] Nmax 超限后 `update --stage modify` → 抛 SafetyBoundaryError
- [ ] 连续两轮 e_wrong 增大后 `update --stage modify` → 抛 SafetyBoundaryError

---

### 3.2 `checklist_compare.py` — 验收清单对比器

**优先级**：P0  **预计行数**：≤250

#### 3.2.1 用途

对比 r(t) 需求清单与实际产物 y(t)，自动生成 `缺失 / 多余 / 错误` 三项清单。对应闭环的 测试₁ 和 反馈 阶段。

#### 3.2.2 接口

```text
checklist_compare.py
    --requirements <json_array_or_@file.json>
    --actual <text_or_@file>
    [--mode code|text]           # 默认 code
    [--baseline <path>]          # ★新增：基线文件/目录（mode=code 时用于检测多余文件）
    [--test-timeout <seconds>]   # ★新增：测试命令超时（默认 60）
    [--format json|text]         # 默认 json
```

#### 3.2.3 mode=code 逻辑

```
输入：
  --requirements: [{"id":"R1", "description":"...", "test_cmd":"pytest test_auth.py", "severity":"critical"}, ...]
  --actual: diff 文本或文件路径
  --baseline: 基线目录路径（如 git HEAD 的 tree）

处理：
  1. 对每条 requirement：
     a. 若有 test_cmd：subprocess.run(test_cmd, timeout=test_timeout)
        - exit 0 → covered
        - exit ≠ 0 → wrong（捕获 stdout/stderr 作为 actual）
        - TimeoutExpired → unverified
     b. 若无 test_cmd：在 actual diff 中搜索相关模块/函数名
        - 触及相关代码 → covered（需 Agent 确认）
        - 未触及 → unverified
  2. 检测多余（extra）：
     a. 若 --baseline 指定：diff baseline 和当前目录，标记新增的未在 requirements 中引用的文件/类/函数
     b. 若无 --baseline：提取 actual diff 中所有 + 行，用启发式检测新增的类/函数定义
  3. 输出 e(t) JSON

质量指标：
  - 有 test_cmd 的项覆盖度 = covered / total_with_test_cmd
  - 总覆盖度 = (covered + unverified) / total（unverified 不算失败）
```

#### 3.2.4 mode=text 逻辑

```
输入：
  --requirements: [{"id":"R1", "criterion":"必须包含错误处理", "keywords":["error","exception","try-catch"], "severity":"high"}, ...]
  --actual: 文本内容或文件路径

处理：
  1. 对每条 criterion：
     a. 在 actual 中搜索每个 keyword（大小写不敏感正则）
     b. 匹配度 = 匹配到的 keyword 数 / 总 keyword 数
        - ≥0.8 → covered
        - 0.3–0.8 → partial
        - <0.3 → missing
  2. 检测多余（extra）：
     a. 用正则提取 actual 中的所有标题/段落首句
     b. 与所有 requirements 的 keywords 做相似度匹配（SequenceMatcher）
     c. 相似度 < 0.3 的段落标记为 extra
  3. 输出 e(t) JSON
```

#### 3.2.5 输出 JSON

```json
{
  "missing": [
    {"requirement_id": "R3", "description": "刷新 token 端点测试", "severity": "high", "evidence": "test_cmd 'pytest test_refresh.py' 返回 exit 1"}
  ],
  "extra": [
    {"description": "新增 TokenValidator 类", "location": "src/auth/token.py:45-67", "severity": "medium", "evidence": "baseline 对比：新增文件/函数不在任何 requirement 引用中"}
  ],
  "wrong": [
    {"requirement_id": "R2", "description": "refresh 端点返回 500", "expected": "200 + new token pair", "actual": "500 Internal Error: UserRepository not injected", "severity": "critical"}
  ],
  "unverified": [
    {"requirement_id": "R5", "description": "OAuth 回调时序正确", "reason": "无 test_cmd 且 diff 中未检测到相关代码变更"}
  ],
  "summary": {
    "total": 5,
    "covered": 2,
    "missing": 1,
    "extra": 1,
    "wrong": 1,
    "unverified": 1
  },
  "suggested_deviation_type": "A",
  "quality_indicators": {
    "test_coverage": "2/3 有测试命令的项通过",
    "keyword_coverage": "N/A（code mode 不适用）"
  }
}
```

`suggested_deviation_type` 推断规则：
- 纯 missing/wrong → "A"（执行偏差）
- unverified 占比 > 50% → "B"（测量偏差：验证手段不足）
- 需求与产物方向不一致（extra 项 > covered 项）→ "C"（可能环境/需求漂移）
- 全部 unverified → "B"

#### 3.2.6 核心函数清单

```python
# ---- 加载 ----
def load_requirements(source: str) -> list[dict]
    """从 JSON 字符串或 @file.json 加载需求列表。校验必填字段。"""

def load_actual(source: str) -> str
    """从 @file 或直接文本获取 y(t)。"""

# ---- 代码模式 ----
def run_test(test_cmd: str, timeout: int) -> tuple[bool, str]
    """运行测试，返回 (passed, output)。TimeoutExpired 返回 (None, "TIMEOUT")。"""

def check_baseline_diff(baseline_path: str, requirements: list) -> list[dict]
    """检测新增/修改的文件中未在 requirements 中引用的项（多余）。"""

def compare_code(requirements: list, actual: str, baseline: str, timeout: int) -> dict
    """代码模式主逻辑。"""

# ---- 文本模式 ----
def keyword_match(criterion: dict, actual: str) -> dict
    """对单条 criterion 做关键词匹配。返回 {status, match_rate, matched_kw, missed_kw}。"""

def detect_text_extra(actual: str, all_keywords: set[str]) -> list[dict]
    """检测文本中超出需求的段落/要点。"""

def compare_text(requirements: list, actual: str) -> dict
    """文本模式主逻辑。"""

# ---- 输出 ----
def suggest_deviation_type(result: dict) -> str
    """根据 missing/wrong/extra/unverified 分布推断偏差类型 A/B/C。"""

def render_json(result: dict) -> str
def render_text(result: dict) -> str
```

#### 3.2.7 边缘情况

| 情况 | 行为 |
|------|------|
| 需求为 `[]` | 输出 `{"missing":[], "extra":[], "wrong":[], "summary":{"total":0}, "warning":"无验收标准，无法自动对比"}` |
| 产物文件不存在 | stderr: `{"error": "actual 文件不存在: <path>", "code": 2}` |
| 测试命令执行超时 | 标记该 requirement 为 `unverified`，reason="TIMEOUT"，不阻塞其余 |
| 基线路径不存在 | 跳过 extra 检测，输出中标注 `"extra_detection": "skipped (no baseline)"` |
| requirement 无 id 字段 | 自动分配 `"auto-R<N>"` |
| 混合 severity | 不影响逻辑，仅透传 |

#### 3.2.8 验证标准

- [ ] 5 条 requirement：3 通过、1 失败、1 缺失 → `missing=1, wrong=1, covered=3`
- [ ] 无 test_cmd 的 requirement → 状态 `unverified`，不计入 wrong
- [ ] 空产物文本 → 全部 requirement 标记为 missing
- [ ] `--mode text` + 关键词不匹配 → partial/missing 正确分类
- [ ] `--baseline` 检测到新增文件不在 requirements 中 → extra 列表包含该项
- [ ] `--test-timeout 1` + 慢测试 → unverified + reason="TIMEOUT"
- [ ] 所有 test_cmd 返回 exit 0 → `suggested_deviation_type` ≠ "B"（除非全部 unverified）

---

### 3.3 `diversity_generator.py` — 研讨厅多模型分歧生成器

**优先级**：P0（★新增）  **预计行数**：≤300

#### 3.3.1 用途

当系统进入研讨厅模式（L4 / 持续不收敛 / `upgrade_to_forum == true`）时，对同一问题生成 ≥3 个不同结构/策略的备选方案，计算预测分歧矩阵。对应 Skill 文档第 7 节研讨厅原则 1（多视角并行分析）。

> **关键设计约束（设计决策 #6）**：`diversity_generator` 不依赖 LLM，只生成策略模板和框架性描述。具体的方案细节由调用它的 Agent 或人在生成模板的基础上填充。工具只保证"≥3 个不同结构"和"分歧矩阵"的形式正确性。

#### 3.3.2 接口

```text
diversity_generator.py
    --task "<描述>"
    --strategies <N>                       # 生成策略数（默认 3，至少 2）
    [--context <cybersyn_state.json>]      # 读取偏差历史，自动选择策略方向
    [--perspectives conservative,refactor,exploratory,...]  # 手动指定策略视角
    [--output <path>]                      # 输出文件路径
    [--format json|markdown]               # 默认 markdown
```

#### 3.3.3 五种策略视角

| 视角标识 | 策略方向 | 触发条件（从 context 偏差历史推断） |
|---------|---------|-----------------------------------|
| `conservative` | 最小改动，现有结构内局部优化 | 偏差类型以 A 为主、收敛趋势向好 |
| `refactor`    | 重构核心接口/数据结构，换取长期可维护性 | 出现 structural_patterns、同类型偏差持续 |
| `exploratory` | 试用新架构/模式，探索替代方案 | L4 任务、env_change_signals 频繁 |
| `decompose`   | 拆分模块，降低耦合度 | 涌现偏差(D)、跨模块集成异常 |
| `integrate`   | 合并功能，减少接口数量 | extra 项过多、重复定义 |

**自动选择策略**（`--context` 指定但无 `--perspectives`）：

```python
def auto_select_perspectives(state: dict, count: int) -> list[str]:
    """
    1. 读取 _patterns_summary.dominant_type
    2. 读取 structural_patterns
    3. 读取 level 和环境信号
    4. 优先选择最有差异性的组合：
       - D 型偏差 → decompose + refactor + conservative
       - C 型偏差 + env_change → exploratory + refactor + conservative
       - A 型偏差 + 持续 → refactor + decompose + conservative
       - L4 无特殊信号 → exploratory + refactor + decompose
       - 默认 → conservative + refactor + exploratory
    返回 count 个互不相同的 perspective
    """
```

#### 3.3.4 每种视角的策略模板结构

```python
STRATEGY_TEMPLATE = {
    "conservative": {
        "name": "保守型：局部优化",
        "principles": [
            "在现有模块边界内修改，不引入新抽象层",
            "优先修复偏差中 severity=critical 的项",
            "保持现有接口签名不变"
        ],
        "effort_profile": {"files": "≤2", "new_abstractions": 0, "risk": "低"},
        "prediction_template": "解决当前 e_wrong 列表中的 {n} 项问题，不改变架构复杂度"
    },
    "refactor": {
        "name": "重构型：结构优化",
        "principles": [
            "识别并消除 structural_patterns 中的结构性问题",
            "引入必要的抽象层/接口以降低耦合",
            "可能改变内部模块边界，但对外接口兼容"
        ],
        "effort_profile": {"files": "3-8", "new_abstractions": "1-3", "risk": "中"},
        "prediction_template": "从结构层面解决 persistent_issues: {issues}，短期可能引入新偏差但长期降低维护成本"
    },
    # ... exploratory, decompose, integrate 类似
}
```

#### 3.3.5 输出 JSON

```json
{
  "task": "重构 auth 模块",
  "generated_at": "2026-07-10T10:00:00",
  "context_from_state": {
    "level": "L3",
    "round": 5,
    "dominant_type": "A",
    "structural_patterns": ["连续 5 轮出现类型 A 偏差（token 刷新逻辑）"]
  },
  "strategies": [
    {
      "name": "保守型：接口封装",
      "perspective": "conservative",
      "description": "在现有 Controller-Service-Repository 结构内，将 token 逻辑提取到独立 service",
      "principles": [
        "在现有模块边界内修改，不引入新抽象层",
        "优先修复偏差中 severity=critical 的项",
        "保持现有接口签名不变"
      ],
      "estimated_effort": "2 文件修改",
      "risk": "低",
      "predicted_outcome": "解决 e_wrong（refresh 500），但不改变整体架构"
    },
    {
      "name": "重构型：命令查询分离",
      "perspective": "refactor",
      "description": "将 auth 模块按 CQRS 模式拆分为 AuthRead 和 AuthWrite 两个子模块",
      "principles": [
        "消除 structural_patterns 中的 token 刷新逻辑反复出错问题",
        "引入读写分离接口层",
        "对外公开 API 签名保持兼容"
      ],
      "estimated_effort": "5 文件修改 + 1 新接口定义",
      "risk": "中",
      "predicted_outcome": "从结构层面解决 token 刷新反复出错问题，短期可能引入新的集成偏差"
    },
    {
      "name": "探索型：引入 OAuth 代理层",
      "perspective": "exploratory",
      "description": "用独立 OAuth 代理服务封装所有第三方认证，auth 模块只做本地 token 管理",
      "principles": [
        "试探新架构假设：第三方认证应该与应用逻辑解耦",
        "auth 模块缩减为 token 本地管理 + 代理转发",
        "引入新组件（OAuth Proxy）"
      ],
      "estimated_effort": "8 文件修改 + 新服务部署",
      "risk": "高",
      "predicted_outcome": "长期灵活性最高，但短期不确定性大，需要人工评估技术可行性"
    }
  ],
  "divergence_matrix": {
    "shared_assumptions": ["JWT 作为核心 token 格式不变"],
    "key_disagreements": [
      {
        "dimension": "对接第三方 OAuth 的方式",
        "conservative": "直接调用",
        "refactor": "接口抽象",
        "exploratory": "独立代理"
      },
      {
        "dimension": "Token 存储位置",
        "conservative": "现有 DB",
        "refactor": "新 cache 层",
        "exploratory": "分布式 session store"
      }
    ],
    "prediction_divergence": "三种策略对 '新增 OAuth provider 的适配成本' 的预测差异达 3 倍以上"
  },
  "recommendation": "分歧集中在 OAuth 对接方式上。建议先做'接口抽象'（重构型最低成本的第一步），保留未来切换到独立代理的灵活性。",
  "human_review_required": true
}
```

#### 3.3.6 Markdown 输出格式

```markdown
# 研讨厅：多模型分歧分析 — [任务名]

**生成时间**：2026-07-10T10:00:00
**复杂度**：L3 | **当前轮次**：5/5 | **主导偏差**：A

---

## 策略 A：保守型 — 接口封装

**风险**：🟢 低 | **预估工作量**：2 文件

### 原则
- 在现有模块边界内修改，不引入新抽象层
- 优先修复偏差中 severity=critical 的项

### 方案描述
在现有 Controller-Service-Repository 结构内...

### 预测结果
解决 e_wrong（refresh 500），但不改变整体架构

---

## 策略 B：重构型 — 命令查询分离

...（同上结构）...

---

## 策略 C：探索型 — OAuth 代理层

...（同上结构）...

---

## 分歧矩阵

| 维度 | 保守型 | 重构型 | 探索型 |
|------|--------|--------|--------|
| OAuth 对接方式 | 直接调用 | 接口抽象 | 独立代理 |
| Token 存储 | 现有 DB | 新 cache 层 | session store |

**关键分歧**：三种策略对新增 OAuth provider 的适配成本预测差异达 3 倍以上

---

## 建议

分歧集中在 OAuth 对接方式上。建议先做"接口抽象"，保留灵活性。

⚠ **需要人工审查后决策。**
```

#### 3.3.7 核心函数清单

```python
# ---- 加载 ----
def load_context(path: str) -> dict
    """从状态文件读取偏差历史和结构模式。返回精简上下文。"""

# ---- 策略选择 ----
def auto_select_perspectives(context: dict, count: int) -> list[str]
    """基于偏差历史自动选择最有差异性的策略视角组合。"""

# ---- 策略生成 ----
def generate_strategy(perspective: str, task: str, context: dict) -> dict
    """基于视角模板 + 上下文，生成一个策略方案。"""

def generate_conservative(task: str, context: dict) -> dict
def generate_refactor(task: str, context: dict) -> dict
def generate_exploratory(task: str, context: dict) -> dict
def generate_decompose(task: str, context: dict) -> dict
def generate_integrate(task: str, context: dict) -> dict

# ---- 分歧分析 ----
def compute_divergence(strategies: list[dict]) -> dict
    """
    比较各策略的关键设计维度，提取：
    1. shared_assumptions：各策略共识的假设
    2. key_disagreements：各维度上的分歧
    3. prediction_divergence：分歧的定性描述
    """

def extract_dimensions(strategies: list[dict]) -> list[str]
    """从各策略描述中提取可比较的设计维度。"""

# ---- 输出 ----
def render_markdown(task: str, strategies: list, divergence: dict, context: dict) -> str
def render_json(task: str, strategies: list, divergence: dict, context: dict) -> dict
```

#### 3.3.8 边缘情况

| 情况 | 行为 |
|------|------|
| `--strategies 2` | 生成 2 个策略，但在 warnings 中标注"研讨厅原则要求至少 3 个不同结构的模型" |
| `--context` 状态文件无有效 rounds | 使用默认视角组合：conservative + refactor + exploratory |
| `--perspectives` 指定了不存在的视角名 | stderr 错误，列出可用视角 |
| 策略视角数 > `--strategies N` | 取前 N 个 |
| `--context` 中 `upgrade_to_forum == true` | 输出顶部加 "⚠ 研讨厅模式" 标记 |

#### 3.3.9 验证标准

- [ ] `--strategies 3` → 返回 3 个不同 perspective 的策略
- [ ] 每个策略有 `risk` 和 `predicted_outcome` 字段
- [ ] `divergence_matrix.key_disagreements` 至少包含 1 个维度
- [ ] `< 2` 个策略时输出警告
- [ ] `--context` + `upgrade_to_forum == true` → 输出含研讨厅标记
- [ ] `--format markdown` → 人类可读的完整分歧分析报告
- [ ] `--format json` + `| python -m json.tool` → 合法 JSON

---

## 4. Phase 2 工具规范

---

### 4.1 `convergence_check.py` — 收敛检测器（含增益/能量/周期/漂移）

**优先级**：P1  **预计行数**：≤350

#### 4.1.1 用途

比较当前轮 e(t) 与历史轮次，判定收敛状态。扩展功能包括：
- **增益分析**（P1-1）：量化"干预产生了多少效果"
- **稳定性能量函数**（P2-3）：Lyapunov 启发的偏差能量度量
- **周期性分析**（P2-1）：检测偏差是否出现周期性模式（极限环）
- **环境漂移检测**（P1-3）：检测核心假设是否仍与环境匹配
- **稳态/暂态区分**（P2-2）：区分过渡过程与稳态偏差

#### 4.1.2 接口

```text
convergence_check.py
    --state <cybersyn_state.json>
    [--energy]          # ★新增：输出偏差能量函数值
    [--periodic]        # ★新增：检测偏差周期性
    [--drift]           # ★新增：检测环境漂移（触发 detect_env_drift）
    [--verbose]
    [--format json|text]
```

#### 4.1.3 收敛判定逻辑

```
输入：state 的 rounds 数组（所有完成轮次的 feedback）
输出：{ "status": "converged" | "continuing" | "handoff", "reasons": [...], ... }

收敛条件（全部满足）：
1. 最近两轮 e_missing、e_extra、e_wrong 三项均无新增项
2. 最近一轮没有任何 critical severity 项
3. 偏差幅度递减（本轮 e 总计数 ≤ 上轮）
4. 无新问题引入（本轮 test2 的 e2 不包含 e1 未见过的项）
5. ★新增：若 --energy，最近两轮增益 > 0.3（干预有效）

继续条件：
- 偏差在减少但未归零
- 有新问题但非 critical
- 偏差能量 E > 0 但 E 在下降

移交条件（任一满足）：
- round > nmax（含 nmax=-1 无限制时永假）
- 连续 2 轮偏差同向增大（近发散）
- 偏差类型从 A/B 突变为 C/D
- 出现涌现偏差 D 且无法分解
- ★新增：若 --energy，连续两轮 gain < 0.3 且 E 不降（低增益停滞）
- ★新增：若 --periodic，检测到极限环（周期性振荡不收敛）
- ★新增：若 --drift，环境漂移分数 > 阈值（0.5）
```

#### 4.1.4 增益分析（P1-1）

```python
def compute_gain_ratio(state: dict) -> dict:
    """
    近似计算每轮干预的"增益"：
    gain_n = |Δe(t)_n| / k_n

    其中：
      |Δe(t)_n| = e(t)_n 总项数变化绝对值（相对于上轮）
      k_n = 第 n 轮修改的量化强度：
            微调=1, 局部重写=2, 整体重构=3（从 modify.k 推断）

    返回：
    {
      "gains": [null, 0.5, 1.0, 0.2, ...],   # 首轮无参考→null
      "avg_gain": 0.57,
      "trend": "declining",                    # improving | stable | declining
      "low_gain_warning": true,                # 连续两轮 gain < 0.3
      "recommendation": "增益递减中，若连续两轮 < 0.3 建议换策略"
    }
    """

def infer_k_intensity(modify: dict) -> int:
    """从 modify.k 文本推断强度数值。"""
    k_text = (modify.get("k") or "").lower()
    if "微调" in k_text or "minor" in k_text: return 1
    if "局部" in k_text or "local" in k_text: return 2
    if "整体" in k_text or "全局" in k_text or "full" in k_text: return 3
    return 2  # 默认
```

#### 4.1.5 稳定性能量函数（P2-3）

```python
def compute_energy(state: dict) -> dict:
    """
    受 Lyapunov 方法启发，将偏差向量映射为标量能量值：

    E(n) = w_c * N_critical + w_h * N_high + w_m * N_medium + w_l * N_low
    其中 w_c=8, w_h=4, w_m=2, w_l=1（严重度权重为 2 的幂，模拟二进制位）

    返回：
    {
      "current": 4.2,
      "series": [12.0, 8.0, 3.0, 4.2],     # 每轮能量值
      "delta": 1.2,                           # ΔE = E(n) - E(n-1)
      "delta_trend": "flat",                  # decreasing | flat | increasing
      "limit_cycle_detected": true,           # E 振荡不降（±10% 波动持续 3+ 轮）
      "suggestion": "偏差能量振荡不降，可能存在极限环。建议触发二阶审计。"
    }

    limit_cycle 检测规则：
    - 最近 3 轮 E 值在均值 ±10% 内振荡
    - 且没有单调下降趋势
    """

def e_count_by_severity(feedback: dict) -> dict:
    """统计 e_missing/e_extra/e_wrong 中各 severity 的条数。"""
```

#### 4.1.6 周期性分析（P2-1）

```python
def detect_periodicity(state: dict) -> dict:
    """
    检查偏差序列是否出现周期性模式（潜在的极限环）。
    方法：对 e_wrong_count 序列做自相关检测。

    返回：
    {
      "detected": true,
      "period": 3,
      "pattern": "每 3 轮出现类型 A 的 e_extra",
      "confidence": 0.7,
      "severity": "medium",
      "recommendation": "周期性偏差提示结构性问题，建议触发二阶审计检查执行策略。"
    }

    检测逻辑：
    1. 从 rounds 中提取每轮的 (deviation_type, e_wrong_count, e_extra_count)
    2. 对 e_wrong_count 序列做滞后自相关（lag 1 到 floor(n/2)）
    3. 若某 lag 的自相关系数 > 0.7 → 存在周期
    4. 若 deviation_type 也呈现周期性（如 A,A,A,... 或 A,B,A,B,...）→ confidence 提升
    """
```

#### 4.1.7 环境漂移检测（P1-3）

```python
def detect_env_drift(state: dict) -> dict:
    """
    检测初始 r(t) 核心假设是否仍与环境匹配。

    检测维度：
    1. 核心假设 vs _env_change_signals 匹配度检查
    2. 连续多轮偏差类型 C（环境漂移）的频次
    3. _env_change_signals.count 自增趋势

    返回：
    {
      "drift_detected": true,
      "confidence": 0.8,
      "drift_score": 0.7,
      "threshold": 0.5,
      "dimensions": [
        {"assumption": "JWT 密钥轮换策略保持不变", "status": "still_valid"},
        {"assumption": "用户表结构暂不修改", "status": "contradicted_by_input",
         "evidence": "新需求要求新增字段"},
        {"assumption": "API 响应格式不变", "status": "unverifiable_locally"}
      ],
      "recommendation": "核心假设 '用户表结构暂不修改' 已被新输入推翻，建议暂停并重设 r(t)。"
    }

    drift_score 计算规则：
    - 每条被推翻的假设贡献 1/len(assumptions)
    - 每条 unverifiable 贡献 0.3/len(assumptions)
    - C 型偏差连续 2+ 轮额外 +0.3
    - _env_change_signals.count > 0 额外 +0.1*(min(count, 5))
    - 最终 score = 上述各项之和，上限 1.0
    """
```

#### 4.1.8 稳态/暂态区分信号（P2-2）

```python
def detect_transient_steady(state: dict) -> dict:
    """
    区分当前偏差是过渡过程的正常暂态，还是已达稳态的残留偏差。

    判定规则：
    - 过渡过程特征：偏差在每轮减少，且减少速率不递减 → transient（继续迭代有效）
    - 稳态特征：偏差连续 2 轮不变，或减少速率趋近零 → steady（已达当前策略的极限）

    返回：
    {
      "phase": "transient",                   # transient | approaching_steady | steady
      "evidence": [],
      "recommendation": "..."
    }
    """
```

#### 4.1.9 完整输出 JSON（`--energy --periodic --drift`）

```json
{
  "status": "continuing",
  "round": 3,
  "nmax": 5,
  "trend": {
    "e_missing_count": [1, 1, 0],
    "e_wrong_count":  [2, 1, 0],
    "e_extra_count":  [1, 0, 0]
  },
  "gain_analysis": {
    "gains": [null, 2.0, 0.5],
    "avg_gain": 1.25,
    "trend": "declining",
    "low_gain_warning": false,
    "recommendation": "增益递减中，当前仍在有效区间"
  },
  "energy": {
    "current": 2.0,
    "series": [12.0, 4.0, 2.0],
    "delta": -2.0,
    "delta_trend": "decreasing",
    "limit_cycle_detected": false,
    "suggestion": null
  },
  "periodic": {
    "detected": false,
    "period": null,
    "pattern": null,
    "confidence": null,
    "severity": null
  },
  "env_drift": {
    "drift_detected": false,
    "score": 0.15,
    "threshold": 0.5,
    "dimensions": [
      {"assumption": "JWT 密钥轮换策略保持不变", "status": "still_valid"},
      {"assumption": "用户表结构暂不修改", "status": "still_valid"}
    ],
    "recommendation": "环境稳定，核心假设成立"
  },
  "transient_steady": {
    "phase": "transient",
    "evidence": ["偏差每轮减少 50% 以上"],
    "recommendation": "继续迭代，当前策略有效"
  },
  "reasons": ["偏差持续减少但 e_missing 仍有 1 项未解决"],
  "recommendation": "继续迭代，重点解决残留的 R3 缺失项"
}
```

#### 4.1.10 核心函数清单

```python
# ---- 主入口 ----
def convergence_verdict(state: dict, flags: dict) -> dict
    """综合所有子分析，输出最终判定。"""

# ---- 基础收敛 ----
def extract_deviation_history(state: dict) -> list[dict]
def compare_rounds(current: dict, previous: dict) -> dict
def assess_trend(history: list) -> str

# ---- 增益分析（P1-1） ----
def compute_gain_ratio(state: dict) -> dict
def infer_k_intensity(modify: dict) -> int

# ---- 能量函数（P2-3） ----
def compute_energy(state: dict) -> dict
def e_count_by_severity(feedback: dict) -> dict

# ---- 周期性检测（P2-1） ----
def detect_periodicity(state: dict) -> dict
def autocorrelation(series: list[float], lag: int) -> float

# ---- 环境漂移（P1-3） ----
def detect_env_drift(state: dict) -> dict

# ---- 稳态/暂态（P2-2） ----
def detect_transient_steady(state: dict) -> dict

# ---- 输出 ----
def render_json(result: dict) -> str
def render_text(result: dict) -> str
```

#### 4.1.11 验证标准

- [ ] 两轮 e(t) 完全相同 → `status: "converged"`
- [ ] 本轮 wrong 从 3→1 → `status: "continuing"`, trend 显示递减
- [ ] round=5, nmax=5 → `status: "handoff"`, reasons 含 "Nmax reached"
- [ ] 无上轮数据（第一轮）→ `status: "continuing"`, reason="首轮，无对比基准"
- [ ] `--energy` + 连续 3 轮 E 不减 → `energy.limit_cycle_detected: true`
- [ ] `--periodic` + 自相关 > 0.7 → `periodic.detected: true`
- [ ] `--drift` + C 型偏差连续 2 轮 → `env_drift.drift_detected: true`
- [ ] 连续两轮 gain < 0.3 → 收敛条件不满足, `gain_analysis.low_gain_warning: true`

---

### 4.2 `audit_trigger.py` — 二阶审计触发器（含自动结论推荐）

**优先级**：P1  **预计行数**：≤250

#### 4.2.1 用途

跟踪迭代轮次和偏差模式，在满足条件时提醒触发二阶审计，并输出审计问题清单。扩展功能：基于 checklist 回答模式自动推荐结论（P1-2）。

#### 4.2.2 接口

```text
audit_trigger.py
    --state <cybersyn_state.json>
    [--auto-conclude]        # ★新增：基于 checklist 回答自动推荐审计结论
    [--force]                # ★新增：绕过 Nmax 检查强制执行审计
    [--format json|text]
```

#### 4.2.3 触发条件（任一满足即触发）

1. `round % audit_every == 0`（定时触发）
2. 同一偏差类型连续 2 轮未消除
3. 偏差类型从 A/B 突变为 C/D
4. `round > nmax / 2` 且未收敛
5. 手动标记：state 中有 `force_audit: true`
6. ★新增：`convergence_check.py --energy` 报告 `limit_cycle_detected: true`
7. ★新增：`convergence_check.py --drift` 报告 `drift_detected: true`
8. ★新增：`_env_change_signals.count` 自上次审计以来新增 > 0

触发条件 6-8 需要 Agent 在调用 audit_trigger 前先运行 convergence_check 并传递结果（通过 `--extra-context` 或直接检查状态文件中的 `_patterns_summary`）。

#### 4.2.4 自动结论推荐逻辑（`--auto-conclude`）

```python
def recommend_conclusion(state: dict) -> dict:
    """
    基于 checklist 回答模式 + 偏差历史 + 环境信号推荐结论。

    规则优先级：
    1. 出现 C 型偏差 + _env_change_signals 有变化 → reset-rt
    2. 出现 D 型偏差 → upgrade-forum
    3. structural_patterns 非空 + 同类偏差 ≥3 轮 → restructure
    4. 连续 2 轮 gain < 0.3（需先运行 convergence_check）→ restructure
    5. 偏差在改善但未收敛 → maintain
    6. 默认 → maintain

    返回：
    {
      "recommended_conclusion": "restructure",
      "confidence": 0.7,
      "reasoning": "偏差类型 A 连续 3 轮未消除，且增益递减。建议重构执行策略。",
      "suggested_actions": [
        "cybersyn_state.py apply-audit --conclusion restructure",
        "diversity_generator.py --task '重构 auth 模块' --context cybersyn_state.json --strategies 3"
      ]
    }
    """
```

#### 4.2.5 输出 JSON

```json
{
  "trigger": true,
  "reasons": ["定时触发 (round=3, every=3)"],
  "audit_round": 3,
  "checklist": [
    "1. r(t) 假设从哪来？最近验证过吗？若 r(t) 本身错，偏差分析还成立吗？",
    "2. 我是否只选了支持先验的测量方式、回避了不想看的区域？",
    "3. 这是参数误差还是结构问题？需换执行策略形状/增大多样性吗？",
    "4. 实际在做的 vs 声称要做的，差距持续则改行为还是改声明？(POSIWID)"
  ],
  "recommended_conclusion": "restructure",
  "confidence": 0.7,
  "reasoning": "偏差类型 A 连续 3 轮未消除，且 gain_analysis 显示增益递减。",
  "suggested_actions": [
    "cybersyn_state.py apply-audit --conclusion restructure",
    "diversity_generator.py --task '重构 auth 模块' --context cybersyn_state.json --strategies 3"
  ],
  "previous_audit_conclusion": "maintain（第 3 轮）",
  "warning": "若 r(t) 最近未经审计确认，禁止开启正反馈加速"
}
```

#### 4.2.6 核心函数清单

```python
# ---- 触发检测 ----
def check_periodic(state: dict) -> tuple[bool, str]
def check_same_type_persist(state: dict) -> bool
def check_type_mutation(state: dict) -> bool
def check_stall(state: dict) -> bool
def check_env_signals(state: dict) -> bool     # ★新增

# ---- 清单生成 ----
def generate_checklist(state: dict) -> list[str]
    """根据偏差类型、轮次、环境信号定制审计清单。如：
       - C 型偏差 → 清单侧重 'r(t) 假设是否被推翻'
       - D 型偏差 → 清单侧重 '子系统交互假设'
       - 多次 A 型 → 清单侧重 '结构 vs 参数'
    """

# ---- 结论推荐 ----
def recommend_conclusion(state: dict) -> dict

# ---- 主入口 ----
def audit_trigger(state: dict, auto_conclude: bool, force: bool) -> dict
```

#### 4.2.7 验证标准

- [ ] round=3, audit_every=3 → `trigger: true`, reasons 含定时
- [ ] round=2, 最近两轮都是类型 A → `trigger: true`
- [ ] round=1, 无特殊条件 → `trigger: false`
- [ ] state.rounds 为空 → 错误退出
- [ ] `--auto-conclude` + A 型连续 3 轮 → `recommended_conclusion: "restructure"`
- [ ] `--auto-conclude` + D 型偏差 → `recommended_conclusion: "upgrade-forum"`
- [ ] `--force` + round > nmax → 仍然输出 `trigger: true`

---

### 4.3 `handoff_report.py` — 移交报告生成器

**优先级**：P1  **预计行数**：≤200

#### 4.3.1 用途

当任务不收敛、超 Nmax、或触发向人移交闸时，汇总当前最佳结果和待决策项。Skill 文档第 8 节"向人移交闸"的机械实现。

#### 4.3.2 接口

```text
handoff_report.py
    --state <cybersyn_state.json>
    [--output <report.md>]       # 输出文件（默认 stdout）
    [--format json|markdown]     # 默认 markdown
    [--extra '<JSON>']           # 额外注入信息：产物位置、用户备注等
```

#### 4.3.3 报告内容结构（Markdown）

```markdown
# 移交报告 — [任务名]

**生成时间：** 2026-07-01 10:30
**状态：** 未收敛，已超 Nmax (5/5)
**复杂度：** L3

---

## 当前最佳产物

[由 Agent 通过 --extra 参数注入产物位置/描述]

- 产物：[路径或描述]
- 最终偏差：e_missing=1, e_extra=0, e_wrong=0
- 最终能量：E=2.0

## 未通过的验收项

| ID | 描述 | 严重度 | 偏差类型 | 持续轮次 |
|----|------|--------|----------|---------|
| R3 | 刷新 token 端点测试 | high | A | 5 |

## 偏差历史摘要

| 轮次 | 类型 | e_missing | e_wrong | e_extra | 判决 |
|------|------|-----------|---------|---------|------|
| 1 | A | 0 | 2 | 1 | continuing |
| 2 | A | 1 | 0 | 0 | continuing |
| 3 | A | 1 | 0 | 0 | continuing |
| 4 | A | 1 | 0 | 0 | continuing |
| 5 | A | 1 | 0 | 0 | handoff (Nmax) |

## 死区

| ID | 描述 | 状态 |
|----|------|------|
| DZ1 | 第三方 OAuth 回调时序依赖外部服务 | open → 建议人工验证 |

## 结构性问题

- 连续 5 轮出现类型 A 偏差（token 刷新逻辑）→ 不是调参能解决的

## 环境信号

- 无环境变化

## 二阶审计历史

- 第 3 轮：maintain（r(t) 成立，偏差为参数误差）

## 建议下一步

1. **[用户决策]** R3 验收项属于声明的死区，是否接受当前产物或调整验收标准？
2. **[继续修改]** 若不接受，需先搭建 OAuth mock 服务（补能力缺口）
3. **[重设目标]** 若 OAuth 测试超出当前阶段范围，将 R3 移入下一阶段 r(t)
4. **[研讨厅]** 偏差持续 5 轮且出现结构性问题，可考虑升级研讨厅

## 待用户回答

- R3 是必须本阶段完成，还是可推迟到下一阶段？
- 是否需要协助搭建 OAuth mock？
```

#### 4.3.4 `--extra` 注入字段

Agent 可通过 `--extra` 注入以下可选字段（JSON）：

```json
{
  "artifact_location": "src/auth/refactored/",
  "artifact_description": "重构后的 auth 模块（token service 已提取）",
  "user_notes": "用户在第 3 轮时确认接受 R1/R2 的当前状态",
  "pending_decisions": ["是否接受 R3 的 dead zone 状态"]
}
```

#### 4.3.5 核心函数清单

```python
# ---- 数据提取 ----
def collect_unmet(state: dict) -> list[dict]
    """从最后一轮 feedback 中提取未解决的 e(t) 项。"""

def summarize_history(state: dict) -> list[dict]
    """轮次级别摘要表。"""

def detect_structural_patterns(state: dict) -> list[str]
def collect_dead_zones(state: dict) -> list[dict]
def collect_env_signals(state: dict) -> list[dict]
def collect_audit_history(state: dict) -> list[dict]

# ---- 建议生成 ----
def generate_next_steps(state: dict) -> list[str]
    """根据偏差类型、死区、Nmax、结构性问题生成建议下一步。"""

def generate_pending_questions(state: dict) -> list[str]
    """生成需要用户回答的问题。"""

# ---- 输出 ----
def render_markdown(state: dict, extra: dict) -> str
def render_json(state: dict, extra: dict) -> dict
```

#### 4.3.6 验证标准

- [ ] Nmax 超限 → 报告标题含"已超 Nmax"
- [ ] 存在死区 → 建议下一步含"用户决策"
- [ ] 连续同类偏差 → 结构性问题区域含相应警告
- [ ] `--format json` → 输出合法 JSON，可被其他工具解析
- [ ] `--extra` 注入 → 报告中出现注入的 artifact 信息
- [ ] 状态文件无 rounds → 报告标注"无迭代数据"

---

## 5. Phase 3 工具规范

---

### 5.1 `complexity_classify.py` — 复杂度分类器（含 enforce 模式）

**优先级**：P2  **预计行数**：≤250

#### 5.1.1 用途

根据任务描述和上下文辅助判定 L1-L4，并生成可被 `cybersyn_state.py init --enforce-from` 读取的强制执行约束。

#### 5.1.2 接口

```text
complexity_classify.py
    --task "<描述>"
    [--files <file1,file2,...>]         # 逗号分隔
    [--dependencies <dep1,dep2,...>]    # 逗号分隔
    [--enforce]                          # ★新增：输出 _enforce 配置（供 init 读取）
    [--format json|text]
```

#### 5.1.3 判定规则

```python
def classify(task: str, files: list[str], dependencies: list[str]) -> dict:
    """
    判定因子（按权重降序）：

    1. 环境波动性（最高权重）：
       - 检测关键词：持续变化、不确定、探索、创业、政策、策略方向、是否应该
       - 命中 → L4 倾向

    2. 异构度：
       - dependencies 中的模块是否属于不同层级/语言/子系统
       - ≥2 不同层级 → L3 倾向

    3. 文件/模块数量：
       - ≤2 → L1 倾向
       - 3-5 → L2 倾向
       - ≥6 → L3 倾向

    4. 需求清晰度：
       - 扫描模糊词：优化、改进、合理的、适当的、尽可能、大概
       - 命中 ≥2 → 至少 L2

    5. 同质度：
       - files 是否属于同一类型（如全是 .test.ts、全是翻译）
       - 同质 + 大量 → L2 而非 L3

    综合判定：
    - 各项因子投票 + 权重，取最匹配的 L 值
    - confidence = 一致因子数 / 总因子数
    """
```

#### 5.1.4 `--enforce` 输出扩展

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
  "enforce": {
    "allow_audit": true,
    "allow_vsm": true,
    "allow_positive_feedback": false,
    "allow_handoff_report": true,
    "allow_forum": false,
    "minimal_path_only": false,
    "nmax": 5,
    "audit_every": 3
  },
  "recommended": {
    "path": "全流程 + 四分类 + 二阶审计",
    "nmax": 5,
    "audit_every": 3,
    "vsm": true,
    "positive_feedback": "off"
  },
  "warnings": [],
  "explanation": "5 个异构模块，存在跨模块依赖（auth→user, auth→cache），需求明确但集成复杂度高 → L3"
}
```

`enforce` 字段生成规则：与 `cybersyn_state.py init` 的默认参数表一致（见 3.1.3 节）。

#### 5.1.5 核心函数清单

```python
def count_files(task: str, explicit_files: list[str]) -> int
def detect_heterogeneity(files: list[str], deps: list[str]) -> bool
def assess_requirement_clarity(task: str) -> str    # clear | medium | vague
def detect_env_volatility(task: str) -> str          # stable | uncertain | volatile
def generate_enforce(level: str) -> dict             # ★新增
def classify(task: str, files: list[str], deps: list[str]) -> dict
def render_json(result: dict) -> str
def render_text(result: dict) -> str
```

#### 5.1.6 边缘情况

| 情况 | 行为 |
|------|------|
| 无文件列表 | 从 task 文本推断，confidence 降低 0.1 |
| 任务描述为空 | stderr 错误，exit code 2 |
| 各项指标矛盾（files 少但 deps 多） | 取最高 L 值，warnings 中记录矛盾 |
| L4 判定 | `explanation` 中明确标注"建议人工确认 L4 判定" |

#### 5.1.7 验证标准

- [ ] "修改单行 bug" → L1, confidence ≥ 0.8
- [ ] "重构 auth/user/cache 三个模块" → L3, confidence ≥ 0.7
- [ ] "批量重命名 50 个文件" → L2, heterogeneity=false
- [ ] "帮我规划创业方向" → L4, env_stability=volatile
- [ ] `--enforce` + L1 → `minimal_path_only: true, allow_audit: false`
- [ ] `--enforce` + L4 → `allow_forum: true, nmax: -1`

---

## 6. 实施顺序

```
Phase 1（本计划审批后立即开始）—— 6 个任务，预计 3-4 轮对话
├── [1] cybersyn_state.py           ← 所有工具的基础（含 migrate/query/archive/pause/lock）
├── [2] checklist_compare.py        ← 闭环核心：测试₁/反馈 阶段
├── [3] diversity_generator.py      ← ★新增：研讨厅多模型分歧生成
├── [4] 安全边界测试                ← 验证 enforce_safety_boundaries 和 LockHeldError
└── [5] 更新 Skill 文档             ← 在相应阶段引用工具

Phase 2 —— 4 个任务
├── [6] convergence_check.py        ← 含 gain/energy/periodic/drift/transient
├── [7] audit_trigger.py            ← 含 auto-conclude
├── [8] handoff_report.py           ← 含 paused 信息读取
└── [9] 集成测试                    ← 全链路：init→checklist_compare→convergence_check→
                                          audit_trigger→apply-audit→handoff_report

Phase 3 —— 2 个任务
├── [10] complexity_classify.py     ← 含 enforce 模式
└── [11] 端到端验证                 ← 用不同复杂度任务跑完整闭环，验证工具链
```

---

## 7. 与 Skill 文档的集成点

每个工具在 Skill 文档的闭环六阶段（第 2 节）中有明确调用位置。Skill 文档需在相应阶段增加"工具："标注。

| Skill 位置 | 阶段 | 调用工具 | 参数 |
|-----------|------|----------|------|
| 0 自检 | 复杂度判定 | `complexity_classify.py` | `--task` + `--files` + `--enforce` |
| 0→1 路由 | 初始化 | `cybersyn_state.py init` | `--level` + `--task` + `--enforce-from` |
| 1 计划 | 状态初始化 | `cybersyn_state.py init` | 同上（若 0 段已 init，此处 update） |
| 2 测试₁ | 测量 | `checklist_compare.py` | `--requirements` + `--actual` + `--mode` |
| 3 反馈 | 偏差分类 | `checklist_compare.py` 输出 + Agent 判定类型 |
| 4 修改 | 记录修改 | `cybersyn_state.py update --stage modify` | `--data` |
| 5 测试₂ | 再验证 | `convergence_check.py` | `--state` + `--energy` + `--drift` |
| 5 判决 | 审计触发 | `audit_trigger.py` | `--state` + `--auto-conclude` |
| 5 判决→审计 | 审计反馈 | `cybersyn_state.py apply-audit` | `--conclusion` |
| 5 移交 | 不收敛时 | `handoff_report.py` | `--state` + `--extra` |
| 5 研讨厅 | L4/不收敛 | `diversity_generator.py` | `--task` + `--context` + `--strategies 3` |
| 5 二阶 | 审计记录 | `cybersyn_state.py update --stage audit` | `--data` |
| 6 输出 | 归档 | `cybersyn_state.py summary` + `cybersyn_state.py archive` |
| 任何暂停 | HITL | `cybersyn_state.py pause / resume` |
| 跨会话 | 记忆检索 | `cybersyn_state.py query` |

---

## 8. 设计决策记录

1. **为什么 JSON 而非 YAML/TOML？** JSON 是 Python stdlib 原生支持，零依赖。状态文件约 10-30KB，可读性足够。

2. **为什么不在脚本内直接调用 LLM？** 判定（偏差类型、POSIWID 等）需要语义理解，由 Agent 执行；工具只做机械化操作（统计、比较、正则匹配、阈值判定）。

3. **为什么不改写现有 Skill 文档？** Skill 文档保持"操作协议"角色，工具是"仪表盘"。两者松耦合，工具失败不影响 Skill 手动执行。

4. **状态文件放在哪？** 由 Agent 在任务工作目录创建，路径通过环境变量 `CYBERSYN_STATE` 或默认 `./cybersyn_state.json`。

5. **为什么在状态文件中增加 `_enforce` 字段？** 复杂度自检后，不同层级需要不同的控制策略。L1 不需要审计、正反馈、移交报告；L4 需要研讨厅。将限制写在状态文件中而非由调用者自觉遵守，可以在工具层面强制执行正确的控制路径，防止误用。

6. **为什么 `diversity_generator.py` 不依赖 LLM？** 与设计决策 #2 一致。`diversity_generator` 只生成策略模板和框架性描述，具体的方案细节由调用它的 Agent 或人在生成模板的基础上填充。工具只保证"≥3 个不同结构"和"分歧矩阵"的形式正确性。

7. **为什么锁机制是协作式的而非强制式的？** 强制锁需要操作系统级别的 IPC，超出了 Python stdlib 的能力范围。协作式锁对于单 Agent 场景零开销，对于多 Agent 场景足以防止最常见的并发冲突。高可靠性多 Agent 协调应使用外部状态存储（如 Redis），属于未来扩展范围。

8. **为什么版本迁移函数放在代码内而非独立脚本？** 迁移逻辑与状态结构高度耦合，放在 `load_state()` 旁边可以确保每次读取状态文件时自动完成迁移，无需用户手动操作。外部迁移脚本容易因为版本失配而无法运行。

---

## 9. 全局验证标准

实施完成后，需通过以下端到端验证：

### 9.1 Phase 1 验证

```
1. cybersyn_state.py init --level L3 --task "test" → 生成合法 v2.0 JSON
2. cybersyn_state.py validate → 无报错
3. cybersyn_state.py update --stage plan --data '{...}' → 更新成功
4. checklist_compare.py --requirements '[{...}]' --actual '...' --mode text → 输出合法 JSON
5. diversity_generator.py --task "test" --strategies 3 → 3 个不同视角的策略
6. cybersyn_state.py pause --reason "test" --options "A,B"
7. cybersyn_state.py resume
8. cybersyn_state.py migrate → v1.0 文件正确转为 v2.0
```

### 9.2 Phase 2 验证

```
1. convergence_check.py --state state.json --energy --drift → 合法 JSON，含所有扩展字段
2. audit_trigger.py --state state.json --auto-conclude → 合法 JSON，含推荐结论
3. handoff_report.py --state state.json --format markdown → 人类可读报告
4. cybersyn_state.py apply-audit --conclusion restructure → nmax+2, audit_every-1
5. cybersyn_state.py archive → archive.ndjson 追加一行
6. cybersyn_state.py query --pattern "type-A" → 合法搜索结果
```

### 9.3 Phase 3 验证

```
1. complexity_classify.py --task "单行bug" → L1, confidence ≥ 0.8
2. complexity_classify.py --task "多模块重构" --files a,b,c --dependencies x,y → L3
3. complexity_classify.py --enforce → enforce 字段符合 level 默认值
4. 全链路：complexity_classify → init --enforce-from → checklist_compare →
   convergence_check → audit_trigger → apply-audit → handoff_report
```

---

> **本文档覆盖**：原 `TOOLING_PLAN.md` 全部 7 个工具规范 + `修订意见` 全部 14 项缺口（P0-1/2/3, P1-1/2/3/4, P2-1/2/3/4/5/6/7/8）+ 4 项文本修订（T1-T5 接口扩展）+ 新增工具规范（NEW-1）+ 状态文件格式修订 + 设计决策补充。
>
> **总计**：7 个工具（含 1 个新增），3 个实施 Phase，11 个实施任务，9 条设计决策，全链路集成点表。
