# Implementation Plan

## Phase 0: Current-State Audit

- Record `git status --short` and `git diff --stat`.
- Audit current backend payload fields and frontend consumers.
- Identify existing family/friends tests that must continue passing.

## Phase 1: PlanCanvasState Backend Contract

- Add `backend/app/models/canvas.py`.
- Add `backend/app/services/canvas.py`.
- Emit `plan_canvas` in `plan_ready`.
- Build map markers, metrics, checks, evidence cards, rejected options, tool tasks, feedback actions, and pending actions.
- Add backend tests for family/friends Canvas building and source scrubbing.

## Phase 2: PlanCanvas Frontend Main UI

- Add `PlanCanvasState` types in `frontend/lib/types.ts`.
- Update `useChat` to store `planCanvas`.
- Add `frontend/components/canvas/*`.
- Switch `frontend/app/page.tsx` to three-column workbench with old PlanCard fallback.

## Phase 3: EvidencePanel

- Add evidence components.
- Render evidence grouped by `source_label`.
- Render rejected options.
- Support selection callbacks for timeline/map linking.

## Phase 4: Map VenuePopover and Linkage

- Upgrade `MapView` to consume canvas map data.
- Add marker click selection and VenuePopover.
- Add timeline click/hover selection that highlights map marker.
- Keep route notice behavior for sequence estimate vs AMap route.

## Phase 5: Local-Life Fan-out Task Display

- Build `tool_tasks` from current state/stats/checks.
- Add `ToolTaskPanel` to left rail or Canvas header.
- Ensure it reads as task decomposition, not raw logs.

## Phase 6: Feedback v1

- Add request schema and `/api/plan/feedback`.
- Add feedback parser/handler service.
- Apply deterministic adjustments or constrained replan using existing candidates.
- Rebuild PlanCanvasState and stream/return updated plan canvas.
- Add tests for closer, indoor, cuisine exclusion, and earlier end.

## Phase 7: Execution Action Cards

- Add pending action generation server-side.
- Update `useChat` to merge execution stream events into canvas state.
- Add `ExecutionActionCard`.

## Phase 8: Polish, Verification, Docs

- Run backend pytest and ruff.
- Run frontend lint and `npx tsc --noEmit`.
- Manually inspect user-facing strings for technical token blacklist.
- Update `progress.md`, `check.md`, and `handoff.md`.

## Commit Suggestions

- `feat: add plan canvas state contract`
- `feat: add plan canvas workbench layout`
- `feat: add evidence panel and source cards`
- `feat: add map venue popover interactions`
- `feat: add feedback replan workflow`
- `feat: add execution action cards`
- `chore: update trellis docs and demo guide`
