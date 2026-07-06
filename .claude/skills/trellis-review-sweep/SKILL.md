---
name: trellis-review-sweep
description: "Manually triggered maintenance sweep over the whole workflow: (1) batch deep-review of merged/archived tasks whose meta.verification.deep_review is pending — parallel read-only reviewers with no one waiting; (2) triage of BACKLOG trigger conditions, governance docs, and the memory layers; (3) mechanical hygiene scan (placeholder text, task metadata gaps, dead links). Use when the user asks to run a review sweep / 深度审查扫一轮 / 清欠审台账 / 工作流大盘点."
---

# Trellis Review Sweep（异步维护扫批）

同步 gate 只守机械门与首轮验证（最贵的是等待）；深度审查与工作流整理攒批到
这里异步执行。**手动触发**——用户说"跑一轮 sweep"才开工，不自动挂定时。

## 派发表（谁干什么）

| 段 | 执行者 | 档位 |
|---|---|---|
| 主控（裁决/综合/回写台账/治理写入） | 本会话（Claude 主控） | high |
| 段 1 deep-review reviewer | `codex exec --sandbox read-only` 异构审（GPT-5.5）；无 codex CLI 时退 CC 只读子代理 | high（GPT-5.5；升档见下）／CC 退档 xhigh |
| 段 2 triage | 主控 inline（跨文档对照，不拆） | （随主控） |
| 段 3 hygiene | 主控跑捆绑脚本 | — |

为什么这样分：欠审存量多为 Claude 产出，异构 reviewer（GPT-5.5）不共享盲区，
且 read-only sandbox 是机制级只读；治理文档与 memory 的裁决写入是主控分工，
不下放。

段 1 reviewer 默认 `high`（2026-07-06 用户拍板：GPT-5.5 high 档实测质量已足，
xhigh 省一档时延/成本）；升 `xhigh` 仅两类触发——安全相邻审计、或 high 档一次
未打穿的硬结复审。无 codex CLI 退 CC 只读子代理时仍走 `xhigh`（Claude 子代理档位
标准不变）；science 侧 zh-research 的 GPT-5.5 xhigh 不受本条影响。

## 段 1：Deep review（清 deep_review 台账）

1. 收集 pending：

```bash
grep -rl '"deep_review": "pending"' .trellis/tasks/*/task.json .trellis/tasks/archive/*/*/task.json 2>/dev/null
```

一轮上限 10 个，超出下轮再扫（报告里说明截断，不静默）。对每个命中读
task.json 拿 `title` / `branch` / `pr_url` / `commit`。

2. 并行派只读 reviewer，首选 codex 异构审：

```bash
codex exec --skip-git-repo-check --cd <repo-root> --sandbox read-only --ephemeral \
  --output-last-message /tmp/sweep-<slug>.md - <<'EOF'
Active task: <task path>
你是异步深审 reviewer（只读）。同步 gate 已跑过 lint/type/tests，不要重跑。
证据入口：task 目录 prd.md / design.md / implement.md + task.json 的
branch/pr_url → git log / diff 实查落地代码；不许只读文档下结论。
Review focus：设计级缺陷、跨层一致性、遗漏的回归面、该沉淀而未沉淀的 spec 教训。
输出：Verdict（CLEAN / FINDINGS）+ 逐条 findings（文件:行 + 危害 + 建议）。
EOF
```

无 codex CLI 时：CC 只读子代理（Read/Bash/Glob/Grep），同一任务书。

3. 主控裁决每份报告：真发现→当场小修开 fix PR，量大→记 BACKLOG（带触发条件）；
   无发现/已处置→`task.py set-deep-review <dir> done`（盖 done@date）；
   纯 chore/记账类不值得深审→`set-deep-review <dir> waived` + task.json notes 写一句理由。

## 段 2：Triage（BACKLOG + 治理文档 + memory，主控 inline）

**BACKLOG**：逐条核对触发条件是否已到期。到期项列清单给用户拍板——
不自动动工（触发未到不预支，到了也只是"可以做了"不是"必须现在做"）。

**治理文档**（PROJECT-MEMORY / 项目等价物）：已完成未划账的条目补划账
（~~划线~~ + 完成指针）；条目里挂的"复审触发"到期的并入上面的拍板清单。

**friction 台账清账**（`.trellis/workspace/<dev>/friction.md`，捕获端见
`trellis-friction`）：逐条分诊——**A 类**（纪律在但未被守/表达被压缩）→
改执法或表达（hook/注入/措辞），**驳回立法**并在条目标注驳回理由（防规
则熵——约三成摩擦属此类，不记录就无法证明"不需要新规则"）；**B 类**
（规则真空/张力）→ 判例成文候选，列给用户拍板后走 marketplace/my-trellis
PR + 出生证；**C 类**（流程过重）→ 进减法轮候选清单。清账后条目标
`triaged@date + 去向`，不删除（台账即历史）。

**memory 分层处理**（按共享记忆协议的层归属，只动本 agent 有权动的层）：

| 层 | 检查 | 动作权限 |
|---|---|---|
| 仓内 `workspace/<dev>/memory.md` | 指向的文件/机制已不存在、被后续决策取代、重复可合并 | 直接修 |
| 治理文档（PROJECT-MEMORY 类） | 同上 + 划账 | 直接修；删除性改动列清单给用户过目 |
| 本 agent 私有 memory | 引用失效、与仓内重复（降级为指针）、过时事实 | 直接修（本就是自己的记忆规则） |
| 其他 agent 私有记忆（如 Codex） | 同上 | 只出报告，贴给对方下次会话自清 |
| `trellis mem`（对话历史） | 不检查——只读归档，无"过时"概念 | — |

## 段 3：Hygiene（机械扫描，跑脚本）

```bash
python3 scripts/sweep_hygiene.py            # 在项目根跑；本 skill 目录下的捆绑脚本
```

覆盖：占位文本（`(Add details)` / `（由团队填写）` / 仅剩 `_example` 行的
jsonl）、非 planning 任务的 strategy 元数据缺口、spec/memory/治理文档里的
仓内死链、deep_review 台账存量统计。输出报告不改文件——修复由主控裁决后动手。

## 收尾

输出一张总表：段 1 任务 × 结论（done/waived/finding→去向）、段 2 到期项与
memory 修订数、段 3 WARN 计数与去向、欠审存量剩余。全程零发现也要说——
连续两轮三段全零发现时，提醒用户触发本 skill 的减法复审（见出生证）。

## Guardrails

- Reviewer 只读；一切修复走主会话或正常 implement/check 路径。
- 不重扫 `done@*` / `waived`；台账即幂等性。
- sweep 产出的 fix 照常走 PR + 同步机械门，不因"来自 sweep"而豁免。
- 段 2 的删除性改动（删条目/删记忆）一律先列清单，用户过目后执行。
