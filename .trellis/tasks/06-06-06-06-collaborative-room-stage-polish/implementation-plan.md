# Implementation Plan

## Phase 0: Current Contract Review

- Read backend/frontend specs.
- Inspect current `RoomState`, room service, frontend room components, and tests.

## Phase 1: Backend Stage Machine

- Add room stage and typing fields to models.
- Reset rooms to idle.
- Add `advance_room` and `set_room_scenario`.
- Build staged friends and family scripts.
- Keep `simulate_room` as full-demo fallback.

## Phase 2: Family Scenario

- Add family participants and deterministic family PlanOptions.
- Ensure family canvas keeps child, clear meal, child seat, low walking, and early return actions.

## Phase 3: Frontend Types/API/Hook

- Add stage/scenario fields and advance/scenario API helpers.
- Add staged demo playback in `useRoom`.

## Phase 4: Layout And Rendering

- Make the main page fixed-height.
- Make the middle column scroll internally.
- Keep composer sticky at the bottom.
- Render idle, typing, option, voting, consensus, final, execution stages progressively.

## Phase 5: Right Panel And Copy Polish

- Add waiting state when no plan exists.
- Label current map/source plan.
- Reduce repeated Agent templates and use member-specific change copy.

## Phase 6: Verification And Delivery

- Update tests.
- Run backend pytest and ruff.
- Run frontend lint, tsc, and build.
- Start/verify dev servers.
- Update Trellis docs.
- Commit final changes.
