# Design

## Room Stage Contract

Add a lightweight stage machine to `RoomState`:

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
executing
done
```

`RoomState` also carries:

- `typing_participants`
- `available_scenarios`
- `demo_step_index`
- `stage_title`
- `stage_description`

The room remains an in-memory demo store.

## Scenario Model

Friends:

- participants: 小红, 小绿, 小蓝, 小粉, Agent.
- A/B/C options: 体验优先, 折中推荐, 稳妥备选.
- final recommendation: B 折中推荐.

Family:

- participants: 小明, 老婆, 孩子, Agent.
- child is a profile participant and not a voting account.
- A/B/C options: 亲子体验优先, 早点回家优先, 雨天室内备选.
- final recommendation keeps child suitability, clear meal, child seat, low walking, early return.

## API

Keep existing endpoints and add demo progression:

- `POST /api/room/{room_id}/advance`
- `POST /api/room/{room_id}/scenario`

Reset accepts an optional scenario and returns an idle room.

`simulate` remains a one-call full demo fallback, but the frontend demo button should call `advance` repeatedly with short delays.

## Frontend

Layout:

```text
RoomSidebar | CollaborativeThread | RightPanel
```

Middle column:

```text
Header
ThreadScrollArea
StickyComposer
```

The thread renders progressively based on `room.stage`:

- idle: empty state and example prompt.
- host/typing: messages plus typing rows.
- options: option cards.
- voting/consensus: group memory and voting explanation.
- final: embedded Plan Canvas.
- done: Plan Canvas execution results.

Right panel:

- no plan: waiting state.
- plan present: map/source tabs with label "当前显示：A/B/C/最终方案".

## Data Reuse

Do not replace `PlanCanvasState`. Each PlanOption still wraps a full canvas. The staged room only decides when each object is visible.
