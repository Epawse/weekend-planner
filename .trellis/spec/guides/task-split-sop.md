# 任务拆分判据（思考清单）

> guides 类：建任务前想什么。执行层规则见 [git-pr-sop](./git-pr-sop.md) 的「Task↔MR 映射」。

## 第一问：要不要 parent？

建 parent **当且仅当**同时满足：
- 一个需求拆出 **≥2 个独立可验收**的交付物（各自能 plan → implement → check → archive）；
- 存在**跨子验收**或统一收口需求（集成 review / 跨子铁律）。

否则单 task。parent 默认不承载实现，例外是它自己的直接工作（如集成收尾）。施工顺序写进 child 的 prd/implement——**树不是依赖系统**。
实例：test-bundle-data-suite（3 child + 跨子验收 4 条 + 集成收口）✔；L1 dev 环境（单一交付单元）✘ 不建 parent。

## 第二问：task 切多大？

- 一个 task = **一个可独立验收、可独立回滚的交付单元**；验收面super过 ~3 个互不相关的领域 → 拆。
- 拆分动机必须是**风险隔离或可验收性**（如 Library.jsx 只动一次、后端先行积累数据），不是"显得整齐"。
- 轻量（PRD-only）vs 复杂（三件套）按 triage；批量建 child 注意指针问题（[[trellis-mod-candidates]] M1/M2，未修复前按执行顺序倒序创建或 start 时自校正）。

## 第三问：映射到几个 MR？

默认 **1 task : 1 MR**。偏离必须命中 git-pr-sop 的成文情形（双轨 1:2 / stacked 集成 N:1 / 搭车 0:1），并在任务 implement.md 记录决策。
