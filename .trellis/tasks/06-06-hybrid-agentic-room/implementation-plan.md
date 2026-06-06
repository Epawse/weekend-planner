# Implementation Plan

## Phase 0: Context and Trellis

- Read `new_plantemp.md`.
- Read backend/frontend Trellis specs.
- Document scope and acceptance.

## Phase 1: Schemas and Agent Service

- Add RoomPatch Pydantic schemas.
- Add LLM room agent prompt construction, JSON extraction, validation, and repair attempt.
- Add tests for schema validation and extraction.

## Phase 2: Room Integration

- Add agent mode/version/lock fields.
- Add async `advance_room_agentic`.
- Add fallback from agentic to scripted.
- Apply messages, memory delta, plan copy, consensus copy, final copy.
- Preserve deterministic `simulate_room`.

## Phase 3: API and Types

- Wire `/api/room/{room_id}/advance` to agentic advance by default when LLM providers are configured.
- Add optional query parameter to force `mode=scripted|llm`.
- Mirror `agent_mode` and `room_version` in frontend types if serialized.

## Phase 4: Tests

- No API key -> scripted fallback.
- Invalid LLM JSON -> scripted fallback.
- Invalid plan ID/venue/speaker -> scripted fallback.
- Concurrent advance for one room remains one-step-at-a-time.
- Existing collaborative room tests remain green.

## Phase 5: Verification and Documentation

- Run backend pytest and ruff.
- Run frontend lint/tsc/build if types changed.
- Update Trellis progress/check/handoff.
- Commit changes.

