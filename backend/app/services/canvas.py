"""Build user-facing Plan Canvas state from planner state."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.models.canvas import (
    CanvasCheck,
    CanvasChecks,
    CanvasFeedback,
    CanvasMap,
    CanvasMapMarker,
    CanvasMetrics,
    CanvasTimelineItem,
    EvidenceCard,
    ExecutionAction,
    FeedbackChangeSummary,
    FeedbackHistoryItem,
    PlanCanvasState,
    RejectedCanvasOption,
    ToolTask,
)

RAW_TOKEN_REPLACEMENTS = {
    "mock_business_api": "演示业务接口",
    "mock_availability": "演示业务接口",
    "mock_api": "演示业务接口",
    "Mock Availability API": "演示业务接口",
    "mock": "演示业务接口",
    "Mock": "演示业务接口",
    "showcase_curated": "精选演示数据",
    "Showcase curated": "精选演示数据",
    "fallback_generated": "系统备选建议",
    "fallback": "系统备选建议",
    "source=": "来源：",
    "POI来源为": "地点信息来自",
    "POI 来源为": "地点信息来自",
    "debug": "调试信息",
}

FORBIDDEN_DETAIL_PATTERNS = [
    re.compile(r"typecode=[^,，；\s]+"),
    re.compile(r"tags=无"),
    re.compile(r"raw_source=[^,，；\s]+"),
]


def build_plan_canvas(
    state: dict,
    plan: dict,
    session_id: str = "",
    status: str = "plan_ready",
    modification_notice: str | None = None,
) -> dict:
    """Build a serializable PlanCanvasState from the current planner state."""
    scenario = str(state.get("scenario") or plan.get("scenario") or "family")
    activities = _sorted_activities(plan.get("activities", []))
    timeline = _build_timeline(activities)
    markers = _build_map_markers(activities, timeline)
    canvas = PlanCanvasState(
        canvas_id=_build_canvas_id(session_id, plan, status),
        scenario="friends" if scenario == "friends" else "family",
        status=_normalize_status(status),
        title=_build_title(scenario, plan),
        summary=_build_summary(scenario, plan, activities, modification_notice),
        metrics=_build_metrics(scenario, plan, activities),
        timeline=timeline,
        checks=_build_checks(scenario, plan, state),
        evidence_cards=_build_evidence_cards(plan, timeline),
        rejected_options=_build_rejected_options(plan),
        map=CanvasMap(
            home_location=_tuple_coords(state.get("home_location", [116.481, 39.998])),
            markers=markers,
            route_geojson=plan.get("route_geojson"),
            route_notice=_route_notice(plan.get("route_geojson")),
        ),
        feedback=CanvasFeedback(
            quick_actions=_quick_actions(scenario),
            history=_build_feedback_history(state),
            change_summary=_build_feedback_change_summary(state),
        ),
        tool_tasks=_build_tool_tasks(scenario, plan, state),
        pending_actions=_build_pending_actions(scenario, plan, activities),
        execution_results=_build_execution_results(state),
        share_text=_scrub_user_text(str(plan.get("share_text") or "")),
        modification_notice=_scrub_user_text(modification_notice) if modification_notice else None,
    )
    return canvas.model_dump(mode="json")


def source_label(raw_source: object) -> str:
    """Map internal source names to user-facing labels."""
    source = str(raw_source or "")
    if source in {"amap_real_poi", "real_api"}:
        return "真实地图数据"
    if source == "showcase_curated":
        return "精选演示数据"
    if source in {"mock_business_api", "mock_api", "mock_availability"}:
        return "演示业务接口"
    if source in {"keyword_rule", "category_rule", "llm"}:
        return "规则推断"
    if source == "fallback_generated":
        return "系统备选建议"
    if source == "sequence_estimate":
        return "路线计算"
    if source == "voting_signal":
        return "投票信号"
    if source == "amap":
        return "真实地图数据"
    return "规则推断"


def scrub_user_text(value: str) -> str:
    """Public wrapper used by tests and feedback services."""
    return _scrub_user_text(value)


def _build_canvas_id(session_id: str, plan: dict, status: str) -> str:
    title_part = re.sub(r"\W+", "_", str(plan.get("title", "plan")))[:24].strip("_") or "plan"
    session_part = session_id or "local"
    return f"{session_part}_{title_part}_{status}"


def _normalize_status(status: str) -> str:
    if status in {"feedback_applied", "executing", "done"}:
        return status
    return "plan_ready"


def _sorted_activities(activities: object) -> list[dict]:
    if not isinstance(activities, list):
        return []
    return sorted([item for item in activities if isinstance(item, dict)], key=lambda item: int(item.get("order", 0)))


def _build_title(scenario: str, plan: dict) -> str:
    raw_title = str(plan.get("title", ""))
    if " + " in raw_title or "+" in raw_title:
        return "朋友局安排好了" if scenario == "friends" else "家庭安心下午"
    if scenario == "friends":
        if "朋友" in raw_title:
            return _scrub_user_text(raw_title)
        return "朋友局安排好了"
    if "家庭" in raw_title and "餐厅" not in raw_title:
        return _scrub_user_text(raw_title)
    return "家庭安心下午"


def _build_summary(
    scenario: str,
    plan: dict,
    activities: list[dict],
    modification_notice: str | None,
) -> str:
    scenario_summary = plan.get("friend_summary") if scenario == "friends" else plan.get("family_summary")
    if isinstance(scenario_summary, str) and scenario_summary.strip():
        base = scenario_summary.strip()
    elif activities:
        parts = [f"{activity.get('start_time', '')} 去{_display_name(activity)}" for activity in activities]
        if scenario == "friends":
            base = "朋友局安排好了：" + "，".join(parts) + "。几个点尽量集中，适合聊天拍照。"
        else:
            base = "家庭下午安排好了：" + "，".join(parts) + "。节奏按低疲劳、少排队和轻松收尾组织。"
    else:
        base = "方案已生成，可在下方查看完整计划。"
    if modification_notice:
        base = f"{modification_notice} {base}"
    return _scrub_user_text(base)


def _build_metrics(scenario: str, plan: dict, activities: list[dict]) -> CanvasMetrics:
    total_minutes = int(round(float(plan.get("duration_hours", 0) or 0) * 60))
    if total_minutes <= 0:
        total_minutes = _estimate_total_minutes(activities)
    travel_minutes = int(plan.get("total_travel_minutes", 0) or 0)
    route_label = "路线集中" if travel_minutes <= 15 else "路线适中" if travel_minutes <= 35 else "路线偏分散"
    if scenario == "friends":
        score = plan.get("social_score")
        fit_label = f"朋友局适配：{plan.get('friend_fit_level') or _score_label(score)}"
    else:
        fatigue_score = plan.get("fatigue_score")
        fit_label = f"家庭疲劳度：{_fatigue_label(fatigue_score)}"
    return CanvasMetrics(
        total_duration_text=_format_minutes(total_minutes),
        travel_time_text=f"{travel_minutes}分钟",
        end_time_text=_end_time_text(activities),
        fit_label=_scrub_user_text(fit_label),
        route_label=route_label,
    )


def _build_timeline(activities: list[dict]) -> list[CanvasTimelineItem]:
    items = []
    for index, activity in enumerate(activities, 1):
        timeline_id = f"timeline_{index}"
        marker_id = f"marker_{index}"
        items.append(
            CanvasTimelineItem(
                id=timeline_id,
                step=index,
                time=str(activity.get("start_time", "")),
                end_time=_activity_end_time(activity),
                duration_text=_activity_duration_text(activity),
                display_name=_display_name(activity),
                category_label=_activity_type_label(str(activity.get("type", ""))),
                user_description=_activity_description(activity),
                address=_scrub_user_text(str(activity.get("venue_address", ""))),
                map_marker_id=marker_id,
                evidence_ids=[
                    str(item) for item in activity.get("evidence_ids", []) if isinstance(item, str) and item.strip()
                ],
                actions=_activity_actions(activity),
            )
        )
    return items


def _build_map_markers(activities: list[dict], timeline: list[CanvasTimelineItem]) -> list[CanvasMapMarker]:
    markers = []
    timeline_by_index = {item.step - 1: item for item in timeline}
    for index, activity in enumerate(activities):
        coords = activity.get("venue_coords")
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            continue
        item = timeline_by_index.get(index)
        if item is None:
            continue
        markers.append(
            CanvasMapMarker(
                id=item.map_marker_id,
                timeline_item_id=item.id,
                step=item.step,
                type=_activity_marker_type(str(activity.get("type", ""))),
                coordinates=_tuple_coords(coords),
                display_name=item.display_name,
                category_label=item.category_label,
                user_description=item.user_description,
                address=item.address,
                source_label=source_label(activity.get("source")),
                schedule_text=f"{item.time}–{item.end_time}" if item.end_time else item.time,
                next_leg_text=_next_leg_text(activity),
                business_status=_business_status(activity),
                actions=item.actions,
            )
        )
    return markers


def _build_checks(scenario: str, plan: dict, state: dict) -> CanvasChecks:
    raw_checks = plan.get("friend_checks") if scenario == "friends" else plan.get("family_checks")
    if not raw_checks:
        raw_checks = state.get("friend_checks") if scenario == "friends" else state.get("family_checks")
    checks = CanvasChecks()
    if not isinstance(raw_checks, list):
        return checks
    for item in raw_checks:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "warn"))
        check = CanvasCheck(
            id=str(item.get("id") or f"check_{len(checks.passed) + len(checks.warnings) + len(checks.failed)}"),
            label=_scrub_user_text(str(item.get("label", "校验项"))),
            detail=_scrub_user_text(str(item.get("detail", ""))),
            status="pass" if status == "pass" else "fail" if status == "fail" else "warn",
        )
        if check.status == "pass":
            checks.passed.append(check)
        elif check.status == "fail":
            checks.failed.append(check)
        else:
            checks.warnings.append(check)
    return checks


def _build_evidence_cards(plan: dict, timeline: list[CanvasTimelineItem]) -> list[EvidenceCard]:
    evidence = plan.get("evidence", [])
    if not isinstance(evidence, list):
        return []
    timeline_by_evidence: dict[str, tuple[list[str], list[str]]] = {}
    for item in timeline:
        for evidence_id in item.evidence_ids:
            timeline_ids, marker_ids = timeline_by_evidence.setdefault(evidence_id, ([], []))
            timeline_ids.append(item.id)
            marker_ids.append(item.map_marker_id)

    cards = []
    for index, item in enumerate(evidence[:30], 1):
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("id") or f"evidence_{index}")
        related_timeline_ids, related_marker_ids = timeline_by_evidence.get(evidence_id, ([], []))
        cards.append(
            EvidenceCard(
                id=evidence_id,
                title=_evidence_title(item),
                source_label=source_label(item.get("source")),
                subject=_scrub_user_text(str(item.get("venue_name", ""))),
                detail=_scrub_user_text(str(item.get("evidence") or item.get("detail") or item.get("claim") or "")),
                related_timeline_ids=related_timeline_ids,
                related_marker_ids=related_marker_ids,
            )
        )
    return cards


def _build_rejected_options(plan: dict) -> list[RejectedCanvasOption]:
    rejected = plan.get("rejected_options", [])
    if not isinstance(rejected, list):
        return []
    options = []
    for index, item in enumerate(rejected[:8], 1):
        if not isinstance(item, dict):
            continue
        reasons = item.get("reasons", [])
        reason = "；".join(str(reason) for reason in reasons) if isinstance(reasons, list) else str(reasons or "")
        options.append(
            RejectedCanvasOption(
                id=f"rejected_{index}",
                name=_scrub_user_text(str(item.get("label") or item.get("name") or "未采用选项")),
                reason=_scrub_user_text(reason or "不符合当前场景质量门槛。"),
                source_label="规则推断",
            )
        )
    return options


def _build_feedback_history(state: dict) -> list[FeedbackHistoryItem]:
    raw_history = state.get("feedback_history", [])
    if not isinstance(raw_history, list):
        return []
    history = []
    for index, item in enumerate(raw_history, 1):
        if not isinstance(item, dict):
            continue
        history.append(
            FeedbackHistoryItem(
                id=str(item.get("id") or f"feedback_{index}"),
                label=_scrub_user_text(str(item.get("label") or item.get("category") or "修改")),
                user_text=_scrub_user_text(str(item.get("user_text") or "")),
                result_message=_scrub_user_text(str(item.get("result_message") or "")),
            )
        )
    return history


def _build_feedback_change_summary(state: dict) -> FeedbackChangeSummary | None:
    raw_summary = state.get("feedback_change_summary")
    if not isinstance(raw_summary, dict):
        return None
    return FeedbackChangeSummary(
        title=_scrub_user_text(str(raw_summary.get("title") or "已根据反馈调整")),
        result=_scrub_user_text(str(raw_summary.get("result") or "")),
        before=_scrub_user_text(str(raw_summary.get("before") or "")),
        after=_scrub_user_text(str(raw_summary.get("after") or "")),
        preserved=[
            _scrub_user_text(str(item))
            for item in raw_summary.get("preserved", [])
            if isinstance(item, str) and item.strip()
        ][:6],
        changed=[
            _scrub_user_text(str(item))
            for item in raw_summary.get("changed", [])
            if isinstance(item, str) and item.strip()
        ][:6],
        note=(_scrub_user_text(str(raw_summary.get("note"))) if raw_summary.get("note") else None),
    )


def _build_tool_tasks(scenario: str, plan: dict, state: dict) -> list[ToolTask]:
    checks = plan.get("friend_checks") if scenario == "friends" else plan.get("family_checks")
    if not isinstance(checks, list):
        checks = []
    passed = sum(1 for item in checks if isinstance(item, dict) and item.get("status") == "pass")
    warnings = sum(1 for item in checks if isinstance(item, dict) and item.get("status") == "warn")
    candidates = state.get("candidate_plans", [])
    venue_count = len(state.get("candidate_venues", []) or [])
    travel = int(plan.get("total_travel_minutes", 0) or 0)
    if scenario == "friends":
        return [
            ToolTask(
                id="task_activity",
                label="朋友活动检索",
                status="done",
                detail=_candidate_detail(venue_count, candidates),
            ),
            ToolTask(
                id="task_restaurant",
                label="4人桌餐厅检索",
                status="done",
                detail=_restaurant_task_detail(plan, "4人桌"),
            ),
            ToolTask(id="task_extra", label="续摊地点检索", status="done", detail=_extra_task_detail(plan)),
            ToolTask(id="task_route", label="路线集中校验", status="done", detail=f"总通勤约{travel}分钟"),
            ToolTask(
                id="task_availability",
                label="排队/余位/预约校验",
                status="done",
                detail=_queue_task_detail(plan),
            ),
            ToolTask(
                id="task_quality",
                label="朋友局质量门槛",
                status="warn" if warnings else "done",
                detail=f"{passed}项通过，{warnings}项提醒",
            ),
        ]
    return [
        ToolTask(
            id="task_activity",
            label="亲子活动检索",
            status="done",
            detail=_candidate_detail(venue_count, candidates),
        ),
        ToolTask(
            id="task_restaurant",
            label="清淡餐厅检索",
            status="done",
            detail=_restaurant_task_detail(plan, "家庭用餐"),
        ),
        ToolTask(id="task_extra", label="轻量收尾检索", status="done", detail=_extra_task_detail(plan)),
        ToolTask(id="task_route", label="路线疲劳度校验", status="done", detail=f"总通勤约{travel}分钟"),
        ToolTask(id="task_availability", label="儿童椅/排队/少油校验", status="done", detail=_queue_task_detail(plan)),
        ToolTask(
            id="task_quality",
            label="家庭安心质量门槛",
            status="warn" if warnings else "done",
            detail=f"{passed}项通过，{warnings}项提醒",
        ),
    ]


def _build_pending_actions(scenario: str, plan: dict, activities: list[dict]) -> list[ExecutionAction]:
    actions = []
    party_size = _party_size(plan, scenario)
    for activity in activities:
        action = str(activity.get("action", "no_action"))
        if action not in {"book", "reserve"}:
            continue
        target = _display_name(activity)
        request_detail = activity.get("action_details", {})
        if scenario == "friends" and activity.get("type") == "eat":
            label = "预订4人桌"
            next_step = "确认后锁定桌位并生成群聊通知"
        elif activity.get("type") == "eat":
            label = "预订家庭餐厅"
            next_step = "确认后备注儿童椅和清淡口味"
        else:
            label = "预约活动"
            next_step = "确认后生成预约记录"
        detail = (
            _scrub_user_text(str(request_detail.get("special_requests", "")))
            if isinstance(request_detail, dict)
            else ""
        )
        actions.append(
            ExecutionAction(
                id=f"pending_{activity.get('order', len(actions) + 1)}",
                label=label,
                status="pending",
                target=target,
                detail=detail or None,
                scheduled_time=str(activity.get("start_time") or "") or None,
                party_size=party_size,
                note=_execution_note(scenario, activity),
                next_step=next_step,
            )
        )
    if scenario == "friends" and any(activity.get("type") == "extra" for activity in activities):
        extra = next(activity for activity in activities if activity.get("type") == "extra")
        actions.append(
            ExecutionAction(
                id="pending_optional_tail",
                label="保留饭后续摊",
                status="pending",
                target=_display_name(extra),
                detail="不想继续也可以直接散。",
                scheduled_time=str(extra.get("start_time") or "") or None,
                party_size=party_size,
                note="可选续摊，不影响主方案完成。",
                next_step="确认后保留为群聊里的可选项",
            )
        )
    actions.append(
        ExecutionAction(
            id="pending_share",
            label="生成分享文案",
            status="pending",
            target="群聊分享" if scenario == "friends" else "家庭分享",
            detail=_scrub_user_text(str(plan.get("share_text") or "")),
            note="确认后可直接复制发送。",
            next_step="生成可发送文案",
        )
    )
    actions.append(
        ExecutionAction(
            id="pending_route",
            label="准备导航路线",
            status="pending",
            target="活动路线",
            note="按时间线顺序串联地点。",
            next_step="确认后打开路线准备状态",
        )
    )
    return actions


def _build_execution_results(state: dict) -> list[ExecutionAction]:
    raw_results = state.get("execution_results", [])
    if not isinstance(raw_results, list):
        return []
    results = []
    for index, item in enumerate(raw_results, 1):
        if not isinstance(item, dict):
            continue
        data = item.get("result", {}).get("data", {}) if isinstance(item.get("result"), dict) else {}
        status = "done" if item.get("result", {}).get("status", "success") == "success" else "failed"
        action = str(item.get("action", "no_action"))
        results.append(
            ExecutionAction(
                id=f"execution_{index}",
                label=_action_label(action),
                status=status,
                target=_scrub_user_text(str(item.get("venue", ""))),
                detail=_scrub_user_text(str(data.get("message", ""))) if isinstance(data, dict) else None,
                confirmation=(
                    str(data.get("confirmation_code", ""))
                    if isinstance(data, dict) and data.get("confirmation_code")
                    else None
                ),
                scheduled_time=_execution_result_time(data),
                party_size=_execution_result_party_size(data),
                note=_execution_result_note(action, data),
                next_step=_execution_result_next_step(action),
            )
        )
    return results


def _route_notice(route_geojson: object) -> str:
    source = None
    if isinstance(route_geojson, dict):
        properties = route_geojson.get("properties", {})
        if isinstance(properties, dict):
            source = properties.get("source")
    if source == "amap":
        return "已按导航路线展示"
    return "示意路线：按活动顺序连接，实际导航以地图为准"


def _quick_actions(scenario: str) -> list[str]:
    if scenario == "friends":
        return ["近一点", "换室内", "不要火锅", "早点回家"]
    return ["近一点", "换室内", "不要甜品", "早点回家"]


def _candidate_detail(venue_count: int, candidates: object) -> str:
    candidate_count = len(candidates) if isinstance(candidates, list) else 0
    if venue_count:
        return f"找到{venue_count}个地点，生成{candidate_count}个候选方案"
    return f"生成{candidate_count}个候选方案"


def _restaurant_task_detail(plan: dict, key_phrase: str) -> str:
    eat = next(
        (activity for activity in _sorted_activities(plan.get("activities", [])) if activity.get("type") == "eat"),
        None,
    )
    if not eat:
        return "未安排餐厅"
    status = _business_status(eat) or f"已校验{key_phrase}需求"
    return _scrub_user_text(status)


def _extra_task_detail(plan: dict) -> str:
    extras = [
        activity for activity in _sorted_activities(plan.get("activities", [])) if activity.get("type") == "extra"
    ]
    if not extras:
        return "未安排额外收尾，可按当前节奏结束"
    return f"保留{_display_name(extras[0])}作为可选收尾"


def _queue_task_detail(plan: dict) -> str:
    queues = []
    for activity in _sorted_activities(plan.get("activities", [])):
        features = activity.get("friend_features") or activity.get("family_features") or {}
        if isinstance(features, dict) and features.get("queue_minutes") is not None:
            queues.append(int(features.get("queue_minutes", 0)))
    if not queues:
        return "可用性已按当前业务规则校验"
    return f"最长预计等待{max(queues)}分钟"


def _evidence_title(item: dict) -> str:
    claim = str(item.get("claim") or "证据已校验")
    if "POI来源" in claim:
        claim = f"{item.get('venue_name', '')}地点信息已核验"
    return _scrub_user_text(claim)


def _display_name(activity: dict) -> str:
    return _scrub_user_text(str(activity.get("display_name") or activity.get("venue_name") or "未命名地点"))


def _activity_description(activity: dict) -> str:
    description = activity.get("user_description") or activity.get("reason") or "已通过当前场景校验。"
    return _scrub_user_text(str(description))


def _activity_duration_text(activity: dict) -> str:
    note = activity.get("schedule_note")
    if note:
        return _scrub_user_text(str(note))
    return _format_minutes(int(activity.get("duration_minutes", 0) or 0))


def _activity_type_label(activity_type: str) -> str:
    return {"play": "游玩", "eat": "用餐", "extra": "收尾"}.get(activity_type, "活动")


def _activity_marker_type(activity_type: str) -> str:
    if activity_type in {"play", "eat", "extra"}:
        return activity_type
    return "extra"


def _activity_actions(activity: dict) -> list[str]:
    activity_type = str(activity.get("type", ""))
    if activity_type == "play":
        return ["替换活动", "查看证据"]
    if activity_type == "eat":
        return ["替换餐厅", "确认订座"]
    return ["取消收尾", "查看证据"]


def _action_label(action: str) -> str:
    return {"book": "已预约活动", "reserve": "已完成预订", "order_delivery": "已安排配送"}.get(action, "已确认")


def _party_size(plan: dict, scenario: str) -> int | None:
    profile_key = "friend_profile" if scenario == "friends" else "family_profile"
    profile = plan.get(profile_key)
    if isinstance(profile, dict) and profile.get("party_size"):
        try:
            return int(profile["party_size"])
        except (TypeError, ValueError):
            return None
    return 4 if scenario == "friends" else 3


def _execution_note(scenario: str, activity: dict) -> str | None:
    details = activity.get("action_details", {})
    special_requests = ""
    if isinstance(details, dict):
        special_requests = str(details.get("special_requests") or "")
    if special_requests:
        return _scrub_user_text(f"备注：{special_requests}")
    if scenario == "friends" and activity.get("type") == "eat":
        return "备注：尽量安排适合聊天的位置。"
    if scenario == "family" and activity.get("type") == "eat":
        return "备注：儿童椅、少油/清淡优先。"
    return None


def _execution_result_time(data: object) -> str | None:
    if not isinstance(data, dict):
        return None
    value = data.get("time_slot") or data.get("delivery_time")
    return str(value) if value else None


def _execution_result_party_size(data: object) -> int | None:
    if not isinstance(data, dict) or data.get("party_size") is None:
        return None
    try:
        return int(data["party_size"])
    except (TypeError, ValueError):
        return None


def _execution_result_note(action: str, data: object) -> str | None:
    if not isinstance(data, dict):
        return None
    special_requests = data.get("special_requests")
    notes = data.get("notes")
    if action in {"reserve", "book"} and special_requests:
        return _scrub_user_text(f"备注：{special_requests}")
    if notes:
        return _scrub_user_text(str(notes))
    return None


def _execution_result_next_step(action: str) -> str:
    if action in {"reserve", "book"}:
        return "可取消 / 查看详情 / 导航前往"
    if action == "order_delivery":
        return "可查看配送状态"
    return "已加入当日路线"


def _business_status(activity: dict) -> str | None:
    features = activity.get("friend_features") or activity.get("family_features") or {}
    if not isinstance(features, dict):
        return None
    parts = []
    if activity.get("type") == "eat" and features.get("table_for_4"):
        parts.append("4人桌已确认")
    if activity.get("type") == "eat" and features.get("child_seat"):
        parts.append("儿童椅已备注")
    if features.get("queue_minutes") is not None:
        parts.append(f"排队预计{int(features.get('queue_minutes', 0))}分钟")
    if features.get("chat_friendly"):
        parts.append("适合聊天")
    if features.get("diet_friendly"):
        parts.append("清淡/轻食可选")
    return "，".join(parts) if parts else None


def _next_leg_text(activity: dict) -> str | None:
    travel = activity.get("travel_to_next_minutes")
    if travel is None:
        return None
    return f"下一站约{int(travel)}分钟"


def _format_minutes(minutes: int) -> str:
    if minutes <= 0:
        return "待确认"
    hours = minutes // 60
    rest = minutes % 60
    if hours and rest:
        return f"{hours}小时{rest}分钟"
    if hours:
        return f"{hours}小时"
    return f"{rest}分钟"


def _estimate_total_minutes(activities: list[dict]) -> int:
    if not activities:
        return 0
    total = 0
    for activity in activities:
        total += int(activity.get("duration_minutes", 0) or 0)
        total += int(activity.get("travel_from_prev_minutes", 0) or 0)
    return total


def _end_time_text(activities: list[dict]) -> str:
    if not activities:
        return "待确认"
    last = activities[-1]
    end_time = _activity_end_time(last)
    return f"约{end_time}" if end_time else "待确认"


def _activity_end_time(activity: dict) -> str:
    start = str(activity.get("start_time", ""))
    try:
        parsed = datetime.strptime(start, "%H:%M")
    except ValueError:
        return ""
    end = parsed + timedelta(minutes=int(activity.get("duration_minutes", 0) or 0))
    return end.strftime("%H:%M")


def _score_label(score: object) -> str:
    if not isinstance(score, (int, float)):
        return "高"
    if score >= 90:
        return "高"
    if score >= 80:
        return "较高"
    if score >= 70:
        return "中等"
    return "需调整"


def _fatigue_label(score: object) -> str:
    if not isinstance(score, (int, float)):
        return "低"
    if score <= 35:
        return "低"
    if score <= 65:
        return "中"
    return "高"


def _tuple_coords(value: object) -> tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return float(value[0]), float(value[1])
    return 116.481, 39.998


def _scrub_user_text(value: str | None) -> str:
    text = str(value or "")
    for raw, replacement in RAW_TOKEN_REPLACEMENTS.items():
        text = text.replace(raw, replacement)
    for pattern in FORBIDDEN_DETAIL_PATTERNS:
        text = pattern.sub("", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()
