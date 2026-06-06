# Check

## Product Checks

- [x] Idle state is centered and chat-first.
- [x] Chat mode does not show full A/B/C cards.
- [x] Compact plan-ready card appears after options are generated.
- [x] Plans mode shows A/B/C cards, voting, reactions, and why-recommended section.
- [x] Final mode shows final itinerary and execution actions.
- [x] Right panel is hidden until plan view/final view.
- [x] Family and friends flows still work.
- [x] User-facing copy avoids debug/backend language in primary chat.

## Command Checks

- [x] `cd backend && .venv/bin/python -m pytest`
- [x] `cd backend && .venv/bin/python -m ruff check app tests`
- [x] `cd frontend && npm run lint`
- [x] `cd frontend && npx tsc --noEmit`
- [x] `cd frontend && npm run build`

## Smoke Checks

- [x] Frontend responds.
- [x] Room API idle and advance respond.
- [x] Demo rooms reset to idle after smoke.
