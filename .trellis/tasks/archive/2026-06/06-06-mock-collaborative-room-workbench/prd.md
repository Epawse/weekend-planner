# PRD

## Goal

Upgrade Weekend Planner AI Mode from a single-user Plan Canvas workbench into a stable, demo-ready mock collaborative room.

The product should show that the Agent can help a group express preferences, vote, resolve conflicts, select a consensus plan, and execute the final arrangement.

## Users

- Host: starts the room, invites members, confirms execution.
- Friends: join the room, send preferences, vote on plans, react to venues.
- Agent: summarizes group intent, turns votes/reactions into constraints, recommends a consensus plan, and explains tradeoffs.

## Core Scenario

Friends room:

1. Red starts a friends gathering.
2. Green, Blue, and Pink join.
3. The Agent generates three plan options:
   - A: best experience.
   - B: consensus plan.
   - C: lowest risk.
4. Members vote and react to venues.
5. The Agent explains group memory and recommends the consensus plan.
6. Host confirms execution.
7. The UI displays reservation, table booking, notes, route, and share copy.

## Non Goals

- Real accounts.
- Database persistence.
- WebSocket conflict handling.
- Real multi-user editing.
- Real payment or Meituan production booking.
- Complex optimization algorithms.

## Acceptance

- Three-column layout becomes:
  - left: room sidebar.
  - center: collaborative conversation plus Plan Canvas and plan options.
  - right: map/source/detail.
- `RoomState` exists as a backend contract wrapping existing `PlanCanvasState`.
- `GET /api/room/{room_id}` returns the demo room.
- `POST /api/room/{room_id}/message`, `/vote`, `/reaction`, `/simulate`, `/execute` update the room state.
- Query parameter `?user=red|green|blue|pink` controls the active participant in the UI.
- Plan A/B/C have visibly different positioning and scores.
- Votes and reactions are visible as avatars.
- Group memory lists confirmed constraints, soft preferences, conflicts, and history.
- Source panel includes a user-facing voting signal source.
- Host execution shows transaction-style execution cards.
- Main UI does not expose technical tokens such as `mock`, `showcase_curated`, `fallback_generated`, `typecode`, `debug`, or `raw_source`.
