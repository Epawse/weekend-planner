# Hybrid Agentic Room Design

## Architecture

The room remains a deterministic workflow with an optional LLM RoomPatch layer.

```text
RoomState snapshot
  -> LLM prompt with scenario/stage/personas/recent messages/memory/plan defs/venue ids
  -> RoomPatch JSON
  -> Pydantic validation
  -> semantic validation
  -> backend hydrate/apply
  -> refresh derived room fields
```

If any step fails, the old scripted advance runs.

## New Backend Modules

- `backend/app/services/room_agent_schemas.py`
  - `MessageDraft`
  - `MemoryDelta`
  - `PlanCopyUpdate`
  - `ConsensusPatch`
  - `FinalCopyPatch`
  - `RoomPatch`

- `backend/app/services/llm_room_agent.py`
  - Builds the prompt.
  - Calls `llm_factory.invoke_with_fallback`.
  - Extracts strict JSON.
  - Retries one repair prompt on parse/validation failure.
  - Raises `LLMRoomAgentError` for fallback.

## Room Service Changes

- Keep `advance_room` as the public sync scripted fallback.
- Add `async advance_room_agentic(room_id, active_user_id, agent_mode="llm")`.
- Add per-room `asyncio.Lock`.
- Add `room_version` and `agent_mode` to RoomState payload.
- Add `dynamic_memory` to internal room dict only; serialized `group_memory` remains compatible.
- Split refresh behavior:
  - Scripted mode may continue deriving group memory from stage.
  - Agentic mode merges `memory_delta` and does not overwrite dynamic memory.

## Patch Application Rules

- Speaker IDs must be participants in the room and cannot be `child`.
- Message text is short and scrubbed by schema limits.
- Plan IDs must map to current options.
- Venue IDs must exist in current plan canvases or known demo venue IDs.
- `PlanCopyUpdate` can change option label/positioning only, not venue facts.
- Consensus summary can be written by LLM, but active plan selection is validated against vote rules.
- Final copy can update canvas summary/share text and execution-state summary; mock execution remains deterministic.

## Frontend Impact

Current frontend already has `chat | plans | final`; no major UI rewrite is required.
Only type additions are needed if serialized `agent_mode`/`room_version` become part of `RoomState`.

