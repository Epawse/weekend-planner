"""Main LangGraph StateGraph for the activity planning agent.

Topology: Plan-and-Execute with Interrupt
  User Input -> parse_intent -> search_and_analyze -> generate_plan
    -> present_plan (INTERRUPT) -> execute_steps -> generate_share_card -> END
                                                 -> replan (on failure)
"""

import json

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.llm.prompts import PLAN_OUTPUT_FORMAT, PLANNING_SYSTEM_PROMPT
from app.llm.provider import llm_factory
from app.models.state import PlannerState
from app.tools.booking import make_reservation
from app.tools.delivery import order_delivery
from app.tools.isochrone import get_reachable_area
from app.tools.poi_search import search_venues
from app.tools.weather import get_weather

logger = structlog.get_logger()


# --- Graph Nodes ---


async def parse_intent_node(state: PlannerState) -> dict:
    """Parse user input to extract scenario, constraints, and preferences."""
    writer = get_stream_writer()
    writer({"type": "thinking", "data": {"message": "正在分析您的需求..."}})

    user_input = state["user_input"]
    scenario = state.get("scenario", "family")
    scenario_description = state.get("scenario_description", "")

    # If no scenario_description provided, use LLM to infer
    if not scenario_description:
        if scenario == "family":
            scenario_description = "家庭场景：带家人出去玩，注重亲子体验和舒适度"
        else:
            scenario_description = "朋友场景：和朋友一起出去玩，注重趣味性和社交体验"

    writer({"type": "thinking", "data": {"message": f"场景识别: {scenario_description}"}})

    return {
        "scenario": scenario,
        "scenario_description": scenario_description,
        "plan_status": "generating",
        "messages": [HumanMessage(content=user_input)],
    }


async def search_and_analyze_node(state: PlannerState) -> dict:
    """Call GIS tools to gather venue data, weather, and reachable area."""
    writer = get_stream_writer()
    home_location = state.get("home_location", (116.481, 39.998))
    location_str = f"{home_location[0]},{home_location[1]}"

    # Step 1: Get weather
    writer({"type": "tool_calling", "data": {"tool": "get_weather", "message": "正在查询天气..."}})
    weather_result = await get_weather.ainvoke({"location": location_str})
    weather_data = weather_result.get("data") if weather_result.get("status") == "success" else None

    # Step 2: Get reachable area (isochrone)
    writer({"type": "tool_calling", "data": {"tool": "get_reachable_area", "message": "正在计算可达范围..."}})
    isochrone_result = await get_reachable_area.ainvoke(
        {
            "location": location_str,
            "travel_minutes": 30,
            "profile": "driving-car",
        }
    )
    isochrone_data = isochrone_result.get("data") if isochrone_result.get("status") == "success" else None

    # Step 3: Search venues based on scenario
    writer({"type": "tool_calling", "data": {"tool": "search_venues", "message": "正在搜索周边场所..."}})

    scenario = state.get("scenario", "family")
    search_queries = _get_search_queries(scenario, state.get("scenario_description", ""))

    all_venues: list[dict] = []
    for query in search_queries:
        result = await search_venues.ainvoke(
            {
                "query": query,
                "location": location_str,
                "radius": 5000,
            }
        )
        if result.get("status") == "success":
            venues = result.get("data", [])
            all_venues.extend(venues)

    writer(
        {
            "type": "tool_result",
            "data": {
                "message": f"找到 {len(all_venues)} 个候选场所",
                "weather": weather_data.get("summary") if weather_data else "天气数据暂不可用",
            },
        }
    )

    return {
        "weather": weather_data,
        "isochrone": isochrone_data,
        "candidate_venues": all_venues,
    }


