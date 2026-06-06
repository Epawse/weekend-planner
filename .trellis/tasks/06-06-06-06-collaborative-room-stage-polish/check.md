# Check

## User-Visible Checks

- [x] Initial page shows an idle room, not a completed script.
- [x] Automatic demo reveals messages, typing, options, votes, consensus, and final plan in stages.
- [x] Composer remains visible at the bottom of the middle column.
- [x] Friends scenario supports A/B/C option voting and final B recommendation.
- [x] Family scenario is available and includes wife feedback plus child constraints.
- [x] Agent messages cite specific member feedback.
- [x] Map/source panel waits before plans exist and follows selected plan afterward.
- [x] No technical tokens appear in default UI contract tests.

## Command Checks

- [x] `cd backend && .venv/bin/python -m pytest`
- [x] `cd backend && .venv/bin/python -m ruff check app tests`
- [x] `cd frontend && npm run lint`
- [x] `cd frontend && npx tsc --noEmit`
- [x] `cd frontend && npm run build`

## Manual/API Checks

- [x] `GET /api/room/demo_friends_room?user=red` returns `stage=idle`.
- [x] `POST /api/room/demo_friends_room/advance` progresses the stage.
- [x] `POST /api/room/demo_family_room/scenario` switches to family.
- [x] Host execution produces execution results in backend tests.
