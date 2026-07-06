# Development Workflow

---

## Core Principles

1. **Plan before code** — figure out what to do before you start
2. **Specs injected, not remembered** — guidelines are injected via hook/skill, not recalled from memory
3. **Persist everything** — research, decisions, and lessons all go to files; conversations get compacted, files don't. Commitments included（禁对话态承诺，研究族 backlog 铁律反向收割）：只活在对话里的规划/判定/待办清单不算交付——收尾前落进 task 产物 / BACKLOG / spec，或显式声明未落盘。
4. **Incremental development** — one task at a time. Big plans stay as a parent task map; task dirs are materialized only at pickup (`task.py start` enforces this: one in_progress task, at most 2 parked planning tasks; break-glass `TRELLIS_ALLOW_PARALLEL=1`). 与 BACKLOG 同一原则：触发未到不预支。
5. **Capture learnings** — after each task, review and write new knowledge back to spec
6. **Language convention** — 给人看的产物中文优先：README、PRD/design/implement、PR 描述（Summary 必须中文书写，CI 强制）、评审 findings、memory、spec、BACKLOG。代码、注释、commit、分支名、CLI/API 名、AGENTS 与 skills 文档保持英文。
7. **Verdict independence（verdict 与 author 异源）** — verdict-bearing 评审必须独立上下文（独立 reviewer dispatch / fresh thread，绝不让 author 顺手自审），并尽量异源（Codex 独立第二视角、跨模型审稿）；同源时靠独立上下文 + 评审 agent 的独立协议兜底。成本护栏：异源/fresh 回炉只花在 verdict-bearing gate 上，廉价机械检查走 delta 复验，不以"独立性"为名膨胀验证成本。

---

## Trellis System

### Developer Identity

On first use, initialize your identity:

```bash
python3 ./.trellis/scripts/init_developer.py <your-name>
```

Creates `.trellis/.developer` (gitignored) + `.trellis/workspace/<your-name>/`.

### Spec System

`.trellis/spec/` holds coding guidelines organized by package and layer.

- `.trellis/spec/<package>/<layer>/index.md` — entry point with **Pre-Development Checklist** + **Quality Check**. Actual guidelines live in the `.md` files it points to.
- `.trellis/spec/guides/index.md` — cross-package thinking guides.

```bash
python3 ./.trellis/scripts/get_context.py --mode packages   # list packages / layers
```

**When to update spec**: new pattern/convention found · bug-fix prevention to codify · new technical decision.

### Task System

Every task has its own directory under `.trellis/tasks/{MM-DD-name}/` holding `task.json`, `prd.md`, optional `design.md`, optional `implement.md`, optional `research/`, and context manifests (`implement.jsonl`, `check.jsonl`) for sub-agent-capable platforms.

```bash
python3 ./.trellis/scripts/task.py --help    # authoritative, up-to-date command list
```

