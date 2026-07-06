---
name: trellis-improve-architecture
description: "Three-mode architecture improvement: proactive codebase analysis into a ranked candidate list, pre-dev guidance appended to design.md before task.py start, and a post-gate deep review after trellis-architecture-review passes. Use when the user asks to 改进架构/architecture health check, when planning wants architecture guidance, or when the strategy calls for a deep post-gate pass."
---

# Trellis Improve Architecture

Three distinct modes, selected by the dispatch marker in the prompt. Never combine modes in one run.

## Mode Selection

- No `架构审查模式:` marker -> **Mode A: Proactive Analysis**
- `架构审查模式: guidance` -> **Mode B: Pre-Dev Guidance**
- `架构审查模式: deep-review` -> **Mode C: Post-Gate Deep Review**

## Mode A: Proactive Analysis

Goal: turn "the codebase could be better" into a ranked, decidable candidate list.

1. If a task is active, ask whether to switch focus before proceeding.
2. Explore the codebase (specs first: `.trellis/spec/**` indexes, then the code). If a relevant spec exists, judge against it; if not, confirm the intended convention with the user one question at a time and record it in `.trellis/spec/` before judging against it.
3. Produce a numbered candidate list — each entry: current pain (with file evidence), proposed direction, blast radius, and a rough size tag (S/M/L).
4. Write the list into a new task's `prd.md` (create the task with consent, per workflow Phase 1.0). The list is a menu, not an execution order: the user picks; each picked item becomes its own task.

Constraints: read-only toward code; no refactoring "while we're here".

## Mode B: Pre-Dev Guidance

Goal: shape the design before implementation starts.

1. Read `prd.md`, `design.md`, and the relevant `.trellis/spec/**` for touched packages.
2. Append a guidance section to `design.md`: module boundaries this task must respect, key abstractions to reuse or introduce, and the architectural risks the implementer should watch.
3. Do not create tasks, do not run `task.py`, do not edit code. Guidance lands in `design.md` only.

## Mode C: Post-Gate Deep Review

Precondition: `trellis-architecture-review` has PASSed for this task, and the strategy has `architecture-review: enabled`. Selecting deep-review without the gate is an invalid strategy — report that and stop.

1. Read `design.md` (including Mode B guidance if present) and the relevant specs.
2. Review every changed file against them — deeper than the gate: hidden coupling, abstraction erosion, boundary drift that individual diffs hide.
3. Verdict `PASS` or `FAIL` with concrete findings. On FAIL, the main session routes back to the implement/check loop and re-runs the review chain; you never edit code yourself.

## Recursion Guard

Whichever mode: do not spawn trellis-implement, trellis-check, or any review-gate agent from inside this skill. Only the main session dispatches Trellis agents.
