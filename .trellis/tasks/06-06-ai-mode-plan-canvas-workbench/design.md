# Design

## PlanCanvasState

Backend emits `plan_canvas` as the user-facing plan contract. It is built from current `PlannerState` and canonical `plan` through `build_plan_canvas(state, plan, session_id?, status?)`.

Core fields:

- `canvas_id`: stable per session/plan.
- `scenario`: `family` or `friends`.
- `status`: `plan_ready`, `executing`, `done`, or `feedback_applied`.
- `title`, `summary`: user-facing text.
- `metrics`: duration, travel time, end time, fit label, route label.
- `timeline`: normalized plan steps with timeline id, map marker id, display text, schedule, evidence links, and action labels.
- `checks`: grouped `passed`, `warnings`, `failed`.
- `evidence_cards`: user-friendly evidence with `source_label`, subject, detail, and related ids.
- `rejected_options`: user-friendly rejected options.
- `map`: home marker, selected venue markers, route GeoJSON, route notice.
- `feedback`: quick actions and history.
- `feedback.change_summary`: latest follow-up before/after explanation with preserved items, changed items, and no-change rationale.
- `tool_tasks`: Local-life fan-out task statuses.
- `pending_actions`: execution actions before approval.
- `execution_results`: execution actions after approval.
- `share_text`: share copy.

Debug fields may exist only inside a nested `debug` object and must not be rendered by default.

## Product Boundary

This workbench is an execution-oriented Agent, not a normal recommender.

- Not search recommendation: it decomposes a goal into activity, dining, optional tail, route, availability, evidence, feedback, and execution tasks.
- Not LLM free-form planning: final UI is built from `PlanCanvasState`, with map/tool/rule/business evidence and scrubbed user fields.
- Not a one-shot answer: feedback applies constraint deltas to the current plan and shows before/after impact.
- Not blind POI trust: user-facing evidence is grouped by source type and rejected options explain why alternatives were excluded.
- Not a fake “done”: approval produces execution actions with target, time, party size, notes, confirmation code, and next step where available.

## Source Label Policy

Raw sources are mapped server-side:

- `amap_real_poi`, `real_api` -> `真实地图数据`
- `showcase_curated` -> `精选演示数据`
- `mock_business_api`, `mock_api`, `mock_availability` -> `演示业务接口`
- `keyword_rule`, `category_rule`, `llm` -> `规则推断`
- `fallback_generated` -> `系统备选建议`

User-facing strings are scrubbed for raw tokens including `mock`, `showcase_curated`, `fallback_generated`, `typecode`, `source=`, `raw_source`, `debug`, and `POI来源`.

## Frontend Workbench

Desktop:

```text
AppShell
├── ChatControlPanel
├── PlanCanvas
└── RightPanel
    ├── Map tab
    └── 来源 tab
```

Narrow screens use tabs/stacking but keep the Canvas as the primary plan surface.

## Components

Canvas:

- `PlanCanvas`
- `CanvasHeader`
- `CanvasMetrics`
- `CanvasTimeline`
- `CanvasChecks`
- `ToolTaskPanel`
- `FeedbackBar`
- `ExecutionActionCard`
- `CanvasShareCard`

Evidence:

- `EvidencePanel`
- `EvidenceCard`
- `RejectedOptionCard`

Map:

- Upgrade existing `MapView` to accept `PlanCanvasState`.
- Marker click sets selected marker.
- Timeline/evidence selection feeds selected ids into `MapView`.
- `VenuePopover` displays schedule, reason, source label, business validation, and actions.

## FeedbackIntent

Supported v1 categories:

- `distance`: closer / route compaction.
- `indoor`: indoor priority.
- `restaurant_exclusion`: exclude hotpot/sweets or user-detected cuisine.
- `time_compression`: go home earlier / skip optional tail.

Feedback request:

```json
{
  "session_id": "uuid",
  "message": "不要火锅",
  "quick_action": "不要火锅"
}
```

Feedback response streams or returns updated `plan_canvas`. The current plan is modified, then rebuilt into PlanCanvasState.

## Feedback v1 Strategy

For demo reliability, v1 can use deterministic plan adjustment plus existing quality checks:

- Closer: select a more route-focused candidate if available; otherwise annotate route compaction and keep quality gates.
- Indoor: prefer indoor tagged activities/extras; if no candidate exists, use curated indoor fallback for scenario.
- Cuisine exclusion: replace dinner slot from existing candidates/fallbacks when the dinner violates the excluded cuisine; preserve activity and extra when possible.
- Earlier home: mark optional tail as skipped/removed and recompute duration/end time; keep main activity and dinner.

Every feedback response rebuilds checks/evidence/tool tasks and records `feedback.history`.

The latest feedback also writes `feedback.change_summary`:

- `before`: compact route/end-time/station summary before the change.
- `after`: compact route/end-time/station summary after the change.
- `preserved`: venues kept from the previous Canvas.
- `changed`: concrete replacements, removals, or route improvements.
- `note`: used when no better replacement exists, so the UI can explain why the original plan was preserved.

## Execution Actions

Before approval:

- Build pending actions from timeline item `action` and scenario notes.
- Always include share text and route preparation as pending actions.
- Include scheduled time, party size, user-facing notes, and next step when they can be inferred from the plan.

After approval:

- Convert `step_complete` and `all_complete` events into `execution_results`.
- Display confirmation codes where available.
- Preserve booking tool data such as `time_slot`, `party_size`, `special_requests`, and `notes`.

## Migration

- Keep old `PlanCard` as fallback while `plan_canvas` is absent.
- Keep existing `Plan` type temporarily; add `PlanCanvasState` and gradually shift primary rendering.
- Keep `PlanMapData` as adapter fallback until `MapView` supports `planCanvas`.
