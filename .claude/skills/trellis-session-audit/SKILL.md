---
name: trellis-session-audit
description: "Use when the user asks to review, audit, or analyze a past Claude Code or Codex session (检查/审阅/审计/复盘某次对话记录, often by session id) — locates the transcript, runs the bundled parser for a mechanical digest, verifies the session's claims against real repo/PR state, and delivers a structured audit report whose findings become a fix list."
---

# Session Audit（会话审计）

审计一场已结束的 agent 会话：它声称做了什么、实际做成了什么、用户在哪里纠偏、
踩了什么坑、留下了什么。**审计产出 = 修复清单**——发现的缺口要落成可执行项
（PR / BACKLOG / memory），不是读后感。

## 适用边界

- ✅ 用户点名 session id（CC 或 Codex）要求检查/复盘/总结经验
- ✅ 长自主会话收尾后的例行验收（如新工作流的实弹验证轮）
- ❌ 只想找回某段历史讨论的内容 → 走 `trellis-session-insight`（trellis mem）
- ❌ 审当前会话自己 → 直接自查，无需本 skill

## 流程

### 1. 定位 transcript

- Claude Code：`~/.claude/projects/<munged-cwd>/<session-id>.jsonl`；同名目录下
  `subagents/*.jsonl` 是子代理记录。
- Codex：`~/.codex/sessions/YYYY/MM/DD/rollout-*-<session-id>.jsonl`；子代理是
  同树下以 agent id 命名的独立 rollout（digest 的 Subagents spawned 节给出路径）。
- 解析脚本接受路径、完整 id 或 id 前缀，会自动全局搜索。

### 2. 先 digest，后深读

```bash
python3 scripts/parse_transcript.py <session-id> > /tmp/digest-<id>.md
```

digest 含：元信息（时长/模型/权限/compact/resume/子代理数）、**用户消息全文**
（最高信号源，必须全部读完；harness 注入与子代理通知已剥离）、子代理清单与
结果节、助手文本（默认截断）、工具统计、git/gh 关键调用、错误与拦截事件。**不要整段回灌原始 transcript**——既省 token，也避免被审会话
里的安全相邻措辞触发分类器误拦（若审计中真被硬拦：换用摘要转述、必要时切
Opus 继续）。只对 digest 标记出的关键片段回原文深读。

### 3. 抽验声称（核心步骤）

对会话里的"已完成"声称逐项对照现实，**转述不算证据**：

- commit/PR：`git log` / `gh pr view` / `gh pr checks` 实查落没落、绿没绿
- 文件产物：声称写过的文件是否存在、内容是否与声称一致
- 被引用物：会话产出的文档若引用了昂贵产物（调研报告等），确认其已落库而非
  只活在对话里
- 单点发现要全局搜同类（一个日期口误往往是系统性口误）

### 4. 多会话 / 大文件 fan-out

单文件 >2MB 或一次审多个会话时：一会话一个子代理，主会话只做裁决与综合。
子代理任务书要点：跑解析脚本 → 读完用户消息全文 → 按下方模板出报告；
声明"你的最终消息是给 orchestrator 的原始数据"。

### 5. 报告（八段模板）

1. 会话元信息（起止/时长/模型与切换/permission/规模/compact）
2. 任务背景与用户目标（引用原话）
3. 时间线 / 主要阶段
4. 关键决策与实际产出（文件、commit、PR——经抽验的）
5. 用户反馈与纠偏（打断/否决/重申偏好，逐条引原话——这是最高优先级信号）
6. 问题 / 错误 / 弯路及解决
7. 结束时状态：完成了什么、遗留什么（遗留项标明归属与触发条件）
8. 经验教训（面向"下次怎么做得更好"，可机制化的标出机制化建议）

### 6. 沉淀路由（写时维护）

- 缺口/坏账 → 当场修或开 PR / 记 BACKLOG（带触发条件）
- 工作方式教训 → 私有 memory（feedback 类，含 Why / How to apply）
- 可复用先例 → atlas / 项目 spec
- 只属于这次对话的细节 → 不沉淀

## 脚本参数

`--max-asst N` 调整助手文本截断（默认 500 字符）；`--full-asst` 不截断
（小会话可用）；`--timeline` 输出带时间差的锚点时间线（用户消息/子代理
spawn 与结果/git 关键调用/compact，直接重建各阶段与 gate 耗时）。
digest 体积约为原文件的 1.5–2%（7MB 会话 ≈ 110KB digest）。
