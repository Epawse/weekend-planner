# Plan Canvas Contract

## Scenario: PlanCanvasState API Contract

### 1. Scope / Trigger

- Trigger: backend emits a new cross-layer `plan_canvas` payload consumed by frontend workbench components.
- Applies to: `plan_ready`, `all_complete`, and `/api/plan/feedback`.
- Goal: keep the frontend reading one user-facing plan contract instead of reconstructing scattered `plan`, `evidence`, `checks`, and `mapData` fields.

### 2. Signatures

- `build_plan_canvas(state: dict, plan: dict, session_id: str = "", status: str = "plan_ready", modification_notice: str | None = None) -> dict`
- `POST /api/plan/feedback`

Feedback request:

```json
{
  "session_id": "thread id",
  "message": "不要火锅",
  "quick_action": "不要火锅"
}
```

Feedback response:

```json
{
  "session_id": "thread id",
  "message": "已根据你的反馈调整...",
  "plan": {},
  "plan_canvas": {}
}
```

### 3. Contracts

`plan_canvas` must include:

- `canvas_id`
- `scenario`
- `status`
- `title`
- `summary`
- `metrics`
- `timeline`
- `checks`
- `evidence_cards`
- `rejected_options`
- `map`
- `feedback`
- `tool_tasks`
- `pending_actions`
- `execution_results`
- `share_text`

`feedback` must include:

- `quick_actions`
- `history`
- `change_summary` for the latest applied follow-up, or `null`.

`feedback.change_summary` must be user-facing and should include:

- `title`
- `result`
- `before`
- `after`
- `preserved`
- `changed`
- `note`

`pending_actions` and `execution_results` must use `ExecutionAction` with:

- `id`
- `label`
- `status`
- `target`
- `detail`
- `confirmation`
- `scheduled_time`
- `party_size`
- `note`
- `next_step`

User-facing fields must use:

- `display_name`
- `user_description`
- `source_label`
- `route_notice`
- `fit_label`

Raw/debug fields must not be displayed by default:

- `mock`
- `showcase_curated`
- `fallback_generated`
- `typecode`
- `source=`
- `raw_source`
- `debug`
- `POI来源为`

### 4. Validation & Error Matrix

- Missing current plan in feedback state -> HTTP 400 `No current plan to modify for this session`.
- Unsupported feedback text -> conservative distance intent fallback.
- Tool/business raw source -> map through `source_label` and scrub details.
- Route source absent or not `amap` -> route notice must say it is a sequence estimate.
- Feedback with no better replacement -> preserve current plan and explain the no-change rationale in `feedback.change_summary.note`.
- Existing `plan` fields remain in SSE payload for backward compatibility.

### 5. Good/Base/Bad Cases

- Good: `plan_ready` contains both old `plan` and new `plan_canvas`; frontend renders Canvas from `plan_canvas`.
- Base: if `plan_canvas` is missing, frontend may fall back to old `PlanCard`.
- Bad: frontend manually combines `family_checks`, `friend_checks`, raw `evidence`, and `mapData` as primary display.

### 6. Tests Required

- Build PlanCanvasState for family.
- Build PlanCanvasState for friends.
- Assert user-visible Canvas text does not contain forbidden raw tokens.
- Assert timeline items have `display_name`, `user_description`, `map_marker_id`, and `evidence_ids`.
- Assert feedback cases rebuild Canvas:
  - closer
  - indoor
  - cuisine exclusion
  - earlier home
- Assert pending/execution actions are available for Canvas rendering.
- Assert feedback exposes before/after `change_summary`.
- Assert execution actions include transactional details where available.

### 7. Wrong vs Correct

#### Wrong

```python
writer({"type": "plan_ready", "data": {"plan": plan, "evidence": raw_evidence}})
```

This forces the frontend to understand raw backend evidence and source labels.

#### Correct

```python
plan_canvas = build_plan_canvas(state, plan, session_id=session_id)
writer({"type": "plan_ready", "data": {"plan": plan, "plan_canvas": plan_canvas}})
```

The frontend reads `plan_canvas` as the primary user-facing contract and uses old `plan` only as fallback.
