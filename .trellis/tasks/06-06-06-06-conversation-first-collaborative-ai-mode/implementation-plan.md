# Implementation Plan

## Phase 1: Trellis And Audit

- Create task docs.
- Review current room components and hook.

## Phase 2: Frontend View Model

- Add `activeView` in `app/page.tsx`.
- Pass view handlers into the thread.
- Hide right panel unless plan exists and view is plans/final.

## Phase 3: Chat Mode

- Refactor `CollaborativeThread` to render separate chat/plans/final views.
- Add compact plan-ready card.
- Improve idle hero and composer layout.
- Add quick reply chips.

## Phase 4: Plan Mode

- Keep full A/B/C cards here only.
- Add concise mode header and why-recommended area.
- Keep voting, reactions, and group memory.

## Phase 5: Final Mode

- Put final summary and embedded PlanCanvas here.
- Keep host-only execution.

## Phase 6: Copy And Playback Polish

- Adjust backend staged assistant copy away from debug language.
- Add varied playback delays.

## Phase 7: Verification

- Run backend pytest/ruff.
- Run frontend lint/tsc/build.
- Smoke front/backend.
- Update docs and commit.
