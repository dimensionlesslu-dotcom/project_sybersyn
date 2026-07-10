# Contributing to Project Cybersyn

感谢你的兴趣！我们欢迎各种形式的贡献。

## 贡献方式

### 报告问题 (Bug Reports)

如果你发现 SKILL.md 中有逻辑错误、不清晰的地方，或在实践中遇到问题，请提交 Issue，包含：

1. 问题描述
2. 触发场景（什么任务触发了问题）
3. 你期望的行为 vs 实际发生的行为
4. 涉及的 L1-L4 层级

### 提出改进 (Feature Requests)

Project Cybersyn 仍在进化中。如果你有：

- 对控制流程的改进建议
- 新的偏差类型
- 更好的定性代理
- 新的应用场景

请提交 Issue，描述建议及其背后的理由。

### 提交代码 (Pull Requests)

1. Fork 本仓库
2. 创建一个分支：`git checkout -b feature/my-improvement`
3. 做出修改
4. 确保 `SKILL.md` 的 frontmatter 格式正确
5. 提交 PR，描述改了什什么、为什么

### 贡献工具脚本 (tools/)

如果你实现了 `TOOLING_PLAN.md` 中规划的某个工具：

- 遵循设计约束：Python 3 stdlib、≤200 行、单文件、argparse CLI
- 在 `tools/README.md` 中更新状态
- 附带简单的使用示例

## 风格指南

### SKILL.md 修改原则

1. **保持简洁**——每行都在争抢注意力，不添加纯学术性的内容。
2. **可操作性优先**——如果你添加了一个概念，它必须有对应的操作定义（AI 能怎么执行）。
3. **向后兼容**——修改偏差分类、验收门等核心机制时需格外谨慎。
4. **标注经验默认**——所有数值阈值（Nmax、m 等）必须标注"经验默认、可调"。

### 语言

- 核心文件 (SKILL.md, README.md) 使用中文为主 + 英文关键术语。
- 代码注释和工具文档可使用英文。

## 许可证

贡献的代码按 MIT License 授权，文档按 CC BY 4.0 授权。
