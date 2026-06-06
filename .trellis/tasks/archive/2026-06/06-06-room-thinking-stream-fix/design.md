# Design

## Sequence (target, both flows)

```text
member/user message committed + visible
  -> 正在思考 bubble (live reasoning streams in, stays visible)
  -> agent reply revealed (carries an expanded 思考过程 panel)
```

## Backend

Refactor `add_room_message` so user-message ingestion is separable from the agent reply:

- `_ingest_user_message(room, actor_id, content)` — append the user message, set typing, do the idle→agent_planning stage transition and `_apply_text_preference`. No agent reply.
- `_scripted_agent_reply(room, actor_id, content)` — the existing canned agent copy (idle start vs member feedback).
- `add_room_message(...)` — unchanged behavior = ingest + scripted reply + refresh (kept for fallback + existing tests).

New streaming service fn:

- `async add_room_message_stream(room_id, actor_id, content) -> AsyncGenerator[dict]`
  1. Under the room lock: `_ingest_user_message` (commit user msg, transition stage).
  2. If LLM available: `stream_room_patch(deepcopy(room))` → yield `{"type":"reasoning","delta":...}`; validate + `_apply_room_patch` + `_refresh_room(dynamic=True)` + bump version.
  3. On no-LLM / failure: append `_scripted_agent_reply` and `_refresh_room`.
  4. Yield `{"type":"done","room": serialized}`.

New route mirroring `/advance/stream`:

- `POST /api/room/{room_id}/message/stream` — SSE; emits `reasoning` events then one `done` event. Delegates to `add_room_message_stream`. Business logic stays in the service (no logic in the route).

`stream_room_patch` already attaches `patch.reasoning` to the agent message; `_apply_room_patch` already surfaces it as `message["reasoning"]`. No change needed there.

## Frontend

### api.ts
- Add `streamRoomMessage(roomId, actorId, content)` async generator, reusing the same SSE parsing as `streamAdvanceRoom`, yielding `RoomStreamEvent` (`reasoning` | `done`).

### useRoom.ts — `sendMessage` (optimistic + streaming)
- Build an optimistic user message (`optimistic_<ts>` id) and append it to `room.messages` immediately → member shows first.
- `setIsAgentThinking(true)`, `setLiveReasoning("")`.
- Stream `streamRoomMessage`: accumulate `reasoning` into `liveReasoning`; capture `done.room`.
- Commit `setRoom(serverRoom)` (canonical; replaces the optimistic msg, agent reply carries reasoning), then clear thinking/liveReasoning.
- Transport error → fall back to non-streaming `sendRoomMessage` so send never stalls.

### useRoom.ts — `playDemo` (member → thinking → agent reveal)
- Per step: stream as today, accumulating `liveReasoning` and capturing `nextRoom`.
- On `done`, reveal in two commits so members land before the thinking bubble:
  1. Commit `nextRoom` **without the trailing agent message(s)** (slice them off) → members type out while `isAgentThinking` + reasoning show *below* them.
  2. After a short beat, commit the full `nextRoom` → agent message types out; clear thinking/liveReasoning.
- The standalone thinking bubble renders at the list bottom (after visible members), so the order reads member → thinking → agent.

### RoomMessageList.tsx — reasoning persistence
- Compute the id of the **last** agent message; render its `ReasoningPanel` expanded (`defaultOpen`); older agent messages stay collapsed.
- Keeps the reasoning the user just watched visible instead of vanishing into a collapsed panel.

## Fallback & Safety
- All LLM failures on the streaming message path fall back to the deterministic reply and still emit `done`.
- Patch validation (speaker/plan/venue ids) is unchanged and still gates application.
- No raw tokens added to user-facing copy.
