# System Architecture Design — Agent Graph & Tool Contracts

## Goal

Design the complete LangGraph agent architecture for the weekend activity planning system: graph topology, state schema, multi-provider LLM adapter, tool interface contracts, and execution flow. This document serves as the implementation blueprint AND the basis for the competition's ≤2-page design document deliverable.

## Research References

* [`research/agent-architecture-patterns.md`](research/agent-architecture-patterns.md) — Harness engineering philosophy, agent loop, multi-agent decision framework, context engineering, production patterns (from learn-agent + learn-claude-code)
* [`research/langgraph-architecture-for-planner.md`](research/langgraph-architecture-for-planner.md) — LangGraph graph topology, state schema, tool contracts, streaming strategy
* [`research/technical-implementation-details.md`](research/technical-implementation-details.md) — LangGraph StateGraph/interrupt/streaming API, FastAPI SSE (EventSourceResponse), LangChain init_chat_model multi-provider, Qwen DashScope OpenAI-compatible integration
* [`research/frontend-sse-integration.md`](research/frontend-sse-integration.md) — Next.js App Router SSE consumption, useSSE hook, POST-based streaming, event protocol design, UI component flow
* [`research/gis-tools-integration.md`](research/gis-tools-integration.md) — Isochrone (OpenRouteService), POI spatial filtering (GeoPandas), TSP route optimization, map visualization (高德 JS API 2.0), competitive advantage analysis

## Requirements

* Agent accepts natural language input ("今天下午想和老婆孩子出去玩") and produces structured executable plan
* Plan includes: activities (play → eat → extras), timeline, venue details, route, map visualization
* Supports family and friends scenarios — constraints inferred by LLM from scenario description (not hardcoded rules)
* **Real data layer**: 高德 POI search, 高德 route planning, OpenRouteService isochrone, 和风天气 real-time weather
* **Mock execution layer**: booking confirmations, delivery orders, queue status (interface matches real API contracts for future swap)
* **GIS capabilities**: isochrone-based reachability (not radius search), TSP multi-stop route optimization, GeoPandas spatial filtering, map visualization with 高德 JS API 2.0
* Multi-provider LLM with priority fallback (Qwen → Gemini → DeepSeek → OpenAI; only providers with a configured key are used; in the demo environment Gemini is primary and DeepSeek is the fallback)
* SSE streaming from backend to frontend during planning and execution
* LangGraph interrupt for plan approval — user confirms before execution begins
* One-click mock execution with confirmation numbers, venue details, delivery ETA
* Shareable plan card generation ("搞定了，下午2点出发，先去……")
* Re-planning on simulated failure (venue full → fallback alternatives)

## Acceptance Criteria

* [ ] LangGraph graph runs end-to-end for both scenarios (family + friends)
* [ ] Isochrone-based venue search returns real Beijing POI data within reachable area
* [ ] Plan output includes timeline, real venues, optimized route, and actionable items
* [ ] Map visualization renders isochrone + route + POI markers
* [ ] Provider fallback works when primary LLM fails
* [ ] SSE streaming updates visible in frontend during planning
* [ ] Interrupt pauses graph; user approval resumes execution
* [ ] Mock execution completes all bookings in plan with confirmation details
* [ ] Re-planning triggers on simulated failure (e.g., restaurant full)
* [ ] Design document (≤2 pages) covers planning strategy, tool call chain, error handling

## Technical Approach

### State Schema

```python
from typing import TypedDict, Literal

class PlannerState(TypedDict):
    # Input
    user_input: str
    scenario: Literal["family", "friends"]
    home_location: tuple[float, float]  # GCJ-02 经纬度 (lng, lat)
    scenario_description: str  # "孩子5岁，老婆最近在减肥" or "4个人，2男2女"

    # GIS Analysis
    isochrone: dict | None  # GeoJSON Polygon from OpenRouteService
    candidate_venues: list[dict]  # 高德 POI results filtered by isochrone
    weather: dict | None  # 和风天气 real-time data
    optimized_route: dict | None  # TSP result + 高德路线 GeoJSON

    # Planning
    messages: list  # LLM conversation history
    plan: dict | None  # Structured plan (see Plan Schema below)
    plan_status: Literal["generating", "presented", "approved", "rejected", "executing", "completed"]

    # Execution
    current_step: int
    execution_results: list[dict]  # Each step's booking/order result

    # Error handling
    error: str | None
    retry_count: int
    fallback_venues: list[dict]  # Alternatives when primary venue fails
```

### Plan Output Schema

```python
class Plan(TypedDict):
    title: str  # "周六下午亲子时光"
    duration_hours: float
    activities: list[Activity]
    total_travel_minutes: int
    share_text: str  # "搞定了，下午2点出发，先去……"

class Activity(TypedDict):
    order: int
    type: Literal["play", "eat", "extra"]
    venue_name: str
    venue_address: str
    venue_coords: tuple[float, float]
    start_time: str  # "14:00"
    duration_minutes: int
    travel_to_next_minutes: int | None
    action: Literal["book", "reserve", "order_delivery", "no_action"]
    action_details: dict  # Params for mock execution
    reason: str  # Why this venue fits the constraints
```

