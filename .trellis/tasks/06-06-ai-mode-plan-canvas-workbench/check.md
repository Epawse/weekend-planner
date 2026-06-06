# Check

## User-Visible Acceptance

- [x] Plan Canvas appears as the central plan surface.
- [x] Left rail is primarily chat, process stream, and quick feedback.
- [x] Right panel has Map and Source tabs.
- [x] Family example input renders a complete Plan Canvas in backend contract tests.
- [x] Friends example input renders a complete Plan Canvas in backend contract tests.
- [x] Main Canvas contract does not show forbidden technical tokens in backend tests:
  - `mock`
  - `mock_api`
  - `showcase_curated`
  - `fallback_generated`
  - `typecode`
  - `source=`
  - `raw_source`
  - `debug`
  - `POI 来源为`
  - `社交适配 100`
- [x] Map markers are clickable in `MapView` implementation.
- [x] VenuePopover displays name, time, reason, source label, business checks, and actions.
- [x] Timeline selection highlights the matching map marker.
- [x] EvidencePanel displays source groups and rejected options.
- [x] EvidencePanel is grouped as a source panel rather than a raw validation log.
- [x] Evidence selection can highlight matching timeline/map items.
- [x] Feedback buttons exist and update the current plan through `/api/plan/feedback`.
- [x] Feedback result shows before/after, preserved items, changed items, and no-change rationale when applicable.
- [x] Confirming a plan displays pending then completed execution actions via Canvas events.
- [x] Execution cards show transactional details including time, party size, notes, next step, and confirmation when available.

## Backend Checks

- [x] PlanCanvasState builder covers family.
- [x] PlanCanvasState builder covers friends.
- [x] Source labels are scrubbed server-side.
- [x] Timeline items have display name, user description, marker id, and evidence ids.
- [x] Feedback closer works.
- [x] Feedback indoor works.
- [x] Feedback cuisine exclusion works.
- [x] Feedback earlier home works.
- [x] Feedback change summary is built and exposed on PlanCanvasState.
- [x] Execution actions are built before and after approval.
- [x] Execution actions include scheduled time, party size, notes, next step, and confirmation fields.

## Frontend Checks

- [x] `PlanCanvas` renders shared family/friends contract.
- [x] `EvidencePanel` renders grouped cards.
- [x] `MapView` marker click opens popover.
- [x] `ToolTaskPanel` renders fan-out tasks.
- [x] `ToolTaskPanel` can render as a collapsed summary to avoid duplicate task-heavy UI.
- [x] `ExecutionActionCard` renders pending and completed states.
- [x] `FeedbackChangeCard` renders feedback before/after.

## Commands

Final commands to run:

```bash
cd backend && .venv/bin/python -m pytest
cd backend && .venv/bin/python -m ruff check app tests
cd frontend && npm run lint
cd frontend && npx tsc --noEmit
```

Latest results:

- Backend focused Plan Canvas pytest: 5 passed.
- Backend full pytest: 65 passed.
- Backend ruff: passed.
- Frontend lint: passed.
- Frontend TypeScript: passed.
- Frontend production build from baseline pass: passed after allowing network for Google Fonts.

## Manual Inputs

Family:

```text
今天下午想和老婆孩子去亲子乐园玩4到6个小时，孩子5岁，老婆最近减肥，别离家太远，少走路少排队。
```

Friends:

```text
今天下午4个朋友聚会，有吃有玩，别太远，适合聊天拍照，吃完还能续摊。
```

Feedback:

```text
太远了
换室内
不要火锅
早点回家
```