Core lifecycle: `create` (dir + `task.json`, status=`planning`, auto-targets the session's active-task pointer) → `start` (planning→`in_progress`, planning gate enforced) → `archive` (→`completed`, moves to `archive/{year-month}/`). Context manifests are managed with `add-context` / `list-context` / `validate`; metadata with `set-branch` / `set-base-branch` / `set-strategy` / `set-deep-review`（异步深审台账：`pending` → `done@date`/`waived`，由手动触发的 `trellis-review-sweep` 批量清账——机械门永远同步必过，深度审查不再挡同步路）. Session pointers live under `.trellis/.runtime/sessions/`; if `start` fails with a session-identity hint, follow it and retry.

### Workspace System

Records every AI session for cross-session tracking under `.trellis/workspace/<developer>/`.

- `index.md` — personal index: **one-line session history** (# / Date / Title / Commits / Branch) plus counters. Journal files are retired (2026-07-05) — legacy `journal-N.md` stay on disk as read-only history; durable narrative belongs in PR descriptions and task archives.
- `memory.md` — cross-platform project memory (SessionStart-injected; see the layering rules in AGENTS.md).

Workspace scope: session records + personal memory ONLY. It is not knowledge storage — the index is session→commit one-liners, deep archaeology is `trellis mem`, and **cross-task research/analysis lands in `docs/research/<topic>.md`**, never in `workspace/<dev>/research/`.

```bash
python3 ./.trellis/scripts/add_session.py --title "Title" --commit "hash"
```

### Context Script

```bash
python3 ./.trellis/scripts/get_context.py                            # full session runtime
python3 ./.trellis/scripts/get_context.py --mode packages            # available packages + spec layers
python3 ./.trellis/scripts/get_context.py --mode phase --step <X.Y>  # detailed guide for a workflow step
```

---

<!--
  WORKFLOW-STATE BREADCRUMB CONTRACT (read this before editing the tag blocks below)

  The [workflow-state:STATUS] blocks embedded in the ## Phase Index section
  below are the SINGLE source of truth for the per-turn `<workflow-state>`
  breadcrumb that every supported AI platform's UserPromptSubmit hook
  reads. inject-workflow-state.py (Python platforms) and
  inject-workflow-state.js (OpenCode plugin) only parse them — there is no
  fallback dict baked into the scripts after v0.5.0-rc.0.

  STATUS charset: [A-Za-z0-9_-]+. When the hook can't find a tag, it
  degrades to a generic "Refer to workflow.md for current step." line —
  intentionally visible so users notice and fix a broken workflow.md.

  INVARIANT:
    The breadcrumb is a minimal per-turn guardrail, not the full workflow.
    It must keep hard gates reachable (task creation consent, reviewed
    planning before `task.py start`, context loading before edits, checking,
    spec update, commit, and goal-dependent finish/ship choice), while the
    detailed procedure stays in the phase walkthroughs and skills.
    Every workflow step marked `[required · once]` must remain represented
    by either a breadcrumb guardrail or a phase walkthrough gate.

  TAG ↔ PHASE scoping:
    [workflow-state:no_task]      → no active task; before Phase 1
    [workflow-state:planning]     → all of Phase 1 (status='planning')
    [workflow-state:planning-inline] → Codex inline variant of Phase 1
    [workflow-state:in_progress]  → Phase 2 + Phase 3.1-3.4
                                    (status stays 'in_progress' from
                                    task.py start until task.py archive)
    [workflow-state:in_progress-inline] → Codex inline variant of Phase 2/3
    [workflow-state:completed]    → currently DEAD: cmd_archive flips
                                    status and moves the dir in the same
                                    call, so the resolver loses the
                                    pointer (block kept for a future
                                    explicit in_progress→completed
                                    transition)

  Editing checklist:
    - When you change a [workflow-state:STATUS] block, also check the
      matching phase's `[required · once]` walkthrough steps for sync
    - Run `trellis update` after editing to push the new bodies to
      downstream user projects (block-level managed replacement)
    - Full runtime contract:
      .trellis/spec/cli/backend/workflow-state-contract.md
-->

## Phase Index

```
Phase 1: Plan    → classify, get task-creation consent, then write planning artifacts
Phase 2: Execute → implement only after task status is in_progress
Phase 3: Finish  → verify, update spec, commit, and wrap up
```

### Request Triage

- Simple conversation or small task: ask only whether this turn should create a Trellis task. If the user says no, skip Trellis for this session.
- Complex task: ask whether you may create a Trellis task and enter planning. If the user says no, do not do broad inline implementation; explain, clarify scope, or suggest a smaller split.
- User approval to create a task is not approval to start implementation. Planning still happens first.
- Greenfield UI（新项目或换设计语言级的方向变更）：planning 之前先过 `trellis-prototype` 原型门——≥3 个分歧风格原型 → 用户冻结一稿（`prototypes/DECISION.md`）→ 冻结稿作为 PRD/design 的设计输入。纯后端或设计体系内增量改动不适用。

### Model / Effort Routing（开局装载，形态切换时调整）

按任务形态选主控模型与推理档位，而非固定一档跑全场：

- **规划 / 设计 / 策展 / 审计** → Fable 5 + `high`。升 `xhigh` 的触发器：跨文件矛盾排查、深度 debug、架构验证类硬结（或主控保持 `high`，把硬结派给 `xhigh` 验证子代理）。`max` 仅当评测证明 `xhigh` 仍有余量。
- **git / 安全相邻的长跑执行**（大扫除、批量修复、安全审计）→ Opus 4.8 + `xhigh` 起手。Fable 分类器在此形态高频误拦，拦截自动回退 Opus 还照扣 Fable 额度——直接 Opus 起手。审计含安全措辞的材料时摘要化读取，勿整段回灌；被硬拦不要反复"继续"，切模型再试。
- **scope 清晰的机械脏活 / 独立第二视角** → Codex（GPT-5.5），默认 `high`（2026-07-06 用户拍板：high 档实测质量已足）；升 `xhigh` 仅限两类触发：安全相邻审计、或 high 档一次未打穿的硬结复审。执行力强但欠约束时抄最快路径——只在 gates/hooks 齐备的仓里放行（supersede 07-05 marketplace #18 立节时的"日常 high／复杂 xhigh"分档；science 侧 zh-research 的 GPT-5.5 xhigh 不受本条影响）。
- **前端 / UI / 视觉类任务（硬规则，2026-07-05 用户拍板）**：一律 Claude 系（Fable 5，长跑或安全相邻退 Opus 4.8）执行，**禁派 GPT-5.5**——实测其前端产出质量差且无 taste。Codex 在前端仓的合法角色仅剩纯逻辑层机械修改与只读 review；凡触 UI/样式/交互/视觉一律 Claude。
- **派发即选型（硬规则）**：优先 typed dispatch——agent 类型定义里已钉模型（`trellis-research` = Sonnet 侦查档；implement/check/review gates 各有 pinned），选对类型 = 选对模型，无需查表。untyped 或 pinless 类型（`claude`/`general-purpose`——类型不带模型钉扎）派发必须显式带 `model`：bounded 机械子任务（侦查、测试、样板、格式化）绑 `sonnet` + effort **`xhigh`**，重活/长程子代理绑 `opus` + effort **`xhigh`**（2026-07-06 用户拍板：sonnet/opus 的 xhigh 档是子代理最优，往下档位质量塌陷——supersede 旧 medium/low 降档条款）。`dispatch-guard` hook 在派发时刻执法：unrouted 派发（无类型且无显式 model）注入提醒，120s 内第 3 次直接 deny——三代理同时继承主控档撞死配额（2026-07-05）的疫苗。
- **review gate 档位**：同步 gate 的 reviewer 一律 `xhigh`（2026-07-06 用户拍板 supersede 07-05"high 不降质"数据点——opus reviewer 的 xhigh 才是质量档）；异步 `trellis-review-sweep` 同 `xhigh`。
- 本节模型名与档位基于 2026-07 实测与官方口径；新一代 SOTA 模型上线时按出生证/减法审计规则复审本节，勿让过时限制拖住强模型。

### Planning Artifacts

- `prd.md` — requirements, constraints, and acceptance criteria. Do not put technical design or execution checklists here.
- `Development Strategy` — mandatory section in `prd.md` / planning docs before `task.py start`. It records execution mode, git mode, development mode, and explicit review-gate choices.
- `design.md` — technical design for complex tasks: boundaries, contracts, data flow, tradeoffs, compatibility, rollout / rollback shape.
- `implement.md` — execution plan for complex tasks: ordered checklist, validation commands, review gates, and rollback points.
- `implement.jsonl` / `check.jsonl` — spec and research manifests for sub-agent context. They do not replace `implement.md`.
- Lightweight tasks may be PRD-only. Complex tasks must have `prd.md`, `design.md`, and `implement.md` before `task.py start`.

### Parent / Child Task Trees

Use a parent task when one user request contains several independently verifiable deliverables. The parent task owns the source requirement set, the task map, cross-child acceptance criteria, and final integration review; it normally should not be the implementation target unless it also has direct work.

**Lazy materialization (hard rule).** The parent's task map is one line per future child, kept in the parent's `prd.md` / `implement.md` — NOT pre-created task directories. A child's directory is created only at pickup, and pickup runs the child's own compressed Phase 1 (PRD 补全 → strategy → gate) before its `task.py start`. Batch-creating fully-planned children up front is the known failure mode: the gate never sees tasks 2..N, their artifacts rot, and steps get skipped mid-batch. `task.py start` enforces the rail mechanically — one in_progress task at a time, at most 2 parked planning tasks (coordination parents with children are exempt); deliberate parallel runs use `TRELLIS_ALLOW_PARALLEL=1`, which records the exemption.

Use child tasks for deliverables that can be planned, implemented, checked, and archived independently. Parent/child structure is not a dependency system: if one child must wait for another, write that ordering in the child `prd.md` / `implement.md` and keep each child's acceptance criteria testable.

Create new children with `task.py create "<title>" --slug <name> --parent <parent-dir>`. Link existing tasks with `task.py add-subtask <parent> <child>`, and unlink mistakes with `task.py remove-subtask <parent> <child>`.

<!-- Per-turn breadcrumb: shown when there is no active task (before Phase 1) -->

[workflow-state:no_task]
No active Trellis task. For complex repo work, ask whether to create a task before planning or editing; for simple conversation, answer normally.
[/workflow-state:no_task]

### Phase 1: Plan
- 1.0 Create task `[required · once]` (only after task-creation consent)
- 1.1 Requirement exploration `[required · repeatable]` (`prd.md`; complex tasks also need `design.md` + `implement.md`)
- 1.2 Research `[optional · repeatable]`
- 1.3 Configure context `[conditional · once]` — Claude Code, Cursor, OpenCode, Codex, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae
- 1.4 Activate task `[required · once]` (review gate, then `task.py start`; status → in_progress)
- 1.5 Completion criteria

<!-- Per-turn breadcrumb: shown throughout Phase 1 (status='planning') -->

[workflow-state:planning]
Use `trellis-brainstorm` for requirement changes; stay in planning.
Do not implement until artifacts are reviewed and `task.py start` succeeds. Lightweight tasks may be PRD-only; complex tasks need `design.md` and `implement.md`.
Before start, run `task.py validate <task-dir>` and curate jsonl manifests only when sub-agents need extra spec/research context.
If Development Strategy sets development-mode=tdd: before start, record in `implement.md` the observable behavior slices, the public interface under test, and the mock boundaries.
[/workflow-state:planning]

<!-- Per-turn breadcrumb: shown throughout Phase 1 when codex.dispatch_mode=inline.
     Codex-only opt-in alternate to [workflow-state:planning]. The main agent
     edits code directly in Phase 2, so jsonl curation is skipped —
     the inline workflow loads `trellis-before-dev` instead of injecting JSONL
     into a sub-agent. -->

[workflow-state:planning-inline]
Use `trellis-brainstorm` for requirement changes; stay in planning.
Do not implement until artifacts are reviewed and `task.py start` succeeds. Lightweight tasks may be PRD-only; complex tasks need `design.md` and `implement.md`.
Inline mode skips jsonl curation; Phase 2 loads artifacts and specs through `trellis-before-dev`.
[/workflow-state:planning-inline]

### Phase 2: Execute
- 2.1 Implement `[required · repeatable]`
- 2.2 Quality check `[required · repeatable]`
- 2.3 Rollback `[on demand]`

<!-- Per-turn breadcrumb: shown while status='in_progress'.
     Scope: all of Phase 2 + Phase 3.1-3.4 (status stays 'in_progress' from
     task.py start until task.py archive; only archive flips it). Keep this
     block short: it should preserve the active-task guardrails while the
     detailed procedure stays in the phase walkthroughs and skills. -->

Sub-agent dispatch protocol applies to all platforms and all sub-agents, including class-2 Codex/Copilot/Gemini/Qoder/ZCode/Reasonix/Trae and `trellis-research`: every dispatch prompt starts with `Active task: <task path from task.py current>` before role-specific instructions.

[workflow-state:in_progress]
If this turn continues the active task, load context first: jsonl entries -> `prd.md` -> `design.md if present` -> `implement.md if present`.
Main session either dispatches implement/check sub-agents (spec context rides the dispatch), or implements inline — inline requires `trellis-before-dev` before the first edit (it is the only spec-injection path when not dispatching) and `trellis-check` before reporting done (spec/PRD compliance: passing tests alone is not it). Either path: `trellis-update-spec` if the task taught something, then commit. If this turn is unrelated, answer normally.
After commit, choose by user goal: local wrap-up/bookkeeping -> `/trellis:finish-work`; remote PR delivery -> `/trellis:ship` directly. Do not tell the user they must run finish-work before ship.
[/workflow-state:in_progress]

<!-- Per-turn breadcrumb: shown while status='in_progress' when
     codex.dispatch_mode=inline. Codex-only opt-in alternate to
     [workflow-state:in_progress]. The main session edits code directly
     instead of dispatching sub-agents. -->

[workflow-state:in_progress-inline]
If this turn continues the active task, use `trellis-before-dev` before edits and `trellis-check` after edits; do not dispatch implement/check sub-agents.
Read context: `prd.md` -> `design.md if present` -> `implement.md if present`, plus relevant spec/research loaded by skills. If this turn is unrelated, answer normally.
After commit, choose by user goal: local wrap-up/bookkeeping -> `/trellis:finish-work`; remote PR delivery -> `/trellis:ship` directly. Do not tell the user they must run finish-work before ship.
[/workflow-state:in_progress-inline]

### Phase 3: Finish
- 3.1 Quality verification `[required · repeatable]`
- 3.2 Debug retrospective `[on demand]`
- 3.3 Spec update `[required · once]`
- 3.4 Commit changes `[required · once]`
- 3.5 Wrap-up reminder

<!-- Per-turn breadcrumb: shown while status='completed'.
     Currently DEAD in normal flow: cmd_archive writes status='completed' in
     the same call that moves the task dir to archive/, so the active-task
     resolver loses the pointer and the hook never fires on archived tasks.
     Block preserved for a future status-transition redesign (e.g. an
     explicit in_progress→completed command). Edit through the same spec
     channel as the live blocks. -->

[workflow-state:completed]
Code committed. Next step is goal-dependent: local wrap-up/bookkeeping -> `/trellis:finish-work`; remote PR delivery -> `/trellis:ship` directly. If dirty, return to Phase 3.4 first.
[/workflow-state:completed]

### Rules

1. Identify which Phase you're in, then continue from the next step there
2. Run steps in order inside each Phase; `[required]` steps can't be skipped
3. Phases can roll back (e.g., Execute reveals a prd defect → return to Plan to fix, then re-enter Execute)
4. Steps tagged `[once]` are skipped if the output already exists; don't re-run
5. Artifact presence informs the next step; missing `design.md` / `implement.md` is valid for lightweight tasks and incomplete planning for complex tasks.

### Active Task Routing

When a user request matches one of these intents inside an active task, route first, then load the detailed phase step if needed.

[Claude Code, Cursor, OpenCode, codex-sub-agent, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

- Planning or unclear requirements -> `trellis-brainstorm`.
- `in_progress` implementation/check -> dispatch `trellis-implement` / `trellis-check`; implementing inline instead -> `trellis-before-dev` before edits, `trellis-check` before done.
- Repeated debugging -> `trellis-break-loop`; spec updates -> `trellis-update-spec`.

[/Claude Code, Cursor, OpenCode, codex-sub-agent, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

[codex-inline, Kilo, Antigravity, Windsurf]

- Planning or unclear requirements -> `trellis-brainstorm`.
- Before editing -> `trellis-before-dev`; after editing -> `trellis-check`.
- Repeated debugging -> `trellis-break-loop`; spec updates -> `trellis-update-spec`.

[/codex-inline, Kilo, Antigravity, Windsurf]

### Guardrails

- Task creation approval is not implementation approval; implementation waits for `task.py start` after artifact review.
- PRD-only is valid for lightweight tasks; complex tasks need `design.md` + `implement.md`.
- Planning must be persisted to task artifacts; checks must run before reporting completion.
- Verdict-bearing 评审是定义式的（研究族原则 7 反向收割）：出判定前必须加载对应 gate 的 skill/agent 协议（`trellis-review-gate` 各 mode），凭印象 ad-hoc 复刻清单不算过 gate——读不到协议不出判定。
- 摩擦当场入账：用户纠偏流程（"为什么不走 X"）或撞到规则真空/别扭时刻 → load `trellis-friction` 记一行台账后继续干活（捕获≠修改；分诊在 review-sweep 段 2，立法走 PR）。

### Loading Step Detail

At each step, run this to fetch detailed guidance:

```bash
python3 ./.trellis/scripts/get_context.py --mode phase --step <step>
# e.g. python3 ./.trellis/scripts/get_context.py --mode phase --step 1.1
```

---

## Phase 1: Plan

Goal: classify the request, get task-creation consent when a task is needed, and produce the planning artifacts required before implementation.

#### 1.0 Create task `[required · once]`

Create the task directory only after task-creation consent. The command sets status to `planning`, writes `task.json`, creates a default `prd.md`, and auto-targets the new task when session identity is available:

```bash
python3 ./.trellis/scripts/task.py create "<task title>" --slug <name>
```

`--slug` is the human-readable name only. Do **not** include the `MM-DD-` date prefix; `task.py create` adds that prefix automatically.

For task trees, create the parent task first and then create each child with `--parent <parent-dir>`. Do not start the parent just because children exist; start the child that owns the next independently verifiable deliverable.

After this command succeeds, the per-turn breadcrumb auto-switches to `[workflow-state:planning]`, telling the AI to stay in planning.

Run only `create` here — do not also run `start`. `start` flips status to `in_progress`, which switches the breadcrumb to the implementation phase before planning artifacts are reviewed. Save `start` for step 1.4.

Skip when `python3 ./.trellis/scripts/task.py current --source` already points to a task.

#### 1.1 Requirement exploration `[required · repeatable]`

Load the `trellis-brainstorm` skill and explore requirements interactively per its guidance (the skill owns the interview protocol; keep `prd.md` current after each answer, and produce `design.md` + `implement.md` for complex tasks before implementation).

Before leaving planning, fill the common Development Strategy contract. The contract is always present in generic templates; `grill-me` is the optional enhancer, not the base protocol.

```bash
python3 ./.trellis/scripts/task.py set-strategy "$TASK_DIR" \
  --execution current-session \
  --git-mode branch \
  --development-mode default \
  --spec-review disabled \
  --code-review enabled \
  --architecture-review disabled \
  --merge-review enabled
```

Allowed values:
- Execution: `current-session` or `subagent`
- Git mode: `branch` or `worktree`
- Development mode: `default` or `tdd`
- Review gates: each of `spec-review`, `code-review`, `architecture-review`, `merge-review` must be explicitly `enabled` or `disabled`
- Optional `grill-me`: add `--grill-me enabled` when the user accepts a grill-me pass (brainstorm recommends it once when acceptance criteria stay vague, scope is P0/P1 cross-package, requirements reversed mid-planning, or two requirements are in unstated tension; load `trellis-grill-me` to run it)

For parent/child splits, apply the Parent / Child Task Trees rules above.

Return to this step whenever requirements change and revise the relevant artifact.

#### 1.2 Research `[optional · repeatable]`

Research can happen at any time during requirement exploration. It isn't limited to local code — you can use any available tool (MCP servers, skills, web search, etc.) to look up external information, including third-party library docs, industry practices, API references, etc.

[Claude Code, Cursor, OpenCode, codex-sub-agent, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

Spawn the research sub-agent:

- **Agent type**: `trellis-research`
- **Task description**: Research <specific question>
- **Dispatch prompt guard**: On class-2/Codex-style platforms, the prompt starts with `Active task: <task path>`.
- **Key requirement**: Research output MUST be persisted to `{TASK_DIR}/research/`

[/Claude Code, Cursor, OpenCode, codex-sub-agent, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

[codex-inline, Kilo, Antigravity, Windsurf]

Do the research in the main session directly and write findings into `{TASK_DIR}/research/`. (For `codex-inline` this avoids a child-agent handoff; use `codex.dispatch_mode: sub-agent` only when the dispatch prompt carries `Active task: <task path>`.)

[/codex-inline, Kilo, Antigravity, Windsurf]

One file per research topic under `research/`; record library usage, API references, version constraints, and relevant spec paths. Brainstorm and research interleave freely. Output must land in files — conversations get compacted, files don't.

#### 1.3 Configure context `[required · once]`

[Claude Code, Cursor, OpenCode, codex-sub-agent, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

Curate `{TASK_DIR}/implement.jsonl` and `check.jsonl` (seeded on `task create`; one JSON object per line — `{"file": "<path>", "reason": "<why>"}`, repo-root relative). Register **spec files and `research/*.md` only** — never code files or files you are about to modify (sub-agents read those themselves). `implement.jsonl` feeds the implement agent, `check.jsonl` the check agent; neither replaces `implement.md`. Discover relevant specs with `get_context.py --mode packages`; append via editor or `task.py add-context`.

Ready gate: `implement.jsonl` and `check.jsonl` must contain at least one real `{"file": "...", "reason": "..."}` entry before `task.py start`, unless the task artifacts explicitly record that no extra injected spec/research context is needed for sub-agent execution. The seed `_example` row alone is not ready.

Skip only when both files are already ready by the rule above.

[/Claude Code, Cursor, OpenCode, codex-sub-agent, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

[codex-inline, Kilo, Antigravity, Windsurf]

Skip this step. Context is loaded directly by the `trellis-before-dev` skill in Phase 2.

[/codex-inline, Kilo, Antigravity, Windsurf]

#### 1.4 Activate task `[required · once]`

After artifact review, flip the task status to `in_progress`:

```bash
python3 ./.trellis/scripts/task.py start <task-dir>
```

For lightweight tasks, `prd.md` can be enough. For complex tasks, `prd.md`, `design.md`, and `implement.md` must exist and be reviewed before start. P0/P1 tasks are guarded by `task.py start`; platform workflow tasks also need persisted `research/*.md` evidence unless the PRD records a clear research exemption. Use `python3 ./.trellis/scripts/task.py validate <task-dir>` before start to see the same gate without changing status. On sub-agent-dispatch platforms, `implement.jsonl` and `check.jsonl` must be ready by the Phase 1.3 rule before start; runtime consumers tolerate missing or seed-only manifests for compatibility, but planning-ready state must be explicit.

Do not start until the Development Strategy contract has explicit choices. For tiny PRD-only tasks, the choices can still be simple: `current-session`, `branch`, `default`, and disabled review gates except the checks you actually intend to run.

If `spec-review` is enabled, load `trellis-review-gate` and run the `spec-review` gate before `task.py start`. Resolve BLOCKED findings by updating planning artifacts, then rerun the gate.

After this command succeeds, the breadcrumb auto-switches to `[workflow-state:in_progress]`, and the rest of Phase 2 / 3 follows.

If `task.py start` errors with a session-identity message (no context key from hook input, `TRELLIS_CONTEXT_ID`, or platform-native session env), follow the hint in the error to set up session identity, then retry.

#### 1.5 Completion criteria

| Condition | Required |
|------|:---:|
| `prd.md` exists | ✅ |
| Development Strategy choices recorded | ✅ |
| User confirms task should enter implementation | ✅ |
| `task.py start` has been run (status = in_progress) | ✅ |
| `research/` has artifacts (P0/P1 platform workflow tasks) | ✅ |
| `design.md` exists (complex tasks) | ✅ |
| `implement.md` exists (complex tasks) | ✅ |

[Claude Code, Cursor, OpenCode, codex-sub-agent, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

| `implement.jsonl` and `check.jsonl` each contain a real curated entry, or task artifacts explicitly record that no extra injected context is needed | ✅ |

[/Claude Code, Cursor, OpenCode, codex-sub-agent, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

---

## Phase 2: Execute

Goal: turn reviewed planning artifacts into code that passes quality checks.

#### 2.1 Implement `[required · repeatable]`

**development-mode=tdd (per-task, from the Development Strategy):** drive this step one behavior slice at a time — write one failing test for the next slice, implement just enough to go green, refactor, then move to the next slice. Slices and interfaces come from the TDD planning gate in `implement.md`; never batch multiple red tests ahead of green.

[Claude Code, Cursor, OpenCode, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

Spawn the implement sub-agent:

- **Agent type**: `trellis-implement`
- **Task description**: Implement the reviewed task artifacts, consulting materials under `{TASK_DIR}/research/`; finish by running project lint and type-check
- **Dispatch prompt guard**: Tell the spawned agent it is already the `trellis-implement` sub-agent and must implement directly, not spawn another `trellis-implement` / `trellis-check`.

The platform hook/plugin/prelude auto-injects `implement.jsonl` context plus `prd.md`, `design.md` if present, and `implement.md` if present.

[/Claude Code, Cursor, OpenCode, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

[codex-sub-agent]

Same dispatch as above, with one hard addition: the prompt MUST start with `Active task: <task path>`. The Codex agent definition loads task artifacts from files (dispatch line first, `task.py current --source` fallback) and requires each `implement.jsonl` entry to be loaded before coding.

[/codex-sub-agent]

[codex-inline, Kilo, Antigravity, Windsurf]

1. Load the `trellis-before-dev` skill to read project guidelines
2. Read `{TASK_DIR}/prd.md`, then `design.md` if present, then `implement.md` if present
3. Consult materials under `{TASK_DIR}/research/`
4. Implement the code per reviewed artifacts
5. Run project lint and type-check

[/codex-inline, Kilo, Antigravity, Windsurf]

#### 2.2 Quality check `[required · repeatable]`

[Claude Code, Cursor, OpenCode, codex-sub-agent, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

Spawn the check sub-agent:

- **Agent type**: `trellis-check`
- **Task description**: Review all code changes against specs and task artifacts; fix any findings directly; ensure lint and type-check pass
- **Dispatch prompt guard**: On class-2/Codex-style platforms, the prompt starts with `Active task: <task path>`. Tell the spawned agent it is already the `trellis-check` sub-agent and must review/fix directly, not spawn another `trellis-check` / `trellis-implement`.

The check agent's job:
- Review code changes against specs
- Review code changes against `prd.md`, `design.md` if present, and `implement.md` if present
- Auto-fix issues it finds
- Run lint and typecheck to verify

[/Claude Code, Cursor, OpenCode, codex-sub-agent, Kiro, Gemini, Qoder, CodeBuddy, Copilot, Droid, Pi, ZCode, Reasonix, Trae]

[codex-inline, Kilo, Antigravity, Windsurf]

Load the `trellis-check` skill and verify the code per its guidance:
- Spec compliance
- lint / type-check / tests
- Cross-layer consistency (when changes span layers)

If issues are found → fix → re-check, until green.

[/codex-inline, Kilo, Antigravity, Windsurf]

Final pass before commit or remote delivery: the last 2.2 / 3.1 verification must be full-scope, not only the latest edit chunk. List affected packages with `python3 ./.trellis/scripts/get_context.py --mode packages`, then load the relevant spec indexes and quality sections.

After the normal quality check passes, run enabled review gates from the Development Strategy:
- `code-review`: load `trellis-review-gate` with mode `code-review`. **Unified gate**: the final full-scope check pass and the code-review gate run as ONE reviewer dispatch carrying both checklists (see `trellis-review-gate`), not two back-to-back fresh agents rebuilding the same evidence. Bug-class child tasks get exactly one such pass.
- `architecture-review`: load `trellis-review-gate` with mode `architecture-review`

Treat BLOCKED gate findings like check findings: fix, rerun the relevant checks, then rerun the gate as a **delta re-review** — scoped to the fix diff and its affected surface only; already-green full suites are not re-run, unchanged artifacts are not re-read. Full-scope review happens once per milestone, not once per fix iteration.

#### 2.3 Rollback `[on demand]`

- `check` reveals a prd defect → return to Phase 1, fix `prd.md`, then redo 2.1
- Implementation went wrong → revert code, redo 2.1
- Need more research → research (same as Phase 1.2), write findings into `research/`

---

## Phase 3: Finish

Goal: ensure code quality, capture lessons, record the work.

#### 3.1 Quality verification `[required · repeatable]`

Load the `trellis-check` skill and do a final verification:
- Spec compliance
- lint / type-check / tests
- Cross-layer consistency (when changes span layers)

If issues are found → fix → re-check, until green.

If `merge-review` is enabled, its mechanical evidence is scripted: `trellis_ship preflight` covers dirty scope, branch/task consistency, `git diff --check`, and `task.py validate`. Dispatch the `trellis-merge-review` agent only for **cross-repo contract changes** (or on explicit user request), after final verification and before committing or remote delivery. Resolve BLOCKED findings before continuing.

#### 3.2 Debug retrospective `[on demand]`

If this task involved repeated debugging (the same issue was fixed multiple times), load the `trellis-break-loop` skill to:
- Classify the root cause
- Explain why earlier fixes failed
- Propose prevention

The goal is to capture debugging lessons so the same class of issue doesn't recur.

#### 3.3 Spec update `[required · once]`

Load the `trellis-update-spec` skill and review whether this task produced new knowledge worth recording:
- Newly discovered patterns or conventions
- Pitfalls you hit
- New technical decisions

Update the docs under `.trellis/spec/` accordingly. Even if the conclusion is "nothing to update", walk through the judgment.

#### 3.4 Commit changes `[required · once]`

Spec-sync preamble: before drafting commits, ask whether this task fixed a bug or surfaced non-obvious knowledge that belongs in `.trellis/spec/` so future sessions do not repeat the issue. If yes, return to Phase 3.3 before committing; spec writes belong in the same task's commit batch.

The AI drives a batched commit of this task's code changes so `/finish-work` can run cleanly afterwards. Goal: produce work commits FIRST, then bookkeeping (archive + session index) commits land after — never interleaved.

**Protocol** (working tree clean → skip to 3.5):

1. Classify dirty files: **AI-edited this session** vs **unrecognized** (user edits / leftover WIP — never silently include).
2. Draft one batched commit plan matching the repo's existing message style: logical commits (one per coherent change unit), unrecognized files listed separately for include/exclude.
3. Present the plan **once** for one-shot confirmation, then execute in order. On any rejection of the grouping, stop and hand over to manual — no second plan.

**Rules**:
- No `git commit --amend` anywhere — three-stage three-commit flow (work commits → archive commit → session-index commit).
- Never push to remote in this step.
- If the user wants different message wording but accepts the file grouping, edit the message and re-confirm once — but if they reject the grouping, exit to manual mode.
- The batched plan is one prompt; do not prompt per commit.

#### 3.5 Wrap-up reminder

After the above, give a goal-dependent next step rather than a linear order. 会话产生了跨项目结论/复盘/判例（"值得存"）→ load `vault-deposit` 当场投递知识库（上下文最完整时刻最便宜；中断会话由接手者开局补）。 If the user wants local wrap-up/bookkeeping only, suggest `/trellis:finish-work`. If the user wants remote PR delivery, suggest `/trellis:ship` directly; ship will finalize before the first push/PR CI when an active task remains.

---

## Customizing Trellis

Fork-maintainer guidance lives outside the per-project file: per-turn text is edited directly in the `[workflow-state:*]` blocks above (see the breadcrumb contract comment); custom statuses / lifecycle hooks / the full state-machine contract are documented in `.trellis/spec/cli/backend/workflow-state-contract.md`, and `.trellis/scripts/inject-workflow-state.py` is the actual parser (reads this file only).