### Home Location Strategy

Demo 时使用预设地址（用户可在 UI 上切换或地图点选）：
- 默认: 望京 SOHO (116.481, 39.998) — OSM 数据质量好，周边业态丰富
- 备选: 三里屯 (116.454, 39.937) — 朋友场景更合适

### Architecture: Plan-and-Execute with Interrupt

```
User Input → [Parse Intent] → [Search & Analyze (GIS)] → [Generate Plan] 
    → [INTERRUPT: Present Plan to User] → [User Approves] 
    → [Execute Steps] → [Generate Share Card] → Done
                                    ↑
                              [Replan on Failure]
```

Single LangGraph StateGraph, not multi-agent. Task is sequential and context won't overflow for a 4-6 hour activity plan.

### Key Design Decisions (ADR-lite)

**Decision 1: Single Agent over Multi-Agent**
- Context: learn-agent multi-agent decision framework says "if single agent can do it cleanly without context overflow, don't add agents"
- Decision: Single graph with specialized nodes
- Consequence: Simpler error handling, lower latency, easier debugging

**Decision 2: Real Search + Mock Execution (Hybrid)**
- Context: Pure mock has no demo credibility; full real API needs enterprise credentials
- Decision: Real APIs for data retrieval (高德, OpenRouteService, 和风天气), mock for transactional actions (booking, ordering)
- Consequence: Demo shows real Beijing venues/routes/weather; execution layer has clean interface for future real API swap

**Decision 3: LLM-Inferred Constraints (not hardcoded)**
- Context: Harness engineering principle — "model decides, harness executes"
- Decision: Put scenario description in system prompt, let model infer search keywords and filters
- Consequence: Handles edge cases and evaluator ad-hoc questions naturally; no brittle rule maintenance

**Decision 4: GIS as Core Differentiator**
- Context: User has GIS professional background; other teams will do radius search
- Decision: Isochrone analysis, TSP route optimization, spatial filtering, map visualization
- Consequence: Visually and technically superior to competitors; demonstrates real spatial intelligence

**Decision 5: LangGraph interrupt() for Plan Approval**
- Context: Competition requires "confirm plan → then execute"
- Decision: Use LangGraph native interrupt + Command(resume=) pattern with MemorySaver checkpointer
- Consequence: Clean separation of planning and execution phases; supports plan modification before execution

### Tool Contracts (Real + Mock)

| Tool | Real/Mock | Service | Purpose |
|------|-----------|---------|---------|
| `get_reachable_area` | Real | OpenRouteService | Isochrone polygon (driving/walking X min) |
| `search_venues` | Real | 高德 POI API | Restaurants, attractions, activities |
| `get_weather` | Real | 和风天气 | Real-time weather for outdoor decisions |
| `calculate_route` | Real | 高德路径规划 | Driving/walking time and route geometry |
| `optimize_route_order` | Real | TSP + 高德 | Multi-stop optimal sequence |
| `filter_venues_in_area` | Real | GeoPandas sjoin | Spatial filter POIs within isochrone |
| `check_availability` | Mock | — | Queue/seat availability simulation |
| `make_reservation` | Mock | — | Booking confirmation generation |
| `order_delivery` | Mock | — | Flower/cake delivery order simulation |

### Multi-Provider LLM

```python
# All providers via OpenAI-compatible interface
Qwen          → ChatOpenAI(base_url="dashscope.aliyuncs.com/compatible-mode/v1")
Gemini        → ChatOpenAI(base_url="generativelanguage.googleapis.com/v1beta/openai/")
DeepSeek      → ChatOpenAI(base_url="api.deepseek.com")
OpenAI        → ChatOpenAI (native)
```

Priority fallback order: Qwen → Gemini → DeepSeek → OpenAI. Only providers with a
configured API key are used, so in the demo environment (only Gemini + DeepSeek keys set)
Gemini is the primary and DeepSeek is the fallback. Try providers in order, switch on failure.

### Frontend Map Visualization

高德 JS API 2.0 + `@uiw/react-amap`:
- Isochrone polygon overlay (semi-transparent fill)
- Route polyline with direction arrows
- POI markers with category icons
- Interactive: click marker → show venue details

### API Protocol (Frontend ↔ Backend)

