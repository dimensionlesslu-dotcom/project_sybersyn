# 示例：L3 复杂巨任务 — 重构三个互相依赖的模块

演示 SKILL.md 的 **L3 全流程**：闭环六阶段 + 偏差四分类 + 二阶审计 + 交付验收门，以及如何用 `tools/` 把状态持久化到 `cybersyn_state.json`。

## 任务

> 用户："把 `auth`、`session`、`user` 三个模块解耦，`auth` 不再直接读 `user` 表；不能破坏现有 API。"

## 第 0 步：复杂度自检 → 初始化状态

3 个异构模块互有依赖 → **L3**（Nmax=5，每 3 轮二阶审计）。

```powershell
python tools/complexity_classify.py --task "decouple auth/session/user" --files auth.py,session.py,user.py --dependencies "auth,session,user" --format json
# → {"level": "L3", ...}

python tools/cybersyn_state.py init --level L3 --task "decouple auth/session/user" --requirements "@examples/requirements.json"
```

**计划**（写入 r(t)）：验收清单 = ①`auth` 不 import `user` 内部表结构 ②既有 API 测试全绿 ③无循环依赖。核心假设 = "session 层可以充当 auth↔user 的中介"。风险应对 = 每步跑集成测试；死区 = 无。

## 第 1 轮

```bash
python tools/cybersyn_state.py next-round
```

- **测试₁**：引入 `UserGateway` 接口，跑测试，只记录输出。
- **反馈**：3 个集成测试失败（session 过期逻辑仍直接查 user 表）→ 缺失 1 项、错误 2 项，方向正确 → **类型 A**。

```bash
python tools/cybersyn_state.py update --stage feedback --data "@examples/feedback.json"
```

- **修改**：路径 A，k=局部重写（session 过期逻辑走 gateway）。
- **测试₂**：e₂ < e₁，判决"继续"。

## 第 2 轮

```bash
python tools/cybersyn_state.py next-round
python tools/cybersyn_state.py update --stage feedback --data "@examples/feedback-converged.json"
python tools/convergence_check.py --state cybersyn_state.json --format json
```

假设本轮各模块单测全过、但集成后出现新的偶发失败 → 各模块独立都过、集成异常 = **类型 D（涌现）**。按四分类规则：**退出一阶回路，不当 A 修**，回定性假设层检查交互假设。

## 第 3 轮 → 二阶审计触发

```bash
python tools/audit_trigger.py --state cybersyn_state.json --auto-conclude --format json
# → {"trigger": true, "recommended_conclusion": "restructure", ...}
python tools/cybersyn_state.py apply-audit --conclusion restructure
```

审计发现核心假设仍成立，但 gateway 的事件顺序设计有结构性问题 → 改结构（引入显式事务边界），而非继续调参。

## 收敛与交付验收门

第 4 轮后连续两轮无新实质问题：

```bash
python tools/convergence_check.py --state cybersyn_state.json --format json
# 只有真实返回 status=converged 且 delivery_allowed=true 才进入交付
```

## 若不收敛：向人移交

超 Nmax 或落入死区时，生成移交报告而不是硬扛：

```bash
python tools/handoff_report.py --state cybersyn_state.json --output handoff.md
python tools/cybersyn_state.py pause --reason "Nmax reached" --options "接受当前产物,扩展 nmax,重设目标"
```

## 要点

- **D 不能当 A 修**：第 2 轮如果继续调参，只会把涌现问题越修越深。
- 状态文件让多轮迭代跨会话可恢复，`summary` 子命令随时给出人类可读概览。
- L3 按可见性规则只向用户展示关键决策点（复杂度判定、主要偏差类型、审计触发、验收结果）。
