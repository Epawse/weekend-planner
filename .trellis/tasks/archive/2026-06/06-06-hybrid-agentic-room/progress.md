# Progress

## 2026-06-06

- Created task.
- Read `new_plantemp.md`.
- Confirmed existing room service is deterministic staged mock.
- Confirmed frontend already implements `chat | plans | final`.
- Confirmed LLM provider fallback already exists.

Next: implement RoomPatch schemas and LLM room agent.

## Implementation

- Added `RoomPatch` schema layer:
  - short message drafts.
  - memory deltas.
  - plan copy updates.
  - venue-level signals.
  - consensus and final copy patches.
- Added `llm_room_agent.py`:
  - builds a compact room-state prompt.
  - uses existing `llm_factory.invoke_with_fallback`.
  - extracts JSON from raw text or fenced blocks.
  - validates with Pydantic.
  - retries one repair prompt before surfacing `LLMRoomAgentError`.
- Reworked room advancement:
  - kept `advance_room` as deterministic scripted fallback.
  - added async `advance_room_agentic`.
  - added per-room `asyncio.Lock`.
  - added `agent_mode` and `room_version`.
  - no key -> scripted fallback.
  - invalid LLM output or semantic validation failure -> scripted fallback.
- Added backend patch application:
  - replace/enhance next-step visible messages.
  - merge dynamic memory without letting refresh overwrite it.
  - update A/B/C label, positioning, risks, fit_for, reason.
  - validate speaker, plan id, and venue id.
  - apply backend-validated consensus copy.
  - update final summary/share text while keeping mock execution deterministic.
- Added frontend type fields for `agent_mode`, `room_version`, and optional agentic plan copy.
- Updated plan cards to show optional LLM reason / fit-for text.

## Verification

- `cd backend && .venv/bin/python -m pytest` -> 81 passed.
- `cd backend && .venv/bin/python -m ruff check app tests` -> passed.
- `cd frontend && npm run lint` -> passed.
- `cd frontend && npx tsc --noEmit` -> passed.
- `cd frontend && npm run build` -> passed.

## Risks

- Agentic mode depends on configured LLM providers; scripted fallback remains the stable demo path.
- Current LLM plan generation intentionally does not choose new venue combinations. It updates plan copy and explanations while backend-owned templates keep map/evidence/execution stable.
- Repair prompt does one extra provider call on invalid output, matching the task plan's repair requirement.
