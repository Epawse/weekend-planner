"""Main LangGraph StateGraph for the activity planning agent.

Topology: Plan-and-Execute with Interrupt
  User Input -> parse_intent -> spatial_analysis -> select_and_narrate
    -> present_plan (INTERRUPT) -> execute_steps -> generate_share_card -> END
"""

import json

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.llm.prompts import PLAN_OUTPUT_FORMAT, SELECTION_SYSTEM_PROMPT
from app.llm.provider import llm_factory
from app.models.state import PlannerState
from app.services.spatial import SpatialAnalysisEngine
from app.tools.booking import make_reservation
from app.tools.delivery import order_delivery

logger = structlog.get_logger()


# --- Graph Nodes ---


async def parse_intent_node(state: PlannerState) -> dict:
    """Parse user input to extract scenario, constraints, and preferences."""
    writer = get_stream_writer()
    writer({"type": "thinking", "data": {"message": "正在分析您的需求..."}})

    user_input = state["user_input"]
    scenario = state.get("scenario", "family")
    scenario_description = state.get("scenario_description", "")

    # If no scenario_description provided, use defaults
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


async def spatial_analysis_node(state: PlannerState) -> dict:
    """Deterministic spatial analysis -- NO LLM involved.

    Computes isochrone, searches POIs, filters spatially, clusters venues,
    optimizes routes via TSP, and produces 2-3 candidate plans.
    """
    writer = get_stream_writer()
    home_location = state.get("home_location", [116.481, 39.998])

    writer({"type": "tool_calling", "data": {"tool": "spatial_engine", "message": "正在计算可达范围..."}})

    engine = SpatialAnalysisEngine()
    result = await engine.analyze(
        home_location=home_location,
        scenario=state.get("scenario", "family"),
        time_budget_hours=4.5,
    )

    candidates = result["candidates"]
    all_venues = result["all_venues"]
    stats = result["stats"]

    writer(
        {
            "type": "tool_result",
            "data": {
                "message": (
                    f"空间分析完成: 找到 {stats['total_venues_found']} 个场所，"
                    f"生成 {stats['valid_candidates']} 个候选方案"
                ),
                "stats": stats,
            },
        }
    )

    return {
        "candidate_plans": candidates,
        "isochrone": result["isochrone_geojson"],
        "candidate_venues": all_venues,
        "weather": result["weather"],
    }


