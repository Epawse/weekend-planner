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
- `POST /api/room/{room_id}/reset?user=red&scenario=friends`
- `POST /api/room/{room_id}/scenario`
- `POST /api/room/{room_id}/advance?user=red`
- `POST /api/room/{room_id}/message`
- `POST /api/room/{room_id}/vote`
- `POST /api/room/{room_id}/reaction`
- `POST /api/room/{room_id}/simulate?user=red`
- `POST /api/room/{room_id}/execute`

## Models

`RoomState` wraps:

- `stage`
- `stage_title`
- `stage_description`
- `typing_participants`
- `demo_step_index`
- `available_scenarios`
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

## Stage Rules

Default `GET` and `reset` return an idle room:

- no messages.
- no plan options.
- no votes.
- no reactions.

The staged demo advances one visible event at a time through `/advance`:

```text
idle
host_prompted
agent_planning
members_invited
members_typing
opinions_collected
options_ready
voting
consensus_ready
final_plan_ready
done
```

The frontend may call `/advance` repeatedly with short delays to create a stable "collaboration is happening now" demo. `simulate` remains a full-script fallback for tests and manual smoke checks.

## Demo Rules

- `red` is the host and the only participant who can execute.
- `green` prefers indoor and quiet.
- `blue` excludes hotpot and prefers moderate budget.
- `pink` prefers photo-friendly venues and after-dinner coffee.
- `plan_b` is the default consensus plan.
- Voting signals are exposed as user-facing evidence with `source_label = "投票信号"`.

Family scenario:

- `red` is displayed as 小明.
- `wife` provides clear/light meal and early-return feedback.
- `child` is a profile participant, not a voting account.
- `plan_b` is the default family recommendation because it balances child suitability, light meal, child seat, low walking, and early return.

## Validation

Room UI and API responses must not expose raw technical tokens:

- `showcase_curated`
- `fallback_generated`
- `typecode`
- `source=`
- `raw_source`
- `debug`

## Tests Required

- Reset returns idle without preloaded script data.
- Advance shows staged messages and typing indicators.
- Simulate builds deterministic demo room with three plan options.
- Vote updates supporters and consensus.
- Reaction updates voting signal evidence.
- Family scenario exposes wife feedback and child constraints.
- Simulate applies stable demo script.
- Execute is host-only and updates active plan canvas execution results.
- Unknown active user falls back to `red`.
