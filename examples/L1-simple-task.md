# 示例：L1 简单任务 — 修复单个函数的 bug

演示 SKILL.md 的 **L1 极简路径**：计划一句 → 改 → 对照验收项查 → 收敛即交付。

## 任务

> 用户："`login.py` 里的 `validate_email` 把带 `+` 号的邮箱判为非法了，修一下。"

## 第 0 步：复杂度自检

1 个文件、无跨模块依赖、需求明确 → **L1**。可用工具确认（可选）：

```bash
python tools/complexity_classify.py --task "fix email validation bug" --files login.py --format json
# → {"level": "L1", ...}
```

L1 走极简路径，SKILL.md 其余章节不适用；**不向用户展示闭环术语**（可见性规则）。

## 极简路径执行

**计划（一句）**：修正 `validate_email` 的正则，使 `user+tag@example.com` 合法；不破坏既有测试。

**改**：修改正则，将 `+` 加入本地部分允许字符。

**对照验收项查**：
- ✅ `user+tag@example.com` 通过
- ✅ 原有非法样例（`no-at-sign`、`a@b`）仍被拒绝
- ✅ `pytest tests/test_login.py` 全绿

**收敛即交付**。对用户的最终回答只需简短说明："已修复并按需求核对：带 + 号的邮箱现在合法，既有测试全部通过。"

## 要点

- L1 **不启用**状态文件、二阶审计、VSM、研讨厅 —— 流程开销为零。
- 若修改后发现牵连 3+ 个异构模块，立即回到第 0 步重判为 L3。
