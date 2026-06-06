# AI Mode Plan Canvas Workbench

## Goal

Upgrade Weekend Planner from a chat-first demo into a Plan Canvas workbench for family outings and friends gatherings. The product should organize local-life planning results as a structured, explainable, map-linked, editable, and executable workspace.

## Users

- Family outing users who care about child fit, low fatigue, low queue time, light meals, child seats, and easy fallback plans.
- Friends gathering users who care about social interaction, photo-friendly activities, 4-person tables, route focus, after-dinner continuation, and easy group sharing.

## Core Scenarios

- Generate a plan from one natural-language request.
- Review the plan in a central Plan Canvas instead of a narrow chat card.
- Inspect sources and validation evidence in a user-friendly EvidencePanel.
- Interact with map markers and venue popovers linked to the timeline.
- Apply follow-up feedback to the current plan: closer, indoor, exclude cuisine, go home earlier.
- Confirm the plan and see concrete execution actions and results.

## Non-Goals

- Real payment, real Meituan order placement, or production booking integrations.
- Account system, multi-user voting, or persisted user profiles.
- Production-grade navigation accuracy beyond available AMap route data or sequence estimate.
- Adding a third scenario beyond family and friends.

## Requirements

- Add a unified PlanCanvasState contract emitted by the backend.
- Make family and friends plans render through one PlanCanvas structure.
- Keep user-facing fields separate from debug/raw fields.
- Add a three-column workbench on desktop: chat/control, Plan Canvas, map/evidence right panel.
- Keep the chat area for input, task progress, and quick feedback, not full plan display.
- Add EvidencePanel grouped by source label and rejected options.
- Add map marker selection, VenuePopover, and timeline/evidence marker linking.
- Add Local-life fan-out task status model from existing planning signals.
- Add feedback workflow for first-version replanning or deterministic plan adjustment.
- Add pending execution actions before approval and execution results after approval.
- Preserve existing evidence-bound and quality-gate behavior.

## Acceptance Criteria

- [ ] `plan_canvas` is present in `plan_ready` payload for both family and friends.
- [ ] Frontend primary plan display reads PlanCanvasState instead of reconstructing scattered plan fields.
- [ ] Three-column workbench is visible on desktop.
- [ ] Family and friends example inputs both produce a usable Plan Canvas.
- [ ] User main UI does not show `mock`, `showcase_curated`, `fallback_generated`, `typecode`, `source=`, `raw_source`, `debug`, or `POI 来源为`.
- [ ] Right panel has map and source tabs.
- [ ] Map markers are clickable and show venue popovers.
- [ ] Timeline selection highlights corresponding map marker.
- [ ] Evidence cards can reference and highlight related timeline/map items.
- [ ] Quick feedback supports closer, indoor, cuisine exclusion, and earlier ending.
- [ ] Confirming a plan updates execution action cards in the Canvas.
- [ ] Backend tests, ruff, frontend lint, and TypeScript typecheck pass or documented blockers are recorded.

## Definition of Done

- Backend PlanCanvasState builder and tests exist.
- Frontend workbench components render both scenarios.
- Feedback endpoint or flow updates current plan and rebuilds PlanCanvasState.
- Execution events are reflected in Canvas state.
- Trellis `design.md`, `implementation-plan.md`, `progress.md`, `check.md`, and `handoff.md` are current.
- Final handoff records test commands, user-visible checks, git status, diff stat, risks, and suggested commit messages.

## Existing Repo Facts

- Backend uses FastAPI + LangGraph in `backend/app/agents/orchestrator.py`.
- `PlannerState` currently stores scattered plan, evidence, checks, route, and execution state in `backend/app/models/state.py`.
- Family/friends logic already exists in `backend/app/services/family.py` and `backend/app/services/friends.py`.
- Existing frontend uses `useChat` to consume SSE and creates `PlanMapData` from scattered `plan_ready` fields.
- Current UI is left chat/plan card and right map in `frontend/app/page.tsx`.
- Current map already draws AMap markers/routes but lacks user-level marker selection and venue popover state.

## Assumptions

- Existing dirty working tree contains intended family/friends work and must be preserved.
- Mock/showcase data is acceptable for demo business actions, but raw technical labels must be hidden from the main UI.
- Feedback v1 can be deterministic and conservative; it does not need full parallel LangGraph replanning if quality gates and Canvas rebuilding are preserved.

## Technical Notes

- Follow `.trellis/spec/backend/*`, `.trellis/spec/frontend/*`, and `.trellis/spec/guides/*`.
- Prefer an adapter layer over deleting old `PlanCard` immediately.
- Add tests around contract building and feedback logic first where practical.
- Keep frontend state minimal; backend remains source of truth for plans.
