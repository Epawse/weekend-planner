# Demo Guide

## Product Narrative

Weekend Planner AI Mode is an execution-oriented local-life Agent for family and friends plans. It is not a normal POI recommender: the system decomposes one natural-language goal into activity, dining, optional tail, route, availability, evidence, and execution tasks; builds a persistent Plan Canvas; supports follow-up constraint updates; and completes mock booking, reservation, notes, navigation preparation, and share copy after approval.

## Friends Showcase

Input:

```text
今天下午4个朋友聚会，有吃有玩，别太远，适合聊天拍照，吃完还能续摊。
```

Walkthrough:

1. Generate the plan and point out the center Plan Canvas as the main answer surface.
2. Show the conclusion summary, metrics, and timeline.
3. Open the right Source tab and explain source groups: curated data, business API, rules, rejected options.
4. Return to the Map tab and click the dinner marker to show VenuePopover with time, source, business checks, and actions.
5. Click `近一点`.
6. Show the feedback change card:
   - before/after route and end-time summary.
   - preserved venues.
   - changed items or the no-change reason when current route is already compact.
7. Click `确认并执行`.
8. Show execution cards with confirmation code, time, party size, notes, next step, and share text.

## Family Showcase

Input:

```text
今天下午想和老婆孩子去亲子乐园玩4到6个小时，孩子5岁，老婆最近减肥，别离家太远，少走路少排队。
```

Walkthrough:

1. Generate the family plan and show the family-specific title, summary, and metrics.
2. Show the family timeline and Family Assurance checks.
3. Open Source tab and point out child suitability, light meal, queue, and route evidence.
4. Click `换室内` or `早点回家`.
5. Show the feedback change card and explain what was preserved and what changed.
6. Confirm and show execution cards:
   - activity reservation.
   - family restaurant reservation.
   - child seat / light meal notes.
   - share copy for family.

## Stable Talking Points

- Canvas is the single plan data source.
- Chat is for input and follow-up, not full plan rendering.
- Sources are user-facing evidence, not debug logs.
- Map markers are actionable plan objects.
- Feedback updates the current plan and explains before/after impact.
- Approval turns the plan into execution results with mock confirmation data.

## Known Demo Constraint

Manual browser verification requires a running backend that matches `NEXT_PUBLIC_API_BASE_URL`. In this sandbox, new backend and frontend ports could not be bound, although code-level checks passed.