async def select_and_narrate_node(state: PlannerState) -> dict:
    """LLM selects best candidate and generates natural language description.

    The LLM receives pre-validated candidate plans (spatially feasible,
    time-budget validated) and picks the best fit for the scenario.
    It then writes natural language descriptions and a share_text.
    """
    writer = get_stream_writer()
    writer({"type": "thinking", "data": {"message": "正在生成活动方案..."}})

    candidates = state.get("candidate_plans", [])
    scenario_description = state.get("scenario_description", "")
    weather = state.get("weather")
    user_input = state["user_input"]

    if not candidates:
        logger.warning("no_candidates_for_selection")
        return {
            "plan": None,
            "error": "no_candidates",
            "plan_status": "failed",
        }

    # Format candidates as structured Chinese text for LLM
    candidates_text = _format_candidates_for_llm(candidates)
    weather_summary = weather.get("summary", "天气数据暂不可用") if weather else "天气数据暂不可用"

    system_prompt = SELECTION_SYSTEM_PROMPT.format(
        scenario_description=scenario_description,
        weather_summary=weather_summary,
    )

    user_message = f"""用户需求: {user_input}

以下是经过空间分析验证的候选方案（已确认时间可行、路线最优）：

{candidates_text}

{PLAN_OUTPUT_FORMAT}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    # Call LLM with fallback
    response = await llm_factory.invoke_with_fallback(messages, temperature=0.7)

    # Parse plan from LLM response
    plan = _parse_plan_from_response(response.content, candidates)

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

    # Interrupt -- waits for user approval via Command(resume=True/False)
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
    """Route after plan selection: retry on error, present on success."""
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


def _format_candidates_for_llm(candidates: list[dict]) -> str:
    """Format candidate plans as structured Chinese text for LLM selection."""
    if not candidates:
        return "暂无候选方案"

    lines = []
    for i, candidate in enumerate(candidates, 1):
        lines.append(f"## 方案 {i}: {candidate.get('label', '')}")
        lines.append(f"- 总时长: {candidate['total_duration_minutes']}分钟")
        lines.append(f"- 通勤时间: {candidate['total_travel_minutes']}分钟")
        lines.append(f"- 步行友好度: {candidate['walkability_score']}")
        lines.append(f"- 空间特征: {candidate.get('spatial_summary', '')}")
        lines.append("")

        for activity in candidate.get("activities", []):
            venue_name = activity.get("venue_name", "")
            category = activity.get("category", "")
            rating = f"评分{activity['rating']}" if activity.get("rating") else "暂无评分"
            start_time = activity.get("start_time", "")
            duration = activity.get("duration_minutes", 0)
            travel = activity.get("travel_from_prev_minutes", 0)
            distance = activity.get("distance_from_home", 0)
            activity_type = activity.get("type", "")

            type_label = {"play": "游玩", "eat": "用餐", "extra": "额外"}.get(activity_type, activity_type)
            lines.append(f"  {activity['order']}. [{type_label}] {venue_name} | {category} | {rating}")
            lines.append(f"     时间: {start_time} ({duration}分钟) | 前往耗时: {travel}分钟 | 距家{distance}米")
            lines.append(f"     地址: {activity.get('venue_address', '')}")
            lines.append(f"     坐标: {activity.get('venue_coords', [])}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _parse_plan_from_response(content: str, candidates: list[dict]) -> dict | None:
    """Extract JSON plan from LLM response text.

    The LLM should output a plan based on one of the candidates,
    enriched with natural language descriptions.
    """
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
            # Enrich activities with coords from candidates if missing
            _enrich_plan_from_candidates(plan, candidates)
            return plan
        return None
    except (json.JSONDecodeError, ValueError):
        logger.warning("plan_json_parse_failed", content_preview=content[:100])
        return None


def _enrich_plan_from_candidates(plan: dict, candidates: list[dict]) -> None:
    """Fill in missing coordinate/address data from candidate plans."""
    # Build a lookup of venue names to their data from candidates
    venue_lookup: dict[str, dict] = {}
    for candidate in candidates:
        for activity in candidate.get("activities", []):
            name = activity.get("venue_name", "")
            if name:
                venue_lookup[name] = activity

    for activity in plan.get("activities", []):
        venue_name = activity.get("venue_name", "")
        if venue_name in venue_lookup:
            source = venue_lookup[venue_name]
            # Fill in missing fields from spatial data
            if not activity.get("venue_coords"):
                activity["venue_coords"] = source.get("venue_coords", [])
            if not activity.get("venue_address"):
                activity["venue_address"] = source.get("venue_address", "")


# --- Graph Construction ---


def build_planning_graph() -> StateGraph:
    """Build and return the compiled planning graph with checkpointer."""
    builder = StateGraph(PlannerState)

    # Add nodes
    builder.add_node("parse_intent", parse_intent_node)
    builder.add_node("spatial_analysis", spatial_analysis_node)
    builder.add_node("select_and_narrate", select_and_narrate_node)
    builder.add_node("present_plan", present_plan_node)
    builder.add_node("execute_steps", execute_steps_node)
    builder.add_node("generate_share_card", generate_share_card_node)

    # Add edges
    builder.add_edge(START, "parse_intent")
    builder.add_edge("parse_intent", "spatial_analysis")
    builder.add_edge("spatial_analysis", "select_and_narrate")

    # Conditional: after plan selection
    builder.add_conditional_edges(
        "select_and_narrate",
        should_retry_or_continue,
        {
            "retry": "select_and_narrate",
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
