# Room Thinking Ordering & Live Reasoning PRD

## Problem

In the hybrid collaborative room, the agent "正在思考" (thinking) indicator behaves wrong in two ways:

1. **Ordering** — The triggering member message does not appear before "正在思考".
   - Interactive send (`/message`): `useRoom.sendMessage` flips `isAgentThinking` on *before* the user's own message is shown; the backend `add_room_message` returns `[user message + agent reply]` in one shot, so the user sees `正在思考 → (member message + agent reply appear together)`.
   - Auto demo (`playDemo` + `advance_room_agentic_stream`): a whole turn's `[member messages + agent message]` arrives only at the `done` event, so members also surface *after* thinking.

2. **Reasoning visibility** — During "正在思考" the reasoning is not visible; it flashes only near the end then disappears.
   - The model spends most of the wait on hidden thinking (`reasoning_effort="low"`), emitting no streamable `content`; the visible reasoning prefix arrives just before the JSON.
   - On `done`, `playDemo`'s `finally` immediately clears `liveReasoning`/`isAgentThinking`, and the final reasoning lands in a **default-collapsed** "思考过程" panel — so it appears to vanish.

## Goal

For **both** flows, the perceived sequence must be:

```
member/user message  →  正在思考 (reasoning visible, streaming)  →  agent reply (reasoning stays visible)
```

User decisions (confirmed):
- Fix **both** the auto-demo stream flow and the interactive send flow.
- Route the interactive `/message` send through the **streaming LLM** so its reasoning is genuine and visible (accepting ~7-9s latency; falls back to the scripted reply when no LLM key / on failure).

## Core Requirements

- Interactive send optimistically shows the user's own message immediately, before the thinking bubble.
- Interactive send streams the agent's reasoning live via SSE and applies a validated `RoomPatch`, reusing the existing `stream_room_patch` + validation + fallback path.
- No LLM key / provider failure on interactive send falls back to the existing deterministic agent reply and still resolves cleanly.
- The streamed reasoning stays visible after the turn: the just-produced agent message's "思考过程" panel is shown expanded (not collapsed), so it does not appear to disappear.
- Auto demo reveals member messages first, then the thinking + reasoning, then the agent message.
- Existing `RoomState` contract, trusted POI facts, voting rules, and scripted fallback are unchanged. No new raw technical tokens leak to the UI.

## Non-goals

- Real accounts / multiplayer concurrency / persistence.
- Changing the deterministic plan/venue/consensus facts.
- Making the model's *hidden* chain-of-thought visible (only the agent's visible reasoning prefix is shown).
- Reworking the `chat | plans | final` surface.

## Definition of Done

- `POST /api/room/{room_id}/message/stream` exists, commits the user message first, streams `reasoning` deltas, then emits `done` with the full room; falls back to the scripted reply safely.
- `useRoom.sendMessage` is optimistic + streaming; `playDemo` reveals member → thinking → agent.
- The latest agent message shows its reasoning expanded; older ones stay collapsed.
- Backend pytest + ruff pass; frontend `tsc --noEmit` + `next lint` pass.
- Manual check: typing a message shows `my message → 正在思考 (reasoning streams) → agent reply (reasoning still visible)`; same order in auto demo.
