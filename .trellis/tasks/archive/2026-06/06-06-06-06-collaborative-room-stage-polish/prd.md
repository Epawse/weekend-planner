# PRD

## Goal

Upgrade the existing Mock Collaborative Room from a fully-expanded script page into a staged, demo-ready Collaborative AI Mode.

The room must feel like a collaboration that is happening now:

- idle room on first load.
- host prompt starts the workflow.
- members appear to type before their messages arrive.
- Agent responses reference concrete member feedback.
- A/B/C options appear before voting and consensus.
- final Plan Canvas appears after consensus.
- host execution closes the loop.

## Users

- Friends scenario: 小红 invites 小绿 / 小蓝 / 小粉 to plan a group afternoon.
- Family scenario: host plans with 老婆 feedback and a child profile constraint.

## Core Scenarios

- Start from a clean collaborative room.
- Switch between friends and family demos.
- Play a staged automatic demo.
- Send a host prompt manually.
- Show typing indicators and stage progression.
- Show A/B/C options, votes, group memory, final Plan Canvas, and execution results at the right stage.
- Keep map/evidence tied to the active option or final plan.

## Non-Goals

- Real accounts.
- Database persistence.
- WebSocket conflict handling.
- Complex optimization algorithms.
- Real-time collaborative editing.
- Real payment or real booking.

## Acceptance Criteria

- Initial room does not preload all messages, votes, options, or execution state.
- Middle column has internal scrolling and a sticky composer.
- Automatic demo advances step by step with typing indicators.
- Friends and family scenarios both work.
- Agent copy names specific feedback and consequences.
- A/B/C option stage, voting stage, consensus stage, final plan stage, and execution stage are visually distinct.
- Right panel shows a waiting state until a plan exists, then tracks selected option/final plan.
- User-facing UI does not show technical tokens such as `mock`, `showcase_curated`, `fallback_generated`, `typecode`, `debug`, or `raw_source`.
- Backend tests, ruff, frontend lint, tsc, and build pass.
