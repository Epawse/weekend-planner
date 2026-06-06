# Implementation Plan

## Phase 0: Task Setup

- Create Trellis task docs.
- Read backend/frontend specs.
- Inspect current Plan Canvas code.

## Phase 1: Room Backend Contract

- Add `backend/app/models/room.py`.
- Add `backend/app/services/room.py`.
- Build deterministic demo room with participants, messages, plan options, votes, reactions, memory, and consensus.

## Phase 2: Room API

- Add request/response schemas.
- Add `/api/room/{room_id}` endpoints:
  - `GET`
  - `POST /message`
  - `POST /vote`
  - `POST /reaction`
  - `POST /simulate`
  - `POST /execute`

## Phase 3: Frontend Types And API

- Add RoomState types to `frontend/lib/types.ts`.
- Add room API helpers to `frontend/lib/api.ts`.
- Add `frontend/hooks/useRoom.ts`.

## Phase 4: Collaborative UI

- Rework `frontend/app/page.tsx` into room-first layout.
- Add room sidebar.
- Add center collaborative thread and plan options.
- Reuse `PlanCanvas`, `MapView`, `EvidencePanel`.

## Phase 5: Voting And Reactions

- Add plan-level voting.
- Add venue reaction controls in the thread.
- Reflect voting signal in group memory and evidence.

## Phase 6: Execution

- Host-only execute endpoint and UI.
- Display execution action cards through existing PlanCanvas.

## Phase 7: Verification And Docs

- Add backend tests for room state, vote/reaction updates, execute, and source scrubbing.
- Run backend pytest/ruff and frontend lint/tsc.
- Update Trellis progress/check/handoff.
- Commit changes.
