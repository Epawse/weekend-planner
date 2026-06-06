# Collaborative Room Contract

## Scope

The collaborative room is a demo-ready shell around existing `PlanCanvasState`.

It is intentionally not a production multiplayer system:

- no accounts.
- no database persistence.
- no WebSocket conflict handling.
- no real-time edit merge.

The room store is an in-memory process dictionary for hackathon demo scope.

## API

- `GET /api/room/{room_id}?user=red`
- `POST /api/room/{room_id}/reset?user=red`
- `POST /api/room/{room_id}/message`
- `POST /api/room/{room_id}/vote`
- `POST /api/room/{room_id}/reaction`
- `POST /api/room/{room_id}/simulate?user=red`
- `POST /api/room/{room_id}/execute`

## Models

`RoomState` wraps:

- `participants`
- `messages`
- `group_memory`
- `plan_options`
- `active_plan_id`
- `votes`
- `reactions`
- `consensus`
- `execution_state`

Each `PlanOption` wraps a complete `PlanCanvasState`.

## Demo Rules

- `red` is the host and the only participant who can execute.
- `green` prefers indoor and quiet.
- `blue` excludes hotpot and prefers moderate budget.
- `pink` prefers photo-friendly venues and after-dinner coffee.
- `plan_b` is the default consensus plan.
- Voting signals are exposed as user-facing evidence with `source_label = "投票信号"`.

## Validation

Room UI and API responses must not expose raw technical tokens:

- `showcase_curated`
- `fallback_generated`
- `typecode`
- `source=`
- `raw_source`
- `debug`

## Tests Required

- Build deterministic demo room with three plan options.
- Vote updates supporters and consensus.
- Reaction updates voting signal evidence.
- Simulate applies stable demo script.
- Execute is host-only and updates active plan canvas execution results.
- Unknown active user falls back to `red`.
