# Check

## User-Visible Acceptance

- [x] Left rail is a collaboration room sidebar.
- [x] Center rail contains multiplayer conversation, group memory, plan options, and active Plan Canvas.
- [x] Right rail continues to show map/source tabs for the active plan.
- [x] Current user follows `?user=red|green|blue|pink`.
- [x] Plan A/B/C are visibly different.
- [x] Plan votes display participant avatars.
- [x] Venue reactions display participant avatars/reasons.
- [x] Group memory explains constraints, preferences, conflicts, and history.
- [x] Source panel includes voting signals.
- [x] Host can execute the active plan.
- [x] Execution result shows booking/table/share details.
- [x] Main UI does not show forbidden technical tokens in tested room payload.

## Backend Checks

- [x] RoomState builds deterministic demo room.
- [x] Message endpoint adds a participant message and updates memory.
- [x] Vote endpoint updates vote summary and consensus.
- [x] Reaction endpoint updates reactions and voting evidence.
- [x] Simulate endpoint applies the full demo script.
- [x] Execute endpoint updates active plan canvas execution results.

## Latest Results

- Backend collaborative room pytest: 6 passed.
- Backend full pytest: 71 passed.
- Backend ruff: passed.
- Frontend TypeScript: passed.
- Frontend lint: passed.
- Frontend production build: passed after allowing network for Google Fonts.
- Local backend health: passed at `http://127.0.0.1:8000/api/health`.
- Local room API: passed for `demo_friends_room?user=blue`.
- Local frontend response: passed at `http://127.0.0.1:3000`.

## Commands

```bash
cd backend && .venv/bin/python -m pytest
cd backend && .venv/bin/python -m ruff check app tests
cd frontend && npm run lint
cd frontend && npx tsc --noEmit
```

## Manual Demo

Open:

```text
http://localhost:3000/?room=demo_friends_room&user=red
http://localhost:3000/?room=demo_friends_room&user=blue
```

Use:

1. Click simulate.
2. Vote on B.
3. React to a venue.
4. Execute as red.