```
POST /api/plan/create
  Request:  { message: str, scenario: "family"|"friends", home_location: [lng, lat] }
  Response: SSE stream (EventSource)
    event: progress    → { type, message }
    event: tool_call   → { tool, args, result_summary }
    event: plan_ready  → { plan: Plan, isochrone: GeoJSON, route: GeoJSON, venues: [...] }
    event: error       → { message, recoverable: bool }

POST /api/plan/approve
  Request:  { session_id: str, approved: bool, modifications?: dict }
  Response: SSE stream
    event: step_start    → { step: int, action, venue }
    event: step_complete → { step: int, confirmation, details }
    event: step_failed   → { step: int, error, fallback_options }
    event: all_complete  → { summary, share_text, share_card }

POST /api/plan/modify
  Request:  { session_id: str, feedback: str }  // "换一家餐厅" / "加个甜品店"
  Response: SSE stream (same as /create, re-plans with feedback)

GET /api/health
  Response: { status: "ok", providers: { qwen: bool, deepseek: bool } }
```

### System Prompt Template (Planning Phase)

```
你是一个本地生活活动规划助手。你的任务是根据用户的需求，规划一个完整的下午活动方案。

## 当前场景
{scenario_description}
// 例: "家庭场景：孩子5岁，老婆最近在减肥"
// 例: "朋友场景：总共4个人，2个男生2个女生"

## 用户位置
{home_address} ({home_coords})

## 当前天气
{weather_summary}

## 可达范围
已计算出从用户位置出发{travel_mode}{travel_minutes}分钟内的可达区域。
你的搜索和推荐必须在此范围内。

## 你的工具
你可以使用以下工具来搜索和规划：
- search_venues: 搜索餐厅/景点/活动
- calculate_route: 计算两点间路线和时间
- check_availability: 查询排队/座位情况
- optimize_route_order: 优化多点访问顺序

## 输出要求
生成一个包含2-4个活动的完整方案，必须包含：
1. 至少一个娱乐/游玩活动
2. 一顿正餐
3. 可选：额外活动（甜品/散步/购物）

每个活动需要：具体场所名称、地址、开始时间、持续时间、为什么适合当前场景。

根据场景自动推断约束（不要问用户额外问题，直接给出方案）。
```

### Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| ORS 等时圈中国数据不准 | Medium | Low | Demo 选望京/三里屯等 OSM 数据好的区域 |
| 高德 API 额度用完 | Low | High | 本地缓存 + 开发期间用固定坐标复用结果 |
| LM 推理约束不稳定 | Medium | Medium | structured output 约束输出格式 + few-shot examples |
| 2周内完成全部实现 | High | — | 按 P0-P3 优先级分层，P0 必须完成 |
| 决赛现场网络问题 | Medium | High | 预录 Demo 视频 backup + 本地缓存关键 API 响应 |
| 主力 LLM tool calling 不稳定 | Medium | Medium | fallback 链 Gemini → DeepSeek（仅用已配置 key 的 provider） |

### Implementation Priority

```
P0 (必须 — 没有这些不算完成):
  - LangGraph 核心流程 (parse → search → plan → interrupt → execute)
  - 高德 POI 搜索 + 路径规划 (真实数据)
  - Mock 执行层 (booking/delivery)
  - 基础 Web UI (chat input → plan display → approve button)
  - FastAPI SSE streaming

P1 (强烈推荐 — 核心差异化):
  - OpenRouteService 等时圈
  - 地图可视化 (高德 JS API: isochrone + route + markers)
  - 和风天气实时数据
  - 多模型 fallback

P2 (加分项):
  - TSP 多点路径优化
  - 分享卡片生成 ("搞定了，下午2点出发……")
  - 重规划 (venue full → fallback)
  - GeoPandas 空间过滤

P3 (锦上添花):
  - 配送下单 mock (鲜花蛋糕)
  - 方案修改对话 (/modify endpoint)
  - 地图交互 (点击 marker 查看详情)
  - 多场景切换动画
```

## Definition of Done

* Design document complete with graph diagram, state schema, tool contracts
* All architectural decisions recorded with rationale
* API endpoint schemas defined (request/response)
* System prompt template finalized
* API keys registered (高德, OpenRouteService, 和风天气, Qwen/DeepSeek)
* Ready to implement without further design questions

## Out of Scope

* Actual Meituan booking/ordering API (mock only — requires enterprise credentials)
* User authentication / accounts
* Multi-city support (Beijing only for demo)
* Real payment processing
* Mobile app (web only)
* RAG / vector database (not needed for this task scope)

## Technical Notes

* LangGraph v1.2.1: StateGraph, conditional edges, interrupt(), Command(resume=), get_stream_writer(), MemorySaver
* FastAPI: EventSourceResponse + ServerSentEvent (native SSE support)
* LangChain: init_chat_model configurable, bind_tools, ToolNode
* GIS stack: openrouteservice-py, geopandas, shapely, @uiw/react-amap, turf.js
* Spec files: `.trellis/spec/backend/directory-structure.md` defines module layout
* Competition deliverable: design doc ≤2 pages + Demo + complete Tool implementation code
