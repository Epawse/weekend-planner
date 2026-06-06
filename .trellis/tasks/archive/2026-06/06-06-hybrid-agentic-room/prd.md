# Hybrid Agentic Room PRD

## Goal

Upgrade the collaborative room from a fixed staged script into a Hybrid Agentic Room:

- Keep the deterministic room state machine, trusted POI facts, PlanCanvasState, voting rules, map/evidence hydration, and mock execution.
- Let the LLM generate a validated RoomPatch containing short visible messages, memory deltas, plan copy updates, consensus explanation, and final/share copy.
- Preserve the current stable scripted demo as fallback for no-key, provider failure, invalid JSON, or semantic validation failure.

## Users

- Friends planning a group meetup with different preferences.
- Family planning a child-friendly outing where the spouse confirms practical constraints.

## Core Requirements

- Each `/api/room/{room_id}/advance` uses at most one LLM call in agentic mode.
- LLM never generates full `RoomState` or `PlanCanvasState`.
- LLM never invents POIs, coordinates, route data, source evidence, bookings, or confirmation codes.
- Backend validates every LLM patch through Pydantic and business rules before applying it.
- No LLM key or failed LLM must fall back to the current deterministic staged flow.
- Existing `chat | plans | final` frontend structure remains the product surface.

## Non-goals

- Real accounts.
- Real multiplayer concurrency or WebSocket synchronization.
- Database persistence.
- LLM-created coordinates, route geometry, evidence IDs, payment, or real booking.
- Multi-call persona-agent orchestration per step.

## Definition of Done

- `RoomPatch` schemas exist and validate LLM output.
- `llm_room_agent.py` calls the existing LLM fallback provider and repairs malformed JSON once.
- `advance_room_agentic` exists and is wired from the Room API.
- Scripted demo remains the fallback and remains green without LLM API keys.
- Agentic patches can update messages, dynamic group memory, A/B/C option copy, consensus text, and final/share text.
- Invalid JSON and invalid plan/venue/speaker references fall back safely.
- Per-room async lock prevents concurrent advance step corruption.
- Tests cover no-key fallback, invalid JSON fallback, invalid semantic patch fallback, and concurrent advance.
- Backend pytest and ruff pass; frontend lint and TypeScript pass if frontend surface changes.

