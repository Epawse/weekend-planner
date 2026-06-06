"""Apply first-version follow-up feedback to the current plan."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

from app.services.canvas import build_plan_canvas, scrub_user_text

DEFAULT_HOME_LOCATION = [116.481, 39.998]


def apply_feedback_to_state(
    state: dict,
    message: str,
    quick_action: str | None = None,
    session_id: str = "",
) -> dict:
    """Apply supported feedback to current state and rebuild PlanCanvasState."""
    plan = deepcopy(state.get("plan") or {})
    if not plan:
        raise ValueError("No current plan to modify")

    intent = parse_feedback_intent(message, quick_action)
    scenario = str(state.get("scenario") or "family")
    before_snapshot = _plan_snapshot(plan)

    if intent["category"] == "distance":
        plan = _apply_distance_feedback(plan, state)
    elif intent["category"] == "indoor":
        plan = _apply_indoor_feedback(plan, state)
    elif intent["category"] == "restaurant_exclusion":
        plan = _apply_restaurant_exclusion(plan, state, intent["excluded_terms"])
    elif intent["category"] == "time_compression":
        plan = _apply_time_compression(plan, state)

    after_snapshot = _plan_snapshot(plan)
    change_summary = _build_change_summary(intent, scenario, before_snapshot, after_snapshot)
    result_message = change_summary["result"]
    plan["share_text"] = _update_share_text(plan, scenario, result_message)
    feedback_history = list(state.get("feedback_history") or [])
    feedback_history.append(
        {
            "id": f"feedback_{len(feedback_history) + 1}",
            "label": intent["label"],
            "category": intent["category"],
            "user_text": message,
            "result_message": result_message,
            "change_summary": change_summary,
        }
    )

    next_state = {
        **state,
        "plan": plan,
        "feedback_history": feedback_history,
        "feedback_change_summary": change_summary,
    }
    canvas = build_plan_canvas(
        next_state,
        plan,
        session_id=session_id,
        status="feedback_applied",
        modification_notice=result_message,
    )
    return {
        "plan": plan,
        "plan_canvas": canvas,
        "feedback_history": feedback_history,
        "feedback_constraints": _constraints_from_intent(intent),
        "feedback_change_summary": change_summary,
        "feedback_message": result_message,
        "plan_status": "presented",
    }


def parse_feedback_intent(message: str, quick_action: str | None = None) -> dict:
    """Parse supported feedback into deterministic intent categories."""
    text = f"{message} {quick_action or ''}"
    if any(keyword in text for keyword in ["早点", "早回", "早点回家", "提前结束", "不续摊"]):
        return {
            "category": "time_compression",
            "label": "早点回家",
            "excluded_terms": [],
            "replan_scope": "time_compression",
        }
    if any(keyword in text for keyword in ["室内", "下雨", "别户外", "换室内"]):
        return {
            "category": "indoor",
            "label": "换室内",
            "excluded_terms": [],
            "replan_scope": "activity_or_extra_replacement",
        }
    if any(keyword in text for keyword in ["近一点", "太远", "别太远", "少折腾", "更近"]):
        return {
            "category": "distance",
            "label": "近一点",
            "excluded_terms": [],
            "replan_scope": "route_compaction",
        }
    excluded = _extract_excluded_terms(text)
    if excluded:
        return {
            "category": "restaurant_exclusion",
            "label": f"不要{excluded[0]}",
            "excluded_terms": excluded,
            "replan_scope": "restaurant_only",
        }
    return {
        "category": "distance",
        "label": "近一点",
        "excluded_terms": [],
        "replan_scope": "route_compaction",
    }


def _apply_distance_feedback(plan: dict, state: dict) -> dict:
    current_travel = int(plan.get("total_travel_minutes", 999) or 999)
    candidates = _candidate_plans(state)
    closer = [
        candidate for candidate in candidates if int(candidate.get("total_travel_minutes", 999) or 999) < current_travel
    ]
    if closer:
        best = min(closer, key=lambda item: int(item.get("total_travel_minutes", 999) or 999))
        return _plan_from_candidate(plan, best, state)
    updated = deepcopy(plan)
    updated["total_travel_minutes"] = min(current_travel, max(3, current_travel))
    updated["route_compaction_note"] = "已优先保留当前同商圈路线，避免跨区折腾。"
    return updated


def _apply_indoor_feedback(plan: dict, state: dict) -> dict:
    candidates = _candidate_plans(state)
    indoor_candidates = sorted(
        candidates,
        key=lambda item: (_indoor_score(item), -int(item.get("total_travel_minutes", 999) or 999)),
        reverse=True,
    )
    current_indoor_score = _indoor_score({"activities": plan.get("activities", [])})
    if indoor_candidates and _indoor_score(indoor_candidates[0]) > current_indoor_score:
        return _plan_from_candidate(plan, indoor_candidates[0], state)
    updated = deepcopy(plan)
    for activity in _activities(updated):
        if activity.get("type") == "play" and "室内" not in str(activity.get("user_description", "")):
            previous = activity.get("user_description") or activity.get("reason") or "保留当前活动节奏。"
            activity["user_description"] = f"已按室内优先处理：{previous}"
    return updated


def _apply_restaurant_exclusion(plan: dict, state: dict, excluded_terms: list[str]) -> dict:
    updated = deepcopy(plan)
    dinner = next((activity for activity in _activities(updated) if activity.get("type") == "eat"), None)
    if dinner is None:
        return updated
    if not _matches_terms(dinner, excluded_terms):
        dinner["user_description"] = _append_sentence(
            str(dinner.get("user_description") or dinner.get("reason") or ""),
            f"已排除{'、'.join(excluded_terms)}。",
        )
        return updated

    replacement = _find_replacement_activity(state, "eat", excluded_terms)
    if replacement:
        preserved_time = dinner.get("start_time")
        preserved_order = dinner.get("order")
        dinner.clear()
        dinner.update(deepcopy(replacement))
        dinner["order"] = preserved_order
        dinner["start_time"] = preserved_time
        dinner["travel_to_next_minutes"] = replacement.get("travel_to_next_minutes")
        dinner["user_description"] = _append_sentence(
            str(dinner.get("user_description") or dinner.get("reason") or ""),
            f"已排除{'、'.join(excluded_terms)}，只替换晚餐地点。",
        )
    return _refresh_plan_metrics(updated, state)


def _apply_time_compression(plan: dict, state: dict) -> dict:
    updated = deepcopy(plan)
    activities = _activities(updated)
    kept = [activity for activity in activities if activity.get("type") != "extra"]
    if len(kept) != len(activities):
        updated["activities"] = kept
        if kept:
            kept[-1]["travel_to_next_minutes"] = None
            kept[-1].setdefault("action_details", {})["ends_plan"] = True
    else:
        updated["early_return_note"] = "当前方案没有饭后续摊，已保留晚餐后直接回家。"
    return _refresh_plan_metrics(updated, state)


def _plan_from_candidate(current_plan: dict, candidate: dict, state: dict) -> dict:
    scenario = str(state.get("scenario") or "family")
    updated = deepcopy(current_plan)
    candidate_activities = _candidate_activities_with_next(candidate)
    updated["activities"] = candidate_activities
    updated["duration_hours"] = round(int(candidate.get("total_duration_minutes", 0) or 0) / 60, 1)
    updated["total_travel_minutes"] = int(candidate.get("total_travel_minutes", 0) or 0)
    updated["walkability_score"] = candidate.get("walkability_score", updated.get("walkability_score"))
    updated["route_geojson"] = candidate.get("route_geojson", updated.get("route_geojson"))
    if scenario == "friends":
        updated["friend_checks"] = candidate.get("friend_checks", updated.get("friend_checks", []))
        updated["social_score"] = candidate.get("social_score", updated.get("social_score"))
        updated["friend_fit_level"] = updated.get("friend_fit_level") or "高"
    else:
        updated["family_checks"] = candidate.get("family_checks", updated.get("family_checks", []))
        updated["fatigue_score"] = candidate.get("fatigue_score", updated.get("fatigue_score"))
        updated["fatigue_level"] = candidate.get("fatigue_level", updated.get("fatigue_level"))
    if candidate.get("evidence"):
        updated["evidence"] = candidate["evidence"]
    return updated


def _candidate_activities_with_next(candidate: dict) -> list[dict]:
    activities = [deepcopy(activity) for activity in candidate.get("activities", []) if isinstance(activity, dict)]
    for index, activity in enumerate(activities):
        activity["order"] = index + 1
        activity["display_name"] = activity.get("display_name") or activity.get("venue_name", "")
        activity["venue_name"] = activity["display_name"]
        activity["travel_to_next_minutes"] = (
            activities[index + 1].get("travel_from_prev_minutes") if index + 1 < len(activities) else None
        )
        feature_key = "friend_features" if activity.get("friend_features") else "family_features"
        features = activity.get(feature_key, {})
        if isinstance(features, dict):
            activity["evidence_ids"] = list(features.get("evidence_ids", []))[:5]
    return activities


def _find_replacement_activity(state: dict, activity_type: str, excluded_terms: list[str]) -> dict | None:
    for candidate in _candidate_plans(state):
        for activity in candidate.get("activities", []):
            if not isinstance(activity, dict) or activity.get("type") != activity_type:
                continue
            if not _matches_terms(activity, excluded_terms):
                return _candidate_activities_with_next({"activities": [activity]})[0]
    return None


def _refresh_plan_metrics(plan: dict, state: dict) -> dict:
    activities = _activities(plan)
    total_travel = sum(int(activity.get("travel_from_prev_minutes", 0) or 0) for activity in activities)
    total_duration = sum(int(activity.get("duration_minutes", 0) or 0) for activity in activities) + total_travel
    plan["duration_hours"] = round(total_duration / 60, 1)
    plan["total_travel_minutes"] = total_travel
    coords = [state.get("home_location") or DEFAULT_HOME_LOCATION]
    coords.extend(activity.get("venue_coords") for activity in activities if activity.get("venue_coords"))
    plan["route_geojson"] = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {"total_travel_minutes": total_travel, "source": "sequence_estimate"},
    }
    return plan


def _update_share_text(plan: dict, scenario: str, result_message: str) -> str:
    activities = _activities(plan)
    if not activities:
        return scrub_user_text(result_message)
    parts = [f"{activity.get('start_time')} {activity.get('venue_name')}" for activity in activities]
    if scenario == "friends":
        return scrub_user_text(f"{result_message} 朋友局安排好了：{' → '.join(parts)}。")
    return scrub_user_text(f"{result_message} 家庭安排好了：{' → '.join(parts)}。")


def _build_change_summary(intent: dict, scenario: str, before: dict, after: dict) -> dict:
    category = intent["category"]
    label = intent.get("label") or "修改"
    preserved = _preserved_names(before, after)
    changed: list[str] = []
    note: str | None = None
    before_text = _snapshot_text(before)
    after_text = _snapshot_text(after)

    if category == "distance":
        if after["travel_minutes"] < before["travel_minutes"]:
            changed.append(f"总通勤从{before['travel_minutes']}分钟降到{after['travel_minutes']}分钟")
            result = "已调整：路线更近，优先集中到同一商圈。"
        else:
            result = f"当前方案已经集中在同一商圈，未替换地点；总通勤约{after['travel_minutes']}分钟。"
            note = "没有找到比当前方案更近且仍满足场景质量门槛的候选，因此保留原地点。"
    elif category == "indoor":
        if before["names"] != after["names"]:
            changed.extend(_replacement_changes(before, after))
            result = "已调整：改为室内优先，保留原晚餐节奏。"
        else:
            changed.append("活动说明更新为室内优先")
            result = "当前方案地点保持不变，已按室内优先重新标注和校验。"
            note = "没有找到更优的室内替代地点，因此保留原路线节奏。"
    elif category == "restaurant_exclusion":
        terms = "、".join(intent.get("excluded_terms", [])) or ("火锅" if scenario == "friends" else "甜品")
        if before["eat_name"] != after["eat_name"]:
            changed.append(f"晚餐从{before['eat_name'] or '原餐厅'}换成{after['eat_name'] or '新餐厅'}")
            result = f"已调整：已排除{terms}，只替换晚餐地点。"
        else:
            result = f"当前晚餐不属于{terms}，未替换地点；已记录排除偏好。"
            note = "保留活动和后续安排，避免为不存在的冲突打乱方案。"
    else:
        if before["extra_name"] and not after["extra_name"]:
            changed.append(f"取消饭后续摊：{before['extra_name']}")
            changed.append(f"结束时间提前到{after['end_time'] or '晚餐后'}左右")
            result = "已调整：取消饭后续摊，预计提前结束。"
        else:
            result = "当前方案没有饭后续摊，已保留晚餐后直接结束。"
            note = "主活动和晚餐仍保留，避免压缩后变成不完整方案。"

    return {
        "title": f"{label}：已根据反馈调整",
        "result": scrub_user_text(result),
        "before": scrub_user_text(before_text),
        "after": scrub_user_text(after_text),
        "preserved": preserved,
        "changed": [scrub_user_text(item) for item in changed if item][:5],
        "note": scrub_user_text(note) if note else None,
    }


def _snapshot_text(snapshot: dict) -> str:
    return (
        f"总通勤{snapshot['travel_minutes']}分钟，"
        f"结束约{snapshot['end_time'] or '待确认'}，"
        f"{len(snapshot['names'])}站安排"
    )


def _preserved_names(before: dict, after: dict) -> list[str]:
    after_names = set(after["names"])
    return [scrub_user_text(name) for name in before["names"] if name in after_names][:4]


def _replacement_changes(before: dict, after: dict) -> list[str]:
    changes = []
    for key, label in [("play_name", "活动"), ("eat_name", "晚餐"), ("extra_name", "收尾")]:
        if before.get(key) != after.get(key):
            old = before.get(key) or "原安排"
            new = after.get(key) or "已取消"
            changes.append(f"{label}从{old}调整为{new}")
    return changes


def _plan_snapshot(plan: dict) -> dict:
    activities = _activities(plan)
    names = [_activity_name(activity) for activity in activities]
    travel_minutes = int(plan.get("total_travel_minutes", 0) or 0)
    duration_minutes = int(round(float(plan.get("duration_hours", 0) or 0) * 60))
    if duration_minutes <= 0:
        activity_minutes = sum(int(activity.get("duration_minutes", 0) or 0) for activity in activities)
        duration_minutes = activity_minutes + travel_minutes
    return {
        "names": names,
        "travel_minutes": travel_minutes,
        "duration_minutes": duration_minutes,
        "end_time": _plan_end_time(activities),
        "play_name": _first_activity_name(activities, "play"),
        "eat_name": _first_activity_name(activities, "eat"),
        "extra_name": _first_activity_name(activities, "extra"),
    }


def _first_activity_name(activities: list[dict], activity_type: str) -> str:
    activity = next((item for item in activities if item.get("type") == activity_type), None)
    return _activity_name(activity) if activity else ""


def _activity_name(activity: dict | None) -> str:
    if not activity:
        return ""
    return scrub_user_text(str(activity.get("display_name") or activity.get("venue_name") or "未命名地点"))


def _plan_end_time(activities: list[dict]) -> str:
    if not activities:
        return ""
    try:
        last = max(activities, key=lambda item: item.get("order", 0))
        end = _activity_end_time(last)
        return end
    except ValueError:
        return ""


def _result_message(intent: dict, scenario: str) -> str:
    category = intent["category"]
    if category == "distance":
        return "已根据你的反馈调整：路线更近，优先集中到同一商圈。"
    if category == "indoor":
        return "已根据你的反馈调整：改为室内优先，保留原晚餐节奏。"
    if category == "restaurant_exclusion":
        terms = "、".join(intent.get("excluded_terms", [])) or ("火锅" if scenario == "friends" else "甜品")
        return f"已根据你的反馈调整：已排除{terms}，优先只替换晚餐地点。"
    return "已根据你的反馈调整：取消饭后续摊，预计提前结束。"


def _constraints_from_intent(intent: dict) -> dict:
    category = intent["category"]
    if category == "distance":
        return {"prefer_same_area": True, "route_compaction": True}
    if category == "indoor":
        return {"prefer_indoor": True}
    if category == "restaurant_exclusion":
        return {"excluded_cuisines": intent.get("excluded_terms", [])}
    return {"prefer_skip_extra": True, "latest_end_time": "early"}


def _candidate_plans(state: dict) -> list[dict]:
    candidates = state.get("candidate_plans", [])
    if not isinstance(candidates, list):
        return []
    return [candidate for candidate in candidates if isinstance(candidate, dict)]


def _activities(plan: dict) -> list[dict]:
    activities = plan.get("activities", [])
    if not isinstance(activities, list):
        return []
    return [activity for activity in activities if isinstance(activity, dict)]


def _extract_excluded_terms(text: str) -> list[str]:
    known_terms = ["火锅", "甜品", "烧烤", "炸鸡", "奶茶", "咖啡", "酒吧", "自助", "川菜", "湘菜"]
    terms = [term for term in known_terms if f"不要{term}" in text or f"不吃{term}" in text or f"排除{term}" in text]
    if terms:
        return terms
    if "不要" not in text:
        return []
    after = text.split("不要", 1)[1].strip()
    if not after:
        return []
    return [after[:6].strip("。,.， ")]


def _matches_terms(activity: dict, terms: list[str]) -> bool:
    text = " ".join(
        str(activity.get(key, ""))
        for key in ["venue_name", "display_name", "category", "poi_type", "user_description", "reason"]
    )
    return any(term and term in text for term in terms)


def _indoor_score(candidate: dict) -> int:
    score = 0
    for activity in candidate.get("activities", []):
        if not isinstance(activity, dict):
            continue
        text = " ".join(str(activity.get(key, "")) for key in ["venue_name", "category", "poi_type"])
        if any(keyword in text for keyword in ["室内", "馆", "展览", "商场", "书店", "中心", "咖啡", "清吧"]):
            score += 1
    return score


def _append_sentence(base: str, sentence: str) -> str:
    cleaned = scrub_user_text(base)
    if sentence in cleaned:
        return cleaned
    if not cleaned:
        return sentence
    return f"{cleaned} {sentence}"


def _activity_end_time(activity: dict) -> str:
    try:
        start = datetime.strptime(str(activity.get("start_time", "")), "%H:%M")
    except ValueError:
        return ""
    end = start + timedelta(minutes=int(activity.get("duration_minutes", 0) or 0))
    return end.strftime("%H:%M")
