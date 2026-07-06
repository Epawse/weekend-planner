---
name: trellis-friction
description: "Capture one workflow-friction entry the moment it happens — the user corrects the process ('为什么不走X', '说过多少遍要Y'), or the agent hits a rule vacuum / rule tension / awkward-flow moment. Capture ONLY: append one structured entry to the friction ledger, then continue the task. Never modify the workflow from here."
---
# Trellis Friction Ledger（捕获端）

铁律：**捕获 ≠ 修改 ≠ 仲裁**。当场一条入账，继续手头任务；不改 workflow、不立新规、不打断用户等裁决。

## 触发（两类）

1. **user-correction（最高价值信号，必须记）**：用户纠偏流程的时刻——"为什么不走 X""说过多少遍要 Y""这里不该问我"。标 `source: user-correction`。
2. **agent-friction（自记）**：撞到规则真空、规则间张力、流程明显过重/别扭的时刻。标 `source: agent`。

不记的：单纯的 bug、代码问题、一次性误会——那些走正常修复/澄清，不是工作流摩擦。

## 记录（append 一条到台账，文件缺失则创建）

台账路径：dev 布局 `.trellis/workspace/<dev>/friction.md`（`<dev>` 读 `.trellis/.developer`，缺省 `default`）；research 布局（无 workspace 目录时）`.trellis/friction.md`。

格式（一条一块，保持短——超过五行说明你在写分析而不是入账）：

```markdown
## [YYYY-MM-DD] <source: user-correction|agent> <一句话现象>
- 预期 vs 实际：<一行>
- 指针：<task 目录 / 会话 id / PR 号>
- 初诊猜测：A(纪律在但未被守/表达被压缩) | B(规则真空或张力) | C(流程过重)
```

初诊只是猜测，真正分诊在清账时做——记录时不确定就写两个候选。

## 分诊与立法（不在此发生）

- dev 家族：`trellis-review-sweep` 段 2 清账——A 类改执法/表达（**驳回立法**，防规则熵），B 类判例成文，C 类进减法候选；立法一律走 marketplace/my-trellis PR + 出生证 + `update --profile` 分发，**绝不在项目会话现场改 workflow.md**（破坏单源且逃过评审）。
- research 家族：review-sweep 双族化之前，由 workspace/meta 会话按同规则清账（backlog P0 挂账项）。

种子：第 0 号条目见 vault 复盘笔记 2026-07-06（ai-console 3995ac8b huashu 判例——一半 A 类沟通压缩不该立法、一半 B 类契约覆盖度真空，正好示范分诊两端）。
