# Design

## Architecture

Keep `PlanCanvasState` as the single-plan contract. Add `RoomState` as a collaborative shell:

```text
RoomState
  participants
  messages
  group_memory
  plan_options[]
    PlanCanvasState
  votes
  reactions
  active_plan_id
  consensus
  execution_state
```

Single-user endpoints remain unchanged. Collaborative demo uses `/api/room/*`.

## Backend Contract

New models live in `backend/app/models/room.py`.

Key models:

- `Participant`
- `SharedMessage`
- `PlanOption`
- `Vote`
- `Reaction`
- `GroupMemory`
- `ConsensusState`
- `RoomExecutionState`
- `RoomState`

Room service lives in `backend/app/services/room.py`.

The room store is process memory:

```text
room_id -> RoomState
```

This follows the hackathon persistence guideline and avoids account/database/websocket scope.

## Demo Room

Default room id:

```text
demo_friends_room
```

Participants:

- `red`: 小红, host, distance/efficiency.
- `green`: 小绿, indoor/quiet.
- `blue`: 小蓝, no hotpot/budget.
- `pink`: 小粉, photo/coffee.

Plan options:

- `plan_a`: 最优方案, best photo/experience, includes higher queue/risk.
- `plan_b`: 折中方案, active recommendation, excludes hotpot and balances the group.
- `plan_c`: 备选方案, full indoor / low risk / optional tail.

Each option wraps a full `PlanCanvasState`.

## Group Rules

Deterministic demo-safe rules:

- Any cuisine veto becomes a confirmed constraint.
- Majority vote chooses the active plan unless it violates a veto.
- Indoor preference increases consensus score for indoor options.
- Photo preference preserves photo-friendly activity.
- Early-home conflict makes the tail optional instead of removing the main plan.

## Frontend

Main page becomes:

```text
RoomSidebar | CollaborativeThread + PlanCanvas | Map/Evidence
```

New components:

- `RoomSidebar`
- `CollaborativeThread`
- `PlanOptionCards`
- `GroupMemoryPanel`
- `RoomMessageList`
- `VenueReactionBar`

New hook:

- `useRoom`

`useRoom` fetches `/api/room/{room_id}` and updates room via POST endpoints. Polling can be added, but initial demo can refresh after each action and provide a simulate button.

## Map And Evidence

The right panel reads the active plan option's `plan_canvas`.

Evidence panel receives `voting_signal` source cards as normal `evidence_cards` with `source_label = "投票信号"`.

## Execution

Only host can execute. UI can show non-host disabled copy.

`POST /api/room/{room_id}/execute` updates the active plan canvas with `execution_results` and `execution_state`.

## Migration

Keep old Plan Canvas workbench behavior available as fallback while the demo room loads. The collaborative room uses the same `PlanCanvas`, `EvidencePanel`, and `MapView` components.