async def generate_plan_node(state: PlannerState) -> dict:
    """Use LLM to generate a structured activity plan from gathered data."""
    writer = get_stream_writer()
    writer({"type": "thinking", "data": {"message": "正在生成活动方案..."}})

    home_location = state.get("home_location", (116.481, 39.998))
    weather = state.get("weather")
    candidate_venues = state.get("candidate_venues", [])
    scenario_description = state.get("scenario_description", "")

    # Build system prompt with context
    weather_summary = weather.get("summary", "天气数据暂不可用") if weather else "天气数据暂不可用"
    system_prompt = PLANNING_SYSTEM_PROMPT.format(
        scenario_description=scenario_description,
        home_address="望京SOHO附近",
        home_coords=f"{home_location[0]},{home_location[1]}",
        weather_summary=weather_summary,
        travel_minutes=30,
    )

    # Build venue context for LLM
    venue_context = _format_venues_for_llm(candidate_venues)

    user_message = f"""用户需求: {state["user_input"]}

以下是搜索到的候选场所（已按距离排序）：
{venue_context}

请根据以上信息，为用户规划一个完整的下午活动方案。

{PLAN_OUTPUT_FORMAT}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    # Call LLM with fallback
    response = await llm_factory.invoke_with_fallback(messages, temperature=0.7)

    # Parse plan from LLM response
    plan = _parse_plan_from_response(response.content)

    if plan:
        writer({"type": "plan_generated", "data": {"message": "方案已生成", "plan_title": plan.get("title", "")}})
        return {
            "plan": plan,
            "plan_status": "presented",
            "messages": [AIMessage(content=response.content)],
        }
    else:
        logger.warning("plan_parse_failed", response_content=response.content[:200])
        return {
            "plan": None,
            "error": "invalid_plan",
            "retry_count": state.get("retry_count", 0) + 1,
            "messages": [AIMessage(content=response.content)],
        }


async def present_plan_node(state: PlannerState) -> dict:
    """Interrupt execution to present plan to user for approval."""
    writer = get_stream_writer()

    plan = state.get("plan")
    if not plan:
        return {"error": "no_plan_to_present", "plan_status": "failed"}

    # Emit plan_ready event before interrupting
    writer(
        {
            "type": "plan_ready",
            "data": {
                "plan": plan,
                "isochrone": state.get("isochrone"),
                "venues": state.get("candidate_venues", [])[:10],
            },
        }
    )

    # Interrupt — waits for user approval via Command(resume=True/False)
    decision = interrupt(
        {
            "question": "请确认活动方案",
            "plan": plan,
        }
    )

    if decision:
        return {"plan_status": "approved"}
    else:
        return {"plan_status": "rejected"}


async def execute_steps_node(state: PlannerState) -> dict:
    """Execute each activity in the plan (mock bookings/reservations)."""
    writer = get_stream_writer()
    plan = state.get("plan")

    if not plan or not plan.get("activities"):
        return {"error": "no_activities_to_execute", "plan_status": "failed"}

    execution_results: list[dict] = []
    activities = plan["activities"]

    for i, activity in enumerate(activities):
        step_num = i + 1
        action = activity.get("action", "no_action")
        venue_name = activity.get("venue_name", "未知场所")

        writer(
            {
                "type": "step_start",
                "data": {"step": step_num, "action": action, "venue": venue_name},
            }
        )

        result: dict = {"step": step_num, "venue": venue_name, "action": action}

        if action == "reserve" or action == "book":
            booking_result = await make_reservation.ainvoke(
                {
                    "venue_name": venue_name,
                    "time_slot": activity.get("start_time", ""),
                    "party_size": 2,
                    "special_requests": activity.get("action_details", {}).get("special_requests", ""),
                }
            )
            result["result"] = booking_result
        elif action == "order_delivery":
            delivery_result = await order_delivery.ainvoke(
                {
                    "item_type": activity.get("action_details", {}).get("item_type", "flowers"),
                    "item_description": activity.get("action_details", {}).get("description", ""),
                    "delivery_address": activity.get("venue_address", ""),
                    "delivery_time": activity.get("start_time", ""),
                }
            )
            result["result"] = delivery_result
        else:
            result["result"] = {"status": "success", "data": {"message": f"{venue_name} 无需预约，直接前往"}}

        execution_results.append(result)

        writer(
            {
                "type": "step_complete",
                "data": {
                    "step": step_num,
                    "venue": venue_name,
                    "status": result["result"].get("status", "success"),
                    "confirmation": result["result"].get("data", {}).get("confirmation_code", ""),
                },
            }
        )

    return {
        "execution_results": execution_results,
        "plan_status": "executing",
        "current_step": len(activities),
    }


async def generate_share_card_node(state: PlannerState) -> dict:
    """Generate a shareable summary card for the completed plan."""
    writer = get_stream_writer()
    plan = state.get("plan", {})
    execution_results = state.get("execution_results", [])

    share_text = plan.get("share_text", "")
    if not share_text and plan.get("activities"):
        activities = plan["activities"]
        parts = [f"先去{a['venue_name']}" if i == 0 else a["venue_name"] for i, a in enumerate(activities)]
        share_text = f"搞定了！{plan.get('title', '今日活动')}，{'，然后'.join(parts)}"

    # Build execution summary
    confirmations = []
    for result in execution_results:
        data = result.get("result", {}).get("data", {})
        if data.get("confirmation_code"):
            confirmations.append(f"{result['venue']}: {data['confirmation_code']}")

    writer(
        {
            "type": "all_complete",
            "data": {
                "summary": "所有预订已完成" if confirmations else "方案已确认",
                "share_text": share_text,
                "confirmations": confirmations,
            },
        }
    )

    return {"plan_status": "completed"}


# --- Routing Functions ---


def should_retry_or_continue(state: PlannerState) -> str:
    """Route after plan generation: retry on error, present on success."""
    if state.get("error") == "invalid_plan" and state.get("retry_count", 0) < 3:
        return "retry"
    if state.get("error"):
        return "end"
    return "present"


def after_approval(state: PlannerState) -> str:
    """Route after user approval decision."""
    if state.get("plan_status") == "approved":
        return "execute"
    return "end"


# --- Helper Functions ---


def _get_search_queries(scenario: str, description: str) -> list[str]:
    """Generate search queries based on scenario type."""
    if scenario == "family":
        return ["亲子乐园", "儿童餐厅", "公园"]
    else:
        return ["密室逃脱", "火锅", "甜品店"]


def _format_venues_for_llm(venues: list[dict]) -> str:
    """Format venue list into readable text for LLM context."""
    if not venues:
        return "暂无搜索结果"

    lines = []
    for i, v in enumerate(venues[:15], 1):  # Limit to 15 venues
        rating = f"评分{v.get('rating')}" if v.get("rating") else "暂无评分"
        distance = f"{v.get('distance', '?')}米" if v.get("distance") else ""
        lines.append(
            f"{i}. {v.get('name', '未知')} | {v.get('category', '')} | {rating} | {distance}\n"
            f"   地址: {v.get('address', '未知')} | 坐标: {v.get('coords', [0, 0])}"
        )
    return "\n".join(lines)


def _parse_plan_from_response(content: str) -> dict | None:
    """Extract JSON plan from LLM response text."""
    try:
        # Try to find JSON block in markdown code fence
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            json_str = content[start:end].strip()
        elif "```" in content:
            start = content.index("```") + 3
            end = content.index("```", start)
            json_str = content[start:end].strip()
        else:
            # Try parsing the whole content as JSON
            json_str = content.strip()

        plan = json.loads(json_str)

        # Validate required fields
        if "activities" in plan and isinstance(plan["activities"], list):
            return plan
        return None
    except (json.JSONDecodeError, ValueError):
        logger.warning("plan_json_parse_failed", content_preview=content[:100])
        return None


# --- Graph Construction ---


def build_planning_graph() -> StateGraph:
    """Build and return the compiled planning graph with checkpointer."""
    builder = StateGraph(PlannerState)

    # Add nodes
    builder.add_node("parse_intent", parse_intent_node)
    builder.add_node("search_and_analyze", search_and_analyze_node)
    builder.add_node("generate_plan", generate_plan_node)
    builder.add_node("present_plan", present_plan_node)
    builder.add_node("execute_steps", execute_steps_node)
    builder.add_node("generate_share_card", generate_share_card_node)

    # Add edges
    builder.add_edge(START, "parse_intent")
    builder.add_edge("parse_intent", "search_and_analyze")
    builder.add_edge("search_and_analyze", "generate_plan")

    # Conditional: after plan generation
    builder.add_conditional_edges(
        "generate_plan",
        should_retry_or_continue,
        {
            "retry": "generate_plan",
            "present": "present_plan",
            "end": END,
        },
    )

    # Conditional: after user approval
    builder.add_conditional_edges(
        "present_plan",
        after_approval,
        {
            "execute": "execute_steps",
            "end": END,
        },
    )

    builder.add_edge("execute_steps", "generate_share_card")
    builder.add_edge("generate_share_card", END)

    return builder


# Module-level compiled graph with checkpointer
checkpointer = MemorySaver()
planning_graph = build_planning_graph().compile(checkpointer=checkpointer)
