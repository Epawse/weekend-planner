# Implementation Plan

## Phase 0: Context
- Read specs in implement.jsonl (collaborative-room-contract, llm-provider, hook-guidelines, state-management, cross-layer guide).
- Confirm streaming SSE shape matches existing `/advance/stream`.

## Phase 1: Backend — separable ingest + streaming message
- Refactor `room.py`: extract `_ingest_user_message` and `_scripted_agent_reply` out of `add_room_message`; keep `add_room_message` behavior identical.
- Add `add_room_message_stream` async generator (reasoning deltas → apply patch → done), reusing `stream_room_patch`, `_validate_room_patch`, `_apply_room_patch`, `_refresh_room`, lock.
- Add `POST /api/room/{room_id}/message/stream` SSE route in `routes.py` mirroring `/advance/stream`.

## Phase 2: Frontend — api + types
- Add `streamRoomMessage` generator in `lib/api.ts` (reuse the SSE reader from `streamAdvanceRoom`).
- No new types needed (reuses `RoomStreamEvent`); confirm `SharedMessage.reasoning` exists in `lib/types.ts`.

## Phase 3: Frontend — useRoom
- Rewrite `sendMessage`: optimistic user message + streaming + fallback.
- Add a small helper to build an optimistic `SharedMessage`.
- Rework `playDemo` done-handling into the two-commit member→thinking→agent reveal.

## Phase 4: Frontend — RoomMessageList
- Open the reasoning panel for the latest agent message only (`ReasoningPanel` gains a `defaultOpen` prop).

## Phase 5: Verify
- Backend: `pytest` (esp. existing room tests still green; add no-key fallback test for the stream message path), `ruff check`/`ruff format`.
- Frontend: `tsc --noEmit`, `next lint`.
- Manual: send a message → order + visible/persistent reasoning; auto demo → same order.
- Update progress.md / check, then stop for review.
