# PRD

## Goal

Turn Collaborative AI Mode from a state-rich demo panel into a product-shaped planning assistant.

The experience should follow:

```text
Chat Mode -> Plan Mode -> Final Mode
```

Default use should feel like a natural AI conversation. Structured plans, evidence, voting, and execution should appear only when the user asks to inspect or the workflow reaches that stage.

## Users

- Friends planning: organizer plus friends with different preferences.
- Family planning: host plus wife confirmation and child profile constraints.

## Requirements

- Add `activeView: chat | plans | final`.
- Chat is default.
- Idle state has centered headline, prompt examples, and a large AI-style input.
- Chat mode only shows lightweight messages, typing indicators, progress, and a compact "3 plans ready" entry card.
- Full A/B/C cards move to Plan Mode.
- Final execution page moves to Final Mode.
- Right panel is hidden or lightweight until a plan is available and selected.
- Agent messages sound like an assistant, not backend logs.
- Automatic demo playback uses varied delays so mock collaboration feels paced.
- Keep existing backend room contract and PlanCanvasState.

## Non-Goals

- Real realtime collaboration.
- New backend optimization logic.
- New external APIs.
- Payment or production booking.

## Acceptance Criteria

- First load looks like an AI planning product, not a completed script.
- User can move between Chat, Plans, and Final.
- In Chat, A/B/C are represented by a compact card, not full cards.
- In Plans, A/B/C cards, vote, reactions, consensus, and why-recommended evidence are available.
- In Final, the final Plan Canvas and execution actions are prominent.
- Family and friends still work.
- Frontend lint, tsc, build, backend tests, and ruff pass.
