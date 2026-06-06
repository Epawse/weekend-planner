# Friends 聚会适配 Agent

## Goal

在不影响已稳定 family 场景的前提下，为 `friends` 场景新增“朋友聚会适配 Agent”：系统能结构化理解人数、群体构成、社交/拍照/互动/聊天/距离偏好，并在 LLM 叙述前完成朋友聚会规则过滤、证据增强、质量门槛、节奏排程和 fallback。

## Requirements

* 朋友画像：默认 4 人；识别 `2男2女`、`四个人`、`轻松`、`有吃有玩`、`别太远`、`适合聊天`、`适合拍照`、`聚会` 等偏好。
* 朋友策略：硬约束包括 4-6 小时、4 人桌、路线不过度分散、至少一个社交/互动/拍照活动、晚餐 17:30-19:00。
* POI 特征：活动补充 `photo_friendly`、`social_friendly`、`interactive`、`novelty`、`not_too_tiring`、`group_suitable`；餐厅补充 `table_for_4`、`chat_friendly`、`ambience_score`、`noise_level`、`food_variety`、`queue_minutes`；饭后补充 `after_dinner_friendly`、`can_continue_chat`、`optional_extension`。
* 质量门槛：pass/warn/fail 三层；fail 不能直接输出，必须重规划或 fallback。
* 朋友节奏：体验/展览/互动活动 → 氛围聚餐 → 饭后轻活动；饭后活动标注可续摊/可跳过。
* Evidence bound：最终理由来自后端 evidence，LLM 不创造 4 人桌、排队短、适合聊天等事实。
* 前端最小改动：复用 family assurance 思路，显示“朋友局适配检查”。

## Out Of Scope

* 不做多人投票。
* 不改 family 场景策略和质量门槛。
* 不接入真实美团订座/下单接口。

## Acceptance Criteria

* [x] `friends` 请求生成结构化 friend profile 和 strategy。
* [x] `friends` 候选方案在进入 LLM 前完成特征增强、可用性校验、质量门槛和排序。
* [x] fail 方案不会作为主方案输出；无合格方案时使用 curated friends fallback。
* [x] 最终活动理由来自 validated evidence claims。
* [x] 前端显示朋友局适配检查，包括 4 人桌、聊天、拍照、互动、路线集中、饭后续摊、风险提醒。
* [x] family 测试继续通过。

## Technical Notes

* 后端新增独立 `friends.py` 服务，避免把 friends 规则塞进 family helper。
* 复用现有 LangGraph 结构：`parse_intent -> spatial_analysis -> scenario_analysis -> LLM -> present`。
* 复用 evidence contract，但新增 `friend_profile`、`friend_strategy`、`friend_checks`、`friend_summary`。
* 前端复用 assurance card 视觉结构，但组件语义改为朋友局。

## Implementation Notes

* Added `backend/app/services/friends.py` with profile parsing, strategy, POI feature enrichment,
  friends availability evidence, pass/warn/fail quality gate, score ranking, curated fallback,
  canonical timeline attachment, WeChat share text, and execution notes.
* Added `check_friends_availability` mock business API in `backend/app/tools/availability.py` for
  4-person table, queue, chat ambience, group suitability, photo/social features, and optional extension.
* Added `build_curated_friends_candidate` in `backend/app/services/spatial.py`, separate from family curated data.
* Extended LangGraph with a `friends_analysis` node after `family_analysis`; family path only passes through
  a no-op friends node.
* Extended prompt context and candidate formatting so LLM receives friend evidence and guardrails.
* Added frontend `FriendAssuranceCard` and TypeScript contracts for friend profile, strategy, checks,
  social score, and friend summaries.
* Added friends regression tests for profile extraction, availability contract, quality gate, fallback,
  canonical rhythm, and evidence-bound reasons.
* Stabilization pass added 8 real-input friends regression cases:
  `4个朋友聚会，有吃有玩`、`2男2女，想拍照吃饭`、`朋友局别太远，适合聊天`、
  `想热闹一点`、`预算别太高`、`不想太吵`、`吃完还能续摊`、`先玩再吃`.
* Strengthened friends main activity gate with `source`/`trust_level`/`social_activity_evidence`;
  company, office, education consulting, culture media, and management-company POIs are rejected as main activities.
* Expanded curated friends fallback coverage to include exhibition, handcraft, board game, market,
  coffee, and ambience-restaurant demo venues.
* Unified user-facing evidence labels to: real map data, rule inference, demo business API, curated demo data.
* Added LLM JSON parse fallback: family and friends can still output a full evidence-bound template plan
  from the top validated candidate.
* Productization pass polished friends demo quality:
  user-facing evidence text no longer exposes `mock`, `showcase_curated`, `source=`, `typecode`, or empty tag details;
  curated friends venues now use natural display names (`望京艺文互动展`, `合生麒麟社氛围餐厅`, `麒麟新天地清吧`);
  friend fit score is displayed as a level in the frontend rather than `100`;
  rejected options are rewritten into product-language reasons;
  map route labels distinguish real navigation routes from sequence-only route sketches;
  the large scenario selector collapses to a compact tag after plan generation;
  friend share text now follows a WeChat-ready template.

## Verification

* `cd backend && .venv/bin/python -m pytest tests/test_tools/test_friends_gathering.py` — 19 passed.
* `cd backend && .venv/bin/python -m pytest` — 60 passed.
* `cd backend && .venv/bin/python -m ruff check app tests` — passed.
* `cd frontend && npm run lint` — passed.
* `cd frontend && npx tsc --noEmit` — passed.
