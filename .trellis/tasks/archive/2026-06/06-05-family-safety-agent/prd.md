# Family安心出游 Agent 升级

## Goal

把现有 Weekend Planner 的家庭场景从“附近亲子推荐”升级为“家庭安心出游执行 Agent”：系统能结构化理解孩子年龄、减脂饮食、低步行、低排队等家庭约束，基于真实 POI/路线/天气加规则推断和 mock 业务接口形成证据，先过滤和打分，再由 LLM 基于证据生成表达。前端展示家庭安心检查，用户确认后执行家庭化 mock 预约、订座、备注和行前提醒。

## What I Already Know

* 当前后端是 FastAPI + LangGraph，核心图在 `backend/app/agents/orchestrator.py`。
* 当前空间引擎在 `backend/app/services/spatial.py`，已有等时圈、POI、Shapely 过滤、聚类、TSP、路线增强。
* 当前 LLM provider 已支持 Qwen/Gemini/DeepSeek/OpenAI fallback，LLM 目前负责从候选方案中选择并输出 JSON。
* 当前已有 mock `availability.py`、`booking.py`、`delivery.py`，但 availability 还未接入主规划流程。
* 当前前端是 Next.js，`useChat` 消费 SSE，`PlanCard` 展示普通方案，`MapView` 展示等时圈、候选点和路线。
* 当前家庭场景信息主要是前端按钮和默认 `scenario_description`，没有成为可计算约束。

## Requirements

* 家庭画像：解析/默认补齐孩子年龄、家庭人数、饮食目标、总时长、最大单段通勤、最大步行、最大排队、室内偏好、儿童椅需求。
* 家庭策略：生成明确的不可妥协约束、优先满足约束、可补偿约束。
* 家庭特征增强：为活动和餐厅补充 `child_friendly`、`age_range`、`indoor`、`rest_area`、`restroom`、`queue_minutes`、`diet_friendly`、`child_seat`、`family_friendly` 等证据化字段。
* 可用性前置：在 LLM 生成最终方案前检查/模拟排队、余位、儿童椅、低脂选项、活动余票。
* 规则过滤与打分：加入家庭硬约束、软偏好、疲劳度、降级说明、主方案和备选方案。
* 证据绑定：LLM 只能基于后端生成的 evidence 解释方案，不允许创造新事实。
* 前端安心卡：展示家庭安心检查、疲劳度、证据来源、降级处理、为什么选/为什么不选。
* 确认后执行：预约亲子活动、订 3 人桌、备注儿童椅/少油/轻食、生成发给老婆的文案和行前提醒。
* Showcase Mode：提供稳定演示模式，可固定家庭数据、availability、备选方案和异常恢复故事。

## Acceptance Criteria

* [x] 家庭请求生成的 `plan_ready` SSE 包含 `family_profile`、`family_strategy`、`family_checks`、`fatigue_score`、`evidence`、`alternatives`。
* [x] LLM 最终方案理由引用后端 evidence，后端可校验引用是否存在。
* [x] 至少一条候选餐厅在进入 LLM 前经过可用性/家庭特征校验。
* [x] 前端方案卡展示家庭安心检查和家庭疲劳度。
* [x] 用户确认后，执行结果包含儿童椅、少油/低脂、三人桌等家庭备注，以及行前提醒。
* [x] Showcase Mode 能在无真实 API 或 API 波动时稳定生成完整家庭演示方案。
* [x] 后端测试覆盖家庭特征增强、规则打分、mock availability 合约。
* [x] 前端 lint 通过，后端测试通过。

## Out Of Scope

* 不接入真实美团下单/订座接口。
* 不把朋友场景同步升级到同等深度。
* 不实现真实儿童椅库存、真实菜单营养数据、真实亲子活动票务库存。
* 不做复杂坐标系重构；短期以高德展示坐标为准，Showcase Mode 避免明显偏移。

## Technical Notes

* 保持原则：工具负责事实，规则负责判断，打分负责排序，LLM 负责表达，前端负责展示系统考虑过什么。
* 证据来源分层：`real_api`、`keyword_rule`、`mock_business_api`。
* 证据可信度分层：`high`、`medium`、`simulated`。
* 前端状态流要产品化，新增家庭场景专属 SSE 文案，而不是只展示技术日志。
* LangGraph interrupt 继续作为用户确认边界；所有预约、订座、备注类动作必须发生在确认后。

## Definition Of Done

* Tests added/updated where behavior changes.
* `npm run lint` passes for frontend.
* Backend tests pass for changed backend modules.
* No real secrets or env files are committed.
* Showcase Mode can be explained and demoed as mock business API capability, not production truth.

## Implementation Notes

* Added `backend/app/services/family.py` for family profile defaults, strategy, evidence, feature enrichment, family scoring, fatigue scoring, alternatives, rejected options, and execution notes.
* Added `check_family_availability` mock business API contract in `backend/app/tools/availability.py`.
* Inserted `family_analysis` into the LangGraph flow between spatial analysis and LLM narration.
* Extended `plan_ready` SSE and final plan payload with family profile, strategy, checks, fatigue, evidence, alternatives, rejected options, degradations, and pre-departure tips.
* Added `SHOWCASE_MODE` backend setting and stable family showcase spatial data.
* Added frontend `FamilyAssuranceCard` plus TypeScript types and streaming display for family-specific events.
* Added second-round family quality gate: strong-child-intent main activity matching, 4-6 hour completeness,
  family rhythm scheduling, dinner time guardrail, stricter diet-risk scoring, queue warn/fail thresholds,
  and canonical backend timeline attachment before final presentation.
* Reworked final activity reasons to use backend-validated evidence claims instead of raw LLM narration for
  child-seat, low-fat, queue, age-fit, ticket, and availability facts.
* Refined frontend family card into `已满足` plus `轻微降级 / 风险提醒`, with evidence, degradations,
  alternatives, and rejected options folded by default.
* Refined map display to focus the final route by default, weaken the isochrone, hide candidate POIs behind
  a toggle, and fit viewport only to home plus selected route points.
* Added POI provenance and trust fields across AMap search, spatial candidates, final activities, evidence,
  and frontend types: `amap_real_poi`, `showcase_curated`, and `fallback_generated`.
* Added company/office POI detection for strong child intent. AMap POIs such as `公司企业;公司` with company
  names are now rejected as main family activities even if returned by a child-related search query.
* Added trusted strong-child main gate: strong child intent accepts `showcase_curated` venues, or
  `amap_real_poi` venues only when `strong_child_activity_evidence=true`.
* Added curated family fallback when live AMap has no qualified strong child main activity, preventing weak
  child venues or company-type POIs from becoming the primary plan.

## Verification

* `backend/.venv/bin/python -m pytest` — 41 passed.
* `backend/.venv/bin/python -m ruff check backend/app backend/tests` — passed.
* `cd frontend && npm run lint` — passed.
* `cd frontend && npx tsc --noEmit` — passed.
