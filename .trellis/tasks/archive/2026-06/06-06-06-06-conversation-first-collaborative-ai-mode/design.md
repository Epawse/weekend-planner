# Design

## View State

`activeView` is frontend UI state:

- `chat`: natural conversation and compact result entry.
- `plans`: A/B/C plan comparison, voting, group memory, venue reactions.
- `final`: final itinerary and execution.

The backend remains the source of truth for room state. `activeView` only controls presentation.

## Layout

Desktop:

```text
RoomSidebar | MainView | OptionalRightPanel
```

Right panel is visible when a selected plan exists and the user is in `plans` or `final`.

Chat mode:

- no full plan cards.
- centered idle hero.
- thread scroll area.
- composer width constrained to 720-880px.

Plan mode:

- PlanOptionCards.
- collapsible "why recommended" group memory/evidence section.
- venue reactions.
- right map/source follows selected plan.

Final mode:

- final summary.
- embedded PlanCanvas.
- execution actions and host confirmation.

## Copy

Assistant copy should be product-facing:

- say "我先帮你们收一下偏好".
- say "我找到了 3 个方向".
- avoid "规则推断", "来源校验", "第 1 步" in primary chat.

Structured evidence remains in right panel or folded "为什么推荐".

## Staged Playback

`useRoom.playDemo` keeps calling `/advance`, but delay is varied by stage:

- typing: longer.
- planning: medium.
- option/final: short.

This is still deterministic enough for demo but feels less like instant script playback.
