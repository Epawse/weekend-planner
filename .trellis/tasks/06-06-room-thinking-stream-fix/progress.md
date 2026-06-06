# Progress

## Status: implementation complete, gates green, awaiting commit

## Summary
Fixed the two collaborative-room "thinking" bugs:
1. Ordering — the member/user message now appears before the agent "正在思考" bubble.
2. Reasoning — the streamed reasoning stays visible and no longer flashes/vanishes.

Both the auto-demo (playDemo stream) and interactive send (`/message`) flows are fixed;
interactive send was routed through a new streaming LLM endpoint so its reasoning is genuine.

## Changes
### Backend
- `room.py` — split `add_room_message` into `_resolve_message_room` + `_ingest_user_message`
  + `_scripted_agent_reply` + `_append_scripted_reply`; added `add_room_message_stream`
  (commits the user message first, streams reasoning, applies a validated RoomPatch, falls
  back to the scripted reply on no-LLM / failure / patch-without-agent-message).
- `routes.py` — new `POST /room/{room_id}/message/stream` SSE route.
- `llm_room_agent.py` — content-preserving line-wraps on 3 long prompt strings (E501).
- `provider.py` — `ruff format` only (pre-existing WIP style fix).

### Frontend
- `lib/api.ts` — extracted shared `parseRoomStream`; added `streamRoomMessage`.
- `hooks/useRoom.ts` — `sendMessage` optimistically renders the user message then streams;
  `playDemo` reveals new member lines first (room without trailing agent message), then
  thinking, then the agent reply. Helpers: `appendOptimisticMessage`,
  `roomWithoutTrailingAgent`, `memberRevealMs`.
- `components/room/RoomMessageList.tsx` — `ReasoningPanel` is user-toggleable, opens by
  default for the latest agent message, re-keyed latest/older so it re-collapses when
  superseded.

### Tests / specs
- `tests/test_tools/test_collaborative_room.py` — +3 tests (no-key scripted reply, valid
  patch + reasoning attach, no-agent-reply fallback).
- `spec/backend/collaborative-room-contract.md` — listed the two SSE routes.
- `spec/backend/quality-guidelines.md` — recorded the CJK-width E501 + dev-tool runner gotchas.

## Verification
- Backend: `ruff check` clean · `ruff format --check` clean · `pytest` 84 passed.
- Frontend: `tsc --noEmit` 0 · `eslint` 0.

## Residual risks (surfaced to user)
1. Streamed reasoning uses the primary provider only (`get_model(order[0])` for `astream`);
   a primary failure falls back to scripted, not to the secondary LLM. Fine for the
   Gemini-primary demo.
2. Mid-stream SSE drop after the server committed the user message → the non-streaming
   fallback re-appends it. Accepted for in-memory demo scope (commented in `sendMessage`).
3. Auto-demo "member before any thinking" is only strict for interactive send; in the demo
   the "正在思考" bubble shows during the LLM wait, then member→agent reveal. Manual visual check.

## Next
- Phase 3.4 commit (pending user confirmation), then `/trellis:finish-work`.
