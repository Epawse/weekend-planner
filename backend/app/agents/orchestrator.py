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
from app.services.canvas import build_plan_canvas
from app.services.family import (
    attach_family_context_to_plan,
    build_execution_notes,
    build_family_profile,
    enrich_and_score_family_candidates,
)
from app.services.friends import (
    attach_friend_context_to_plan,
    build_friend_execution_notes,
    build_friend_profile,
    enrich_and_score_friend_candidates,
)
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

    family_profile = None
    family_strategy = None
    friend_profile = None
    friend_strategy = None
    if scenario == "family":
        family_profile = build_family_profile(user_input, scenario, scenario_description)
        family_strategy = {
            "title": "家庭安心策略",
            "summary": (
                f"{family_profile['party_size']}人出行，孩子{family_profile['child_age']}岁，"
                f"饮食目标：{family_profile['diet_goal']}，优先少步行、少排队。"
            ),
        }
        writer(
            {
                "type": "family_profile",
                "data": {
                    "message": (
                        f"已识别家庭需求：{family_profile['party_size']}人，"
                        f"孩子{family_profile['child_age']}岁，{family_profile['diet_goal']}"
                    ),
                    "family_profile": family_profile,
                },
            }
        )
    elif scenario == "friends":
        friend_profile = build_friend_profile(user_input, scenario, scenario_description)
        friend_strategy = {
            "title": "朋友局适配策略",
            "summary": (
                f"{friend_profile['group_composition']}，偏好："
                f"{'、'.join(friend_profile.get('preferences', []))}。"
            ),
        }
        writer(
            {
                "type": "friend_profile",
                "data": {
                    "message": (
                        f"已识别朋友局需求：{friend_profile['group_composition']}，"
                        f"偏好{'、'.join(friend_profile.get('preferences', []))}"
                    ),
                    "friend_profile": friend_profile,
                },
            }
        )

    return {
        "scenario": scenario,
        "scenario_description": scenario_description,
        "family_profile": family_profile,
        "family_strategy": family_strategy,
        "friend_profile": friend_profile,
        "friend_strategy": friend_strategy,
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


async def family_analysis_node(state: PlannerState) -> dict:
    """Apply family-safety rules before LLM narration."""
    if state.get("scenario") != "family":
        return {}

    writer = get_stream_writer()
    profile = state.get("family_profile") or build_family_profile(
        state["user_input"],
        state.get("scenario", "family"),
        state.get("scenario_description", ""),
    )

    writer(
        {
            "type": "family_strategy",
            "data": {
                "message": "正在启用家庭安心策略：低步行、低排队、亲子适配、健康餐优先",
                "family_profile": profile,
            },
        }
    )

    context = await enrich_and_score_family_candidates(
        candidates=state.get("candidate_plans", []),
        profile=profile,
        weather=state.get("weather"),
    )

    writer(
        {
            "type": "family_filter_result",
            "data": {
                "message": (
                    f"家庭安心校验完成：保留 {len(context['candidate_plans'])} 个方案，"
                    f"排除 {len(context['rejected_options'])} 个高风险选项"
                ),
                "family_checks": context["family_checks"],
                "fatigue_score": context["fatigue_score"],
                "rejected_options": context["rejected_options"],
            },
        }
    )

    return context


async def friends_analysis_node(state: PlannerState) -> dict:
    """Apply friends-gathering rules before LLM narration."""
    if state.get("scenario") != "friends":
        return {}

    writer = get_stream_writer()
    profile = state.get("friend_profile") or build_friend_profile(
        state["user_input"],
        state.get("scenario", "friends"),
        state.get("scenario_description", ""),
    )

    writer(
        {
            "type": "friend_strategy",
            "data": {
                "message": "正在启用朋友局策略：社交互动、拍照友好、4人桌、路线集中、饭后可续摊",
                "friend_profile": profile,
            },
        }
    )

    context = await enrich_and_score_friend_candidates(
        candidates=state.get("candidate_plans", []),
        profile=profile,
        weather=state.get("weather"),
    )

    writer(
        {
            "type": "friend_filter_result",
            "data": {
                "message": (
                    f"朋友局适配校验完成：保留 {len(context['candidate_plans'])} 个方案，"
                    f"排除 {len(context['rejected_options'])} 个高风险选项"
                ),
                "friend_checks": context["friend_checks"],
                "social_score": context["social_score"],
                "rejected_options": context["rejected_options"],
            },
        }
    )

    return context


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

    scenario_context = ""
    if state.get("scenario") == "family":
        scenario_context = _format_family_context_for_llm(state)
    elif state.get("scenario") == "friends":
        scenario_context = _format_friend_context_for_llm(state)

    user_message = f"""用户需求: {user_input}

以下是经过空间分析验证的候选方案（已确认时间可行、路线最优）：

{candidates_text}

{scenario_context}

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
        plan = _attach_validated_context_to_plan(plan, candidates, state)
        writer({"type": "plan_generated", "data": {"message": "方案已生成", "plan_title": plan.get("title", "")}})
        return {
            "plan": plan,
            "plan_status": "presented",
            "messages": [AIMessage(content=response.content)],
        }
    else:
        logger.warning("plan_parse_failed", response_content=response.content[:200])
        fallback_plan = _build_template_plan_from_top_candidate(state, candidates)
        if fallback_plan:
            writer(
                {
                    "type": "plan_generated",
                    "data": {
                        "message": "模型输出格式异常，已使用已验证候选方案模板生成完整方案",
                        "plan_title": fallback_plan.get("title", ""),
                    },
                }
            )
            return {
                "plan": fallback_plan,
                "plan_status": "presented",
                "messages": [AIMessage(content=response.content)],
                "error": None,
            }
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

    plan_canvas = build_plan_canvas(state, plan)

    # Emit plan_ready event before interrupting
    writer(
        {
            "type": "plan_ready",
            "data": {
                "plan": plan,
                "plan_canvas": plan_canvas,
                "isochrone": state.get("isochrone"),
                "venues": state.get("candidate_venues", [])[:10],
                "family_profile": state.get("family_profile"),
                "family_strategy": state.get("family_strategy"),
                "family_checks": state.get("family_checks", []),
                "friend_profile": state.get("friend_profile"),
                "friend_strategy": state.get("friend_strategy"),
                "friend_checks": state.get("friend_checks", []),
                "social_score": state.get("social_score"),
                "fatigue_score": state.get("fatigue_score"),
                "evidence": state.get("evidence", []),
                "alternatives": state.get("alternatives", []),
                "rejected_options": state.get("rejected_options", []),
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
    family_notes = build_execution_notes(plan) if state.get("scenario") == "family" else {}
    friend_notes = build_friend_execution_notes(plan) if state.get("scenario") == "friends" else {}

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
                    "party_size": family_notes.get("party_size", friend_notes.get("party_size", 2)),
                    "special_requests": activity.get("action_details", {}).get(
                        "special_requests",
                        family_notes.get("restaurant_request", friend_notes.get("restaurant_request", "")),
                    ),
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
                    "family_note": activity.get("action_details", {}).get("special_requests", ""),
                    "friend_note": activity.get("action_details", {}).get("special_requests", ""),
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

    plan_canvas = build_plan_canvas(state, plan, status="done")

    writer(
        {
            "type": "all_complete",
            "data": {
                "summary": "所有预订已完成" if confirmations else "方案已确认",
                "share_text": share_text,
                "confirmations": confirmations,
                "pre_departure_tips": plan.get("pre_departure_tips", []),
                "family_summary": plan.get("family_summary", ""),
                "friend_summary": plan.get("friend_summary", ""),
                "plan_canvas": plan_canvas,
            },
        }
    )

    return {"plan_status": "completed", "plan_canvas": plan_canvas}


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
        if "family_score" in candidate:
            lines.append(f"- 家庭安心分: {candidate.get('family_score')}")
            lines.append(f"- 家庭疲劳度: {candidate.get('fatigue_score')} ({candidate.get('fatigue_level')})")
        if "friend_score" in candidate:
            lines.append(f"- 朋友局适配分: {candidate.get('friend_score')}")
            lines.append(f"- 社交适配分: {candidate.get('social_score')}")
        lines.append(f"- 空间特征: {candidate.get('spatial_summary', '')}")
        lines.append("")

        for check in candidate.get("family_checks", []):
            lines.append(f"  安心检查: {check.get('label')} = {check.get('status')} | {check.get('detail')}")
        for check in candidate.get("friend_checks", []):
            lines.append(f"  朋友局检查: {check.get('label')} = {check.get('status')} | {check.get('detail')}")
        if candidate.get("degradations"):
            lines.append(f"  降级处理: {'；'.join(candidate.get('degradations', []))}")
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
            features = activity.get("family_features", {})
            if features:
                lines.append(
                    "     家庭特征: "
                    f"排队{features.get('queue_minutes', '?')}分钟, "
                    f"儿童适配={features.get('child_friendly')}, "
                    f"来源={features.get('source')}, "
                    f"强亲子证据={features.get('strong_child_activity_evidence')}, "
                    f"低脂={features.get('diet_friendly')}, "
                    f"儿童椅={features.get('child_seat')}"
                )
            friend_features = activity.get("friend_features", {})
            if friend_features:
                lines.append(
                    "     朋友局特征: "
                    f"排队{friend_features.get('queue_minutes', '?')}分钟, "
                    f"4人桌={friend_features.get('table_for_4')}, "
                    f"聊天={friend_features.get('chat_friendly')}, "
                    f"拍照={friend_features.get('photo_friendly')}, "
                    f"互动={friend_features.get('interactive')}, "
                    f"来源={friend_features.get('source')}, "
                    f"可信社交主活动={friend_features.get('social_activity_evidence')}, "
                    f"可续摊={friend_features.get('optional_extension')}"
                )
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _format_family_context_for_llm(state: PlannerState) -> str:
    """Format family evidence and guardrails for evidence-grounded narration."""
    profile = state.get("family_profile") or {}
    evidence = state.get("evidence", [])
    rejected = state.get("rejected_options", [])
    alternatives = state.get("alternatives", [])

    lines = [
        "## 家庭安心约束",
        f"- 家庭人数: {profile.get('party_size', 3)}人",
        f"- 孩子年龄: {profile.get('child_age', 5)}岁",
        f"- 饮食目标: {profile.get('diet_goal', '清淡均衡')}",
        "- 必须保留候选方案中的活动顺序、开始时间和持续时间，不要把餐厅/甜品提前到首站。",
        "- 你只能基于下面 evidence 写推荐理由，不要创造儿童椅、排队、低脂、余票等新事实。",
        "",
        "## 可引用证据",
    ]
    for item in evidence[:30]:
        lines.append(
            f"- {item.get('id')}: {item.get('claim')} | {item.get('evidence')} "
            f"(source={item.get('source')}, confidence={item.get('confidence')})"
        )
    if rejected:
        lines.append("")
        lines.append("## 已排除/降级的高风险选项")
        for item in rejected[:5]:
            lines.append(f"- {item.get('label')}: {'；'.join(item.get('reasons', []))}")
    if alternatives:
        lines.append("")
        lines.append("## 备选方案")
        for item in alternatives:
            lines.append(f"- {item.get('title')}: {item.get('reason')}")
    return "\n".join(lines)


def _format_friend_context_for_llm(state: PlannerState) -> str:
    """Format friends evidence and guardrails for evidence-grounded narration."""
    profile = state.get("friend_profile") or {}
    evidence = state.get("evidence", [])
    rejected = state.get("rejected_options", [])
    alternatives = state.get("alternatives", [])

    lines = [
        "## 朋友局适配约束",
        f"- 人数: {profile.get('party_size', 4)}人",
        f"- 群体: {profile.get('group_composition', '4人朋友局')}",
        f"- 偏好: {'、'.join(profile.get('preferences', []))}",
        "- 必须保留候选方案中的活动顺序、开始时间和持续时间。",
        "- 默认节奏必须是体验/展览/互动活动 → 氛围聚餐 → 饭后轻活动。",
        "- 你只能基于下面 evidence 写推荐理由，不要创造4人桌、适合聊天、排队短、适合拍照等新事实。",
        "- 分享文案要适合发微信群，简洁明确，不要写成朋友圈文案。",
        "",
        "## 可引用证据",
    ]
    for item in evidence[:30]:
        lines.append(
            f"- {item.get('id')}: {item.get('claim')} | {item.get('evidence')} "
            f"(source={item.get('source')}, confidence={item.get('confidence')})"
        )
    if rejected:
        lines.append("")
        lines.append("## 已排除/降级的高风险选项")
        for item in rejected[:5]:
            lines.append(f"- {item.get('label')}: {'；'.join(item.get('reasons', []))}")
    if alternatives:
        lines.append("")
        lines.append("## 备选方案")
        for item in alternatives:
            lines.append(f"- {item.get('title')}: {item.get('reason')}")
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


def _attach_validated_context_to_plan(plan: dict, candidates: list[dict], state: PlannerState) -> dict:
    """Attach scenario evidence and guarantee a share_text fallback."""
    if state.get("scenario") == "family":
        plan = attach_family_context_to_plan(plan, candidates, state)
    elif state.get("scenario") == "friends":
        plan = attach_friend_context_to_plan(plan, candidates, state)
    _ensure_share_text(plan, state.get("scenario", "family"))
    return plan


def _build_template_plan_from_top_candidate(state: PlannerState, candidates: list[dict]) -> dict | None:
    """Build a complete plan from the top validated candidate when LLM JSON parsing fails."""
    if not candidates:
        return None

    selected = candidates[0]
    scenario = state.get("scenario", "family")
    feature_key = "family_features" if scenario == "family" else "friend_features"
    selected_activities = selected.get("activities", [])
    activities = []

    for index, activity in enumerate(selected_activities):
        features = activity.get(feature_key, {})
        activities.append(
            {
                "order": index + 1,
                "type": activity.get("type", "play"),
                "venue_name": activity.get("display_name") or activity.get("venue_name", ""),
                "display_name": activity.get("display_name") or activity.get("venue_name", ""),
                "venue_address": activity.get("venue_address", ""),
                "venue_coords": activity.get("venue_coords", []),
                "start_time": activity.get("start_time", ""),
                "duration_minutes": int(activity.get("duration_minutes", 0) or 0),
                "travel_to_next_minutes": (
                    selected_activities[index + 1].get("travel_from_prev_minutes")
                    if index + 1 < len(selected_activities)
                    else None
                ),
                "action": activity.get("action", "no_action"),
                "action_details": dict(activity.get("action_details") or {}),
                "reason": "",
                "user_description": activity.get("user_description", ""),
                "evidence_ids": list(features.get("evidence_ids", []))[:5],
                "family_features": activity.get("family_features"),
                "friend_features": activity.get("friend_features"),
                "poi_type": activity.get("poi_type"),
                "typecode": activity.get("typecode"),
                "tags": activity.get("tags", []),
                "source": activity.get("source"),
                "trust_level": activity.get("trust_level"),
            }
        )

    plan = {
        "title": selected.get("label") or ("家庭安心下午" if scenario == "family" else "轻松朋友局"),
        "duration_hours": round(int(selected.get("total_duration_minutes", 0) or 0) / 60, 1),
        "activities": activities,
        "total_travel_minutes": int(selected.get("total_travel_minutes", 0) or 0),
        "walkability_score": selected.get("walkability_score"),
        "route_geojson": selected.get("route_geojson"),
        "share_text": _build_fallback_share_text(scenario, activities),
    }
    return _attach_validated_context_to_plan(plan, candidates, state)


def _ensure_share_text(plan: dict, scenario: str) -> None:
    if plan.get("share_text"):
        return
    plan["share_text"] = _build_fallback_share_text(scenario, plan.get("activities", []))


def _build_fallback_share_text(scenario: str, activities: list[dict]) -> str:
    if not activities:
        return "方案已安排好，可以直接确认执行。"
    parts = [f"{activity.get('start_time')} {activity.get('venue_name')}" for activity in activities]
    if scenario == "friends":
        return f"我看好了，下午按这个走：{' → '.join(parts)}。饭后可选续摊，不想继续也可以直接散。"
    return f"下午家庭安排好了：{' → '.join(parts)}。餐厅已按清淡少油和家庭用餐备注，最后一站可按状态跳过。"


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
    builder.add_node("family_analysis", family_analysis_node)
    builder.add_node("friends_analysis", friends_analysis_node)
    builder.add_node("select_and_narrate", select_and_narrate_node)
    builder.add_node("present_plan", present_plan_node)
    builder.add_node("execute_steps", execute_steps_node)
    builder.add_node("generate_share_card", generate_share_card_node)

    # Add edges
    builder.add_edge(START, "parse_intent")
    builder.add_edge("parse_intent", "spatial_analysis")
    builder.add_edge("spatial_analysis", "family_analysis")
    builder.add_edge("family_analysis", "friends_analysis")
    builder.add_edge("friends_analysis", "select_and_narrate")

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
