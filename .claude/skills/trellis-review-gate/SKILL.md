---
name: trellis-review-gate
description: "Use when a Trellis task's Development Strategy enables spec-review, code-review, architecture-review, or merge-review; or when the user asks to run a Trellis review gate. Dispatches an independent read-only reviewer sub-agent and tracks repeated blocks (3-strikes)."
---

# Trellis Review Gate

Run a review gate for the active Trellis task through an **independent read-only reviewer**, then track the verdict. This skill orchestrates; the reviewing happens in a fresh context so the reviewer does not inherit the implementer's assumptions.

## Step 1: Confirm the Gate

1. Resolve the active task: `python3 ./.trellis/scripts/task.py current --source`
2. Check `task.json.meta.development_strategy.review_gates.<gate>`. If `disabled`, report that and stop unless the user explicitly asks to run it anyway.

## Step 2: Dispatch the Reviewer

**Sub-agent platforms (Claude Code and class-2 dispatch):** spawn the matching read-only agent — `trellis-spec-review` / `trellis-code-review` / `trellis-architecture-review` / `trellis-merge-review`:

- The dispatch prompt MUST start with `Active task: <task path>`, then state the agent is already that reviewer and must review directly without spawning further agents.
- These agents carry `tools: Read, Bash, Glob, Grep` and `model: opus` — no write surface by construction.

**Inline platforms (codex-inline, Kilo, Antigravity, Windsurf):** no sub-agent is available. Switch yourself into the reviewer role: load the matching agent file under `.claude/agents/` and follow its Review Focus, Read-Only Discipline, and Output sections in the current session. State explicitly that this is an inline degraded review (same session, weaker independence).

**Unified gate (check + code-review, one dispatch):** when `code-review` is enabled, the final full-scope `trellis-check` pass and the code-review gate run as ONE dispatch, not two back-to-back fresh agents — their evidence lists overlap ~70%, and each fresh reviewer rebuilds all evidence from cold start. Dispatch the `trellis-code-review` reviewer with the check duties folded into the prompt: spec/PRD compliance + lint/type/tests verification + its own review focus. Bug-class child tasks get exactly one such pass.

**Delta re-review (re-runs after a fix):** a gate re-run after BLOCKED/finding fixes reviews the delta, not the world. The dispatch prompt must scope it: review the fix diff and its affected surface only; do NOT re-run full test suites that are already green (only tests touching the fix); do NOT re-read artifacts that did not change. Full-scope review happens once per milestone, not once per fix iteration. (Data: a 72-min run spent 14 min on post-fix re-verification with zero findings — the same vitest suite ran 5×, the same 7 artifacts were re-read by 5 fresh agents.)

**merge-review is scripted by default:** its mechanical evidence (dirty scope, `git diff --check`, `task.py validate`, PR readiness) lives in `trellis_ship preflight`. Dispatch the `trellis-merge-review` agent only for cross-repo contract changes, or when the user explicitly asks for an agent pass.

**Effort routing:** synchronous gate reviewers run at `high` — synchronous waiting is the most expensive cost and `high` finding quality holds. `xhigh` belongs to the asynchronous review sweep (`trellis-review-sweep`), where nobody is waiting.

## Step 3: Record the Verdict (3-strikes)

Track repeated blocks in `.trellis/.runtime/review-gate-strikes.json` (runtime, never committed), keyed `"<task-dir>:<gate>"`:

- `Verdict: BLOCKED` -> increment the counter, then hand the P1 findings to the normal fix loop (fix -> re-check -> re-run this gate).
- `Verdict: PASS` -> reset the counter to 0.
- Counter reaches **3** -> stop the loop. Report to the user: the gate has blocked this task three consecutive times, list the recurring findings, and ask whether to (a) keep fixing, (b) skip this gate for this task (record the ruling in `task.json` notes / PRD), or (c) re-scope the task. Do not silently keep looping.

Read/update the counter with a small inline command, e.g.:

```bash
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path('.trellis/.runtime/review-gate-strikes.json')
data = json.loads(p.read_text()) if p.exists() else {}
key = "<task-dir>:<gate>"; verdict = "<PASS|BLOCKED>"
data[key] = 0 if verdict == "PASS" else data.get(key, 0) + 1
p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(data, indent=1))
print(key, "->", data[key])
EOF
```

## Step 4: Follow-ups

- After `architecture-review` PASSes, if the task wants a deeper pass, the main session may load `trellis-improve-architecture` in deep-review mode (never from inside the reviewer).
- Gate reports are read-only: fixes always happen in the main session or via the normal implement/check path, never by the reviewer.
