# Check

## Product Checks

- [x] Room still opens cleanly in idle state.
- [x] Without LLM keys, auto demo still progresses through existing scripted stages.
- [x] With a valid RoomPatch, room messages/memory/option copy can differ from the fixed script.
- [x] LLM cannot introduce unknown speaker IDs, plan IDs, or venue IDs.
- [x] A/B/C cards remain backed by trusted PlanCanvasState.
- [x] Final execution still uses mock booking/confirmation rules.
- [x] User-visible UI does not expose raw technical tokens.

## Command Checks

- [x] `cd backend && .venv/bin/python -m pytest`
- [x] `cd backend && .venv/bin/python -m ruff check app tests`
- [x] `cd frontend && npm run lint`
- [x] `cd frontend && npx tsc --noEmit`
- [x] `cd frontend && npm run build`

## Git

- [x] `git status --short`
- [x] `git diff --stat`
- [x] Commit created.

## Evidence

- Backend tests include no-key fallback, valid patch application, invalid speaker fallback, invalid venue fallback, concurrent advance serialization, invalid JSON rejection, and plan-copy/consensus/final-share updates.
