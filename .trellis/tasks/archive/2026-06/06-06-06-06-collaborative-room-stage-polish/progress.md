# Progress

## 2026-06-06 Setup

Completed:

- Created and started Trellis task.
- Confirmed working tree started clean.
- Read backend Plan Canvas and Collaborative Room specs.
- Read frontend component and state-management specs.
- Reviewed previous collaborative room implementation.

Next:

- Implement backend room stage machine and family scenario.

Risks:

- Existing collaborative room tests assert full demo state at reset; they need to be updated to the new idle-first contract.

## 2026-06-06 Implementation

Completed:

- Added staged `RoomState` fields: stage, stage title/description, typing participants, demo step index, and available scenarios.
- Changed room reset/get to return idle state with no preloaded messages, plan options, votes, or reactions.
- Added `/api/room/{room_id}/advance` for one-event-at-a-time demo progression.
- Added `/api/room/{room_id}/scenario` and optional reset/simulate scenario support.
- Added deterministic friends staged script:
  - host prompt.
  - Agent task split.
  - invited members.
  - green/blue/pink typing and messages.
  - A/B/C options.
  - voting.
  - reactions and consensus.
  - final B plan.
- Added deterministic family staged script:
  - 小明 host prompt.
  - 老婆 typing/message.
  - child as profile constraint.
  - family A/B/C options.
  - B 早点回家优先 consensus.
- Reworked frontend room types, API helpers, and `useRoom` to support stage advancement, scenario switching, and staged auto playback.
- Reworked left sidebar into scenario/room/member/vote/consensus control area.
- Reworked middle column into fixed-height Conversation + Canvas thread with internal scroll and sticky composer.
- Added typing indicators in `RoomMessageList`.
- Delayed A/B/C cards, group memory, venue reactions, and Plan Canvas until their stage.
- Added right-panel waiting state and current displayed plan label.
- Updated backend collaborative room spec and README API documentation.

Verification:

- `cd backend && .venv/bin/python -m pytest tests/test_tools/test_collaborative_room.py` -> 8 passed.
- `cd backend && .venv/bin/python -m pytest` -> 73 passed.
- `cd backend && .venv/bin/python -m ruff check app tests` -> passed.
- `cd frontend && npx tsc --noEmit` -> passed.
- `cd frontend && npm run lint` -> passed.
- `cd frontend && npm run build` -> passed.
- Backend smoke on `http://127.0.0.1:8001`:
  - `GET /api/room/demo_friends_room?user=red` returned idle room.
  - `POST /api/room/demo_friends_room/advance?user=red` returned `host_prompted`.
  - `POST /api/room/demo_family_room/scenario` returned family idle room with wife and child.
  - `POST /api/room/demo_family_room/advance?user=red` returned family `host_prompted`.
  - `POST /api/room/demo_friends_room/simulate?user=red` returned `final_plan_ready`.
- Frontend smoke:
  - `http://127.0.0.1:3000` responded.
  - Frontend dev server started with `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001`.

Notes:

- Demo rooms were reset to idle after API smoke so opening the running app starts clean.
- Backend port binding required elevated execution in this sandbox.
- Ruff formatter mechanically reformatted a few existing backend Python files while fixing line-length issues; no behavior changes were made there.

Next:

- Commit staged collaborative room demo polish.
