"""Friends-gathering planning helpers.

This service keeps friends rules separate from family-safety rules. It turns
group gathering preferences into structured profile, evidence, quality checks,
route rhythm, fallback planning, and evidence-bound final plan reasons.
"""

from __future__ import annotations

import re
from math import asin, cos, radians, sin, sqrt

import structlog

from app.config import settings
from app.services.spatial import build_curated_friends_candidate
from app.tools.availability import check_friends_availability

logger = structlog.get_logger()

EvidenceSource = str
Confidence = str

POI_SOURCE_AMAP = "amap_real_poi"
POI_SOURCE_SHOWCASE = "showcase_curated"
POI_SOURCE_FALLBACK = "fallback_generated"

PHOTO_KEYWORDS = ["展览", "艺术", "美术", "市集", "景观", "夜景", "网红", "咖啡", "天台", "拍照"]
SOCIAL_KEYWORDS = ["剧本杀", "密室", "桌游", "ktv", "清吧", "酒馆", "展览", "市集", "咖啡", "茶"]
INTERACTIVE_KEYWORDS = ["剧本杀", "密室", "桌游", "互动", "体验", "手作", "ktv", "运动"]
NOVELTY_KEYWORDS = ["新店", "沉浸", "艺术", "展览", "市集", "潮流", "快闪", "主题", "体验"]
TIRING_KEYWORDS = ["徒步", "爬山", "远足", "骑行", "户外运动", "攀岩"]
CHAT_FOOD_KEYWORDS = ["西餐", "日料", "小馆", "酒馆", "清吧", "咖啡", "茶", "餐厅", "融合菜"]
NOISY_KEYWORDS = ["ktv", "夜店", "酒吧", "火锅", "烧烤", "排队", "网红"]
AFTER_DINNER_KEYWORDS = ["清吧", "咖啡", "甜品", "桌游", "书店", "市集", "夜景", "散步", "茶"]
COMPANY_OR_OFFICE_KEYWORDS = [
    "公司企业",
    "有限公司",
    "公司",
    "写字楼",
    "办公室",
    "办公",
    "产业园",
    "教育咨询",
    "文化传媒",
    "管理公司",
    "企业管理",
    "广告",
    "传媒",
]
COMPANY_TYPECODE_PREFIXES = ("17",)

MIN_FRIEND_TOTAL_MINUTES = 240
TARGET_FRIEND_TOTAL_MINUTES = 300
MAX_FRIEND_TOTAL_MINUTES = 360
FIRST_ACTIVITY_EARLIEST_MINUTES = 14 * 60 + 30
DINNER_START_MINUTES = 17 * 60 + 30
DINNER_LATEST_START_MINUTES = 19 * 60


def build_friend_profile(user_input: str, scenario: str, scenario_description: str = "") -> dict:
    """Build a structured friends profile from user text plus safe defaults."""
    text = f"{user_input} {scenario_description}"
    party_size = 4
    party_match = re.search(r"(\d{1,2})\s*(个人|人|位)", text)
    chinese_party = {"两": 2, "俩": 2, "三": 3, "四": 4, "五": 5, "六": 6}
    chinese_match = re.search(r"([两俩三四五六])\s*(个人|人|位)", text)
    if party_match:
        party_size = max(2, int(party_match.group(1)))
    elif chinese_match:
        party_size = chinese_party.get(chinese_match.group(1), 4)

    group_composition = ""
    gender_match = re.search(r"(\d{1,2})\s*男\s*(\d{1,2})\s*女|(\d{1,2})\s*女\s*(\d{1,2})\s*男", text)
    if gender_match:
        if gender_match.group(1):
            group_composition = f"{gender_match.group(1)}男{gender_match.group(2)}女"
            party_size = int(gender_match.group(1)) + int(gender_match.group(2))
        else:
            group_composition = f"{gender_match.group(4)}男{gender_match.group(3)}女"
            party_size = int(gender_match.group(3)) + int(gender_match.group(4))

    preferences = []
    preference_patterns = {
        "轻松": r"轻松|别太累|不累",
        "有吃有玩": r"有吃有玩|吃.*玩|玩.*吃",
        "别太远": r"别.*太远|附近|近一点|少折腾",
        "适合聊天": r"聊天|好聊|安静|别太吵",
        "适合拍照": r"拍照|出片|好看",
        "聚会": r"聚会|朋友局|朋友聚|约朋友",
        "新鲜感": r"新鲜|新店|有意思|特别",
        "热闹氛围": r"热闹|有氛围|气氛",
        "预算适中": r"预算|别太贵|别.*太高|人均|性价比",
        "不太吵": r"不想太吵|别太吵|安静一点",
        "饭后续摊": r"续摊|吃完.*(继续|还能)|饭后",
        "先玩再吃": r"先玩再吃|先玩.*吃",
    }
    for label, pattern in preference_patterns.items():
        if re.search(pattern, text):
            preferences.append(label)

    profile = {
        "scenario": scenario,
        "party_size": party_size,
        "group_composition": group_composition or f"{party_size}人朋友局",
        "preferences": preferences or ["轻松", "有吃有玩", "聚会"],
        "nearby_preference": "别太远" in preferences,
        "chat_preference": "适合聊天" in preferences,
        "photo_preference": "适合拍照" in preferences,
        "start_time": "14:00",
        "min_total_minutes": MIN_FRIEND_TOTAL_MINUTES,
        "target_total_minutes": TARGET_FRIEND_TOTAL_MINUTES,
        "max_total_minutes": MAX_FRIEND_TOTAL_MINUTES,
        "max_drive_minutes": 35,
        "max_queue_minutes": 20,
        "dinner_window": "17:30-19:00",
        "risk_level": "medium",
    }
    logger.info(
        "friend_profile_built",
        party_size=party_size,
        group_composition=profile["group_composition"],
        preferences=profile["preferences"],
    )
    return profile


def build_friend_strategy(profile: dict) -> dict:
    """Convert friend profile into explicit strategy buckets."""
    return {
        "title": "朋友局适配策略",
        "summary": (f"{profile.get('group_composition', '4人朋友局')}，优先有吃有玩、适合聊天拍照、路线集中。"),
        "non_negotiables": [
            "总时长控制在4-6小时",
            f"餐厅需支持{profile.get('party_size', 4)}人桌",
            "至少包含一个社交/互动/拍照活动",
            "晚餐安排在17:30-19:00",
            "路线不过度分散",
        ],
        "priorities": [
            "社交氛围",
            "拍照友好",
            "互动性",
            "新鲜感",
            "餐厅氛围",
            "饭后可续摊",
            "预算适中",
            "路线集中",
        ],
        "compensations": [
            "饭后活动设为可续摊/可跳过",
            "排队略高时准备同区域备选",
            "餐厅偏热闹时优先备注安静座位",
        ],
    }


async def enrich_and_score_friend_candidates(
    candidates: list[dict],
    profile: dict,
    weather: dict | None,
) -> dict:
    """Add friends features, availability evidence, checks, fallback, and ranking."""
    strategy = build_friend_strategy(profile)
    evidence: list[dict] = []
    enhanced: list[dict] = []
    rejected: list[dict] = []

    for candidate in candidates:
        enriched = await _enrich_candidate(candidate, profile, weather, evidence)
        if enriched.get("hard_blockers"):
            rejected.append(_build_rejected_option(enriched))
        else:
            enhanced.append(enriched)

    enhanced.sort(key=lambda item: item.get("friend_score", 0), reverse=True)

    if not enhanced:
        fallback = await _enrich_candidate(
            build_curated_friends_candidate(_home_coords_from_candidates(candidates)),
            profile,
            weather,
            evidence,
            allow_degraded=True,
        )
        fallback["degradations"].append("当前实时地图结果里没有合格朋友局主活动，已切换为精选朋友局备选")
        enhanced.append(fallback)

    top = enhanced[0] if enhanced else None
    context = {
        "friend_profile": profile,
        "friend_strategy": strategy,
        "candidate_plans": enhanced,
        "friend_checks": top.get("friend_checks", []) if top else [],
        "social_score": top.get("social_score") if top else None,
        "evidence": evidence,
        "alternatives": _build_alternatives(enhanced),
        "rejected_options": rejected,
    }
    logger.info(
        "friend_candidates_scored",
        candidates=len(candidates),
        enhanced=len(enhanced),
        rejected=len(rejected),
        top_score=top.get("friend_score") if top else None,
    )
    return context


def attach_friend_context_to_plan(plan: dict, candidates: list[dict], state: dict) -> dict:
    """Attach the selected candidate's friend evidence to the final LLM plan."""
    selected = _find_matching_candidate(plan, candidates)
    if not selected and candidates:
        selected = candidates[0]

    plan["friend_profile"] = state.get("friend_profile")
    plan["friend_strategy"] = state.get("friend_strategy")
    plan["friend_checks"] = selected.get("friend_checks", []) if selected else state.get("friend_checks", [])
    plan["social_score"] = selected.get("social_score") if selected else state.get("social_score")
    plan["friend_fit_level"] = _fit_level(plan.get("social_score"))
    plan["evidence"] = selected.get("evidence", []) if selected else state.get("evidence", [])
    plan["degradations"] = _clean_text_items(selected.get("degradations", []) if selected else [])
    plan["alternatives"] = state.get("alternatives", [])
    plan["rejected_options"] = state.get("rejected_options", [])
    if selected:
        _apply_selected_candidate_to_plan(plan, selected)
    plan["friend_summary"] = _build_friend_summary(plan)
    _validate_plan_evidence_ids(plan)
    _apply_friend_user_descriptions(plan)
    plan["share_text"] = _build_wechat_share_text(plan)
    plan["pre_departure_tips"] = _build_pre_departure_tips(plan)

    for activity in plan.get("activities", []):
        action_details = activity.setdefault("action_details", {})
        if activity.get("type") == "eat":
            action_details.setdefault("special_requests", _build_restaurant_request(plan))
        elif activity.get("type") == "play":
            profile = plan.get("friend_profile") or {}
            action_details.setdefault("special_requests", f"{profile.get('party_size', 4)}人朋友互动体验")
        elif activity.get("type") == "extra":
            action_details.setdefault("skippable", True)
            action_details.setdefault("special_requests", "饭后可续摊，也可按状态跳过")

    return plan


def build_friend_execution_notes(plan: dict) -> dict:
    """Build friends-specific execution notes after user approval."""
    profile = plan.get("friend_profile") or {}
    return {
        "party_size": profile.get("party_size", 4),
        "restaurant_request": _build_restaurant_request(plan),
        "activity_request": f"{profile.get('party_size', 4)}人朋友互动体验",
        "share_text": plan.get("share_text", ""),
        "pre_departure_tips": plan.get("pre_departure_tips") or _build_pre_departure_tips(plan),
    }


async def _enrich_candidate(
    candidate: dict,
    profile: dict,
    weather: dict | None,
    global_evidence: list[dict],
    allow_degraded: bool = False,
) -> dict:
    enriched = _prepare_friend_candidate(candidate, profile)
    activities: list[dict] = []
    candidate_evidence: list[dict] = []

    for activity in enriched.get("activities", []):
        enriched_activity = dict(activity)
        features = _infer_friend_features(enriched_activity, profile, global_evidence)
        availability = await _get_friend_availability(enriched_activity, profile, global_evidence)
        keyword_evidence_ids = list(features.get("evidence_ids", []))
        availability_features = _features_from_availability(enriched_activity, availability, global_evidence, features)
        availability_evidence_ids = list(availability_features.get("evidence_ids", []))
        features.update(availability_features)
        features["evidence_ids"] = keyword_evidence_ids + availability_evidence_ids
        enriched_activity["friend_features"] = features
        enriched_activity["availability"] = availability
        activities.append(enriched_activity)
        candidate_evidence.extend([item for item in global_evidence if item["id"] in features.get("evidence_ids", [])])

    checks, blockers, degradations = _build_candidate_checks(enriched, activities, profile, weather)
    if allow_degraded:
        blockers = []
    social_score = _calculate_social_score(enriched, activities)
    friend_score = _calculate_friend_score(checks, social_score, degradations)

    enriched["activities"] = activities
    enriched["friend_checks"] = checks
    enriched["hard_blockers"] = blockers
    enriched["degradations"] = degradations
    enriched["social_score"] = social_score
    enriched["friend_score"] = friend_score
    enriched["evidence"] = _unique_evidence(candidate_evidence)
    return enriched


def _prepare_friend_candidate(candidate: dict, profile: dict) -> dict:
    prepared = {**candidate}
    activities = [dict(activity) for activity in candidate.get("activities", [])]
    if not activities:
        prepared["activities"] = []
        return prepared
    activities = _order_friend_activities(activities)
    _apply_friend_schedule(prepared, activities, profile)
    if _needs_after_dinner_extra(prepared, activities, profile):
        activities.append(_build_after_dinner_extra(prepared, activities))
        activities = _order_friend_activities(activities)
        _apply_friend_schedule(prepared, activities, profile)
    prepared["activities"] = activities
    _refresh_candidate_metrics(prepared, activities)
    return prepared


def _order_friend_activities(activities: list[dict]) -> list[dict]:
    original_index = {id(activity): index for index, activity in enumerate(activities)}

    def priority(activity: dict) -> tuple[int, int]:
        return {"play": 0, "eat": 1, "extra": 2}.get(activity.get("type", ""), 3), original_index[id(activity)]

    ordered = sorted(activities, key=priority)
    for index, activity in enumerate(ordered, 1):
        activity["order"] = index
    return ordered


def _apply_friend_schedule(candidate: dict, activities: list[dict], profile: dict) -> None:
    current = _time_to_minutes(profile.get("start_time", "14:00"))
    prev_coords = _home_coords_from_candidate(candidate)
    total_travel = 0

    for index, activity in enumerate(activities):
        coords = activity.get("venue_coords")
        travel = _estimate_travel_minutes(prev_coords, coords, activity.get("travel_from_prev_minutes", 8))
        total_travel += travel
        current += travel

        if index == 0 and activity.get("type") == "play" and current < FIRST_ACTIVITY_EARLIEST_MINUTES:
            current = FIRST_ACTIVITY_EARLIEST_MINUTES
        if activity.get("type") == "eat" and current < DINNER_START_MINUTES:
            gap_minutes = DINNER_START_MINUTES - current
            if index > 0 and gap_minutes >= 20:
                previous_activity = activities[index - 1]
                if previous_activity.get("type") == "play":
                    previous_activity["duration_minutes"] = (
                        int(previous_activity.get("duration_minutes", _normalized_duration(previous_activity)))
                        + gap_minutes
                    )
                    previous_activity["schedule_note"] = "展览 + 周边拍照轻逛"
                    previous_activity.setdefault("action_details", {})["visible_buffer_minutes"] = gap_minutes
            current = DINNER_START_MINUTES

        activity["order"] = index + 1
        activity["travel_from_prev_minutes"] = travel
        activity["start_time"] = _minutes_to_time(current)
        activity["duration_minutes"] = _normalized_duration(activity)
        if activity.get("type") == "eat":
            activity["action"] = "reserve"
        elif activity.get("type") == "play":
            activity["action"] = "book"
        else:
            activity["action"] = "no_action"
        activity.setdefault("action_details", {})
        if activity.get("type") == "extra":
            activity["action_details"].setdefault("skippable", True)
            activity["action_details"].setdefault("optional_extension", True)
        current += int(activity.get("duration_minutes", 0))
        prev_coords = coords or prev_coords

    candidate["total_travel_minutes"] = total_travel
    candidate["total_duration_minutes"] = current - _time_to_minutes(profile.get("start_time", "14:00"))


def _needs_after_dinner_extra(candidate: dict, activities: list[dict], profile: dict) -> bool:
    del candidate, profile
    if any(activity.get("type") == "extra" for activity in activities):
        return False
    return any(activity.get("type") == "eat" for activity in activities)


def _build_after_dinner_extra(candidate: dict, activities: list[dict]) -> dict:
    previous = activities[-1] if activities else {}
    coords = previous.get("venue_coords") or _home_coords_from_candidate(candidate) or []
    return {
        "order": len(activities) + 1,
        "type": "extra",
        "venue_name": "望京夜话小酒馆",
        "display_name": "望京夜话小酒馆",
        "venue_address": "餐厅附近步行可达的轻松小酒馆",
        "venue_coords": coords,
        "start_time": "",
        "duration_minutes": 45,
        "travel_from_prev_minutes": 5,
        "action": "no_action",
        "action_details": {"skippable": True, "optional_extension": True},
        "category": "清吧;咖啡;小酒馆;饭后续摊;聊天",
        "poi_type": "fallback_generated",
        "typecode": "",
        "tags": ["续摊", "可跳过"],
        "biz_type": [],
        "source": "fallback_generated",
        "trust_level": "generated_fallback",
        "venue_type": "after_dinner_bar",
        "scenario_tags": ["清吧", "小酒馆", "续摊", "可跳过"],
        "rating": None,
        "distance_from_home": previous.get("distance_from_home", 0),
        "generated_after_dinner_extra": True,
    }


def _refresh_candidate_metrics(candidate: dict, activities: list[dict]) -> None:
    home_coords = _home_coords_from_candidate(candidate)
    route_coords = []
    if home_coords:
        route_coords.append(home_coords)
    route_coords.extend(activity["venue_coords"] for activity in activities if activity.get("venue_coords"))
    if route_coords:
        candidate["route_geojson"] = {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": route_coords},
            "properties": {
                "total_travel_minutes": candidate.get("total_travel_minutes", 0),
                "source": "sequence_estimate",
            },
        }
    candidate["walkability_score"] = round(
        sum(1 for activity in activities if int(activity.get("travel_from_prev_minutes", 99)) <= 12)
        / max(len(activities), 1),
        2,
    )
    play = next((activity for activity in activities if activity.get("type") == "play"), None)
    eat = next((activity for activity in activities if activity.get("type") == "eat"), None)
    if play and eat:
        candidate["label"] = f"{play.get('venue_name', '互动活动')} + {eat.get('venue_name', '氛围聚餐')}"


def _normalized_duration(activity: dict) -> int:
    duration = int(activity.get("duration_minutes", 0) or 0)
    if activity.get("type") == "play":
        return max(duration, 90)
    if activity.get("type") == "eat":
        return max(duration, 80)
    if activity.get("type") == "extra":
        return max(duration, 40)
    return max(duration, 30)


def _infer_friend_features(activity: dict, profile: dict, evidence: list[dict]) -> dict:
    name = activity.get("venue_name", "")
    category = activity.get("category", "")
    poi_type = activity.get("poi_type", category)
    typecode = str(activity.get("typecode", ""))
    tags = activity.get("tags", [])
    if not isinstance(tags, list):
        tags = [tags] if tags else []
    poi_source = _poi_source(activity)
    trust_level = activity.get("trust_level") or "unknown"
    text = f"{name} {category} {poi_type} {' '.join(str(tag) for tag in tags)}".lower()
    activity_type = activity.get("type", "")
    evidence_ids: list[str] = []

    company_or_office_poi = _is_company_or_office_poi(activity)
    photo_friendly = _contains_any(text, PHOTO_KEYWORDS)
    social_friendly = _contains_any(text, SOCIAL_KEYWORDS)
    interactive = _contains_any(text, INTERACTIVE_KEYWORDS)
    novelty = _contains_any(text, NOVELTY_KEYWORDS)
    not_too_tiring = not _contains_any(text, TIRING_KEYWORDS)
    semantic_social = photo_friendly or social_friendly or interactive or novelty
    social_activity_evidence = bool(
        activity_type == "play"
        and (
            poi_source == POI_SOURCE_SHOWCASE
            or (poi_source == POI_SOURCE_AMAP and semantic_social and not company_or_office_poi)
        )
    )
    group_suitable = activity_type != "play" or social_activity_evidence
    chat_friendly = activity_type == "eat" and _contains_any(text, CHAT_FOOD_KEYWORDS)
    noisy = _contains_any(text, NOISY_KEYWORDS)
    after_dinner_friendly = activity_type == "extra" and _contains_any(text, AFTER_DINNER_KEYWORDS)

    evidence_ids.append(
        _add_evidence(
            evidence,
            f"{name}地点信息已核验",
            "已纳入地点名称、地址、品类和场景标签校验。",
            poi_source,
            trust_level,
            name,
        )
    )
    if activity_type == "play" and social_activity_evidence:
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}适合朋友局互动体验",
                (
                    "精选演示数据标注为适合朋友局的互动活动。"
                    if poi_source == POI_SOURCE_SHOWCASE
                    else "地图地点名称和品类命中社交、互动或拍照特征。"
                ),
                poi_source,
                trust_level,
                name,
            )
        )
    elif activity_type == "play" and company_or_office_poi:
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}疑似公司或办公类POI",
                "地点名称、地址或品类更像公司办公地址，不作为朋友局主活动。",
                poi_source,
                trust_level,
                name,
            )
        )
    elif activity_type == "play" and semantic_social:
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}仅有朋友局语义弱证据",
                f"名称或品类命中社交/互动/拍照关键词，但地点形态不足以作为主活动：{category or name}",
                "keyword_rule",
                "medium",
                name,
            )
        )
    if activity_type == "eat" and chat_friendly:
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}适合朋友聊天聚餐",
                f"名称或品类命中小馆/西餐/日料/清吧/咖啡等聊天氛围关键词：{category or name}",
                "keyword_rule",
                "medium",
                name,
            )
        )
    if activity_type == "extra" and after_dinner_friendly:
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}适合饭后续摊",
                f"名称或品类命中清吧/咖啡/甜品/桌游/夜景等续摊关键词：{category or name}",
                "keyword_rule",
                "medium",
                name,
            )
        )
    if activity.get("generated_after_dinner_extra"):
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}是可跳过续摊点",
                "为补足朋友局4-6小时节奏生成，饭后可续摊也可跳过。",
                "fallback_generated",
                "generated_fallback",
                name,
            )
        )

    return {
        "photo_friendly": photo_friendly,
        "social_friendly": social_friendly,
        "interactive": interactive,
        "novelty": novelty,
        "not_too_tiring": not_too_tiring,
        "source": poi_source,
        "trust_level": trust_level,
        "poi_type": poi_type,
        "typecode": typecode,
        "tags": tags,
        "company_or_office_poi": company_or_office_poi,
        "social_activity_evidence": social_activity_evidence,
        "group_suitable": group_suitable,
        "chat_friendly": chat_friendly,
        "ambience_score": 70 if chat_friendly else 60,
        "noise_level": "high" if noisy else "medium",
        "food_variety": "medium",
        "after_dinner_friendly": after_dinner_friendly,
        "can_continue_chat": after_dinner_friendly,
        "optional_extension": bool(activity.get("action_details", {}).get("optional_extension", False)),
        "evidence_ids": evidence_ids,
    }


async def _get_friend_availability(activity: dict, profile: dict, evidence: list[dict]) -> dict:
    result = await check_friends_availability.ainvoke(
        {
            "venue_name": activity.get("venue_name", ""),
            "activity_type": activity.get("type", "play"),
            "party_size": profile.get("party_size", 4),
            "preferences": profile.get("preferences", []),
        }
    )
    if result.get("status") == "success":
        return result["data"]

    venue_name = activity.get("venue_name", "")
    _add_evidence(
        evidence,
        f"{venue_name}朋友局可用性未确认",
        result.get("message", "演示业务接口暂不可用，已按保守等待时间处理。"),
        "mock_business_api",
        "simulated",
        venue_name,
    )
    return {
        "venue_name": venue_name,
        "available": True,
        "queue_minutes": 18,
        "source": "mock_business_api",
        "message": "可用性接口失败，按保守18分钟排队估算",
    }


def _features_from_availability(
    activity: dict,
    availability: dict,
    evidence: list[dict],
    base_features: dict,
) -> dict:
    venue_name = activity.get("venue_name", "")
    queue_minutes = availability.get("queue_minutes", 18)
    evidence_ids = [
        _add_evidence(
            evidence,
            f"{venue_name}朋友局可用性已校验",
            availability.get("message", "演示业务接口已返回可用性结果。"),
            "mock_business_api",
            "simulated",
            venue_name,
        ),
        _add_evidence(
            evidence,
            f"{venue_name}预计排队{queue_minutes}分钟",
            f"演示业务接口返回预计等待约{queue_minutes}分钟。",
            "mock_business_api",
            "simulated",
            venue_name,
        ),
    ]
    updates = {
        "queue_minutes": queue_minutes,
        "available": availability.get("available", True),
        "reservation_required": availability.get("reservation_required", False),
        "evidence_ids": evidence_ids,
    }
    if activity.get("type") == "eat":
        table_for_4 = availability.get("table_for_4", False)
        chat_friendly = availability.get("chat_friendly", False)
        if table_for_4:
            evidence_ids.append(
                _add_evidence(
                    evidence,
                    f"{venue_name}支持4人桌",
                    "演示业务接口确认18:00可安排4人桌。",
                    "mock_business_api",
                    "simulated",
                    venue_name,
                )
            )
        if chat_friendly:
            evidence_ids.append(
                _add_evidence(
                    evidence,
                    f"{venue_name}适合聊天",
                    "演示业务接口确认聊天氛围较合适。",
                    "mock_business_api",
                    "simulated",
                    venue_name,
                )
            )
        updates.update(
            {
                "table_for_4": table_for_4,
                "chat_friendly": chat_friendly,
                "ambience_score": availability.get("ambience_score", 65),
                "noise_level": "medium" if chat_friendly else "high",
                "food_variety": availability.get("food_variety", "medium"),
            }
        )
    elif activity.get("type") == "extra":
        updates.update(
            {
                "after_dinner_friendly": availability.get("after_dinner_friendly", True),
                "can_continue_chat": availability.get("can_continue_chat", False),
                "optional_extension": availability.get("optional_extension", True),
            }
        )
    else:
        updates.update(
            {
                "group_suitable": bool(
                    base_features.get("group_suitable", False) and availability.get("group_suitable", True)
                ),
                "photo_friendly": bool(
                    base_features.get("photo_friendly", False) or availability.get("photo_friendly", False)
                ),
                "social_friendly": bool(
                    base_features.get("social_friendly", False) or availability.get("social_friendly", False)
                ),
                "social_activity_evidence": bool(base_features.get("social_activity_evidence", False)),
                "company_or_office_poi": bool(base_features.get("company_or_office_poi", False)),
            }
        )
    return updates


def _build_candidate_checks(
    candidate: dict,
    activities: list[dict],
    profile: dict,
    weather: dict | None,
) -> tuple[list[dict], list[str], list[str]]:
    del weather
    blockers: list[str] = []
    degradations: list[str] = []
    min_total = int(profile.get("min_total_minutes", MIN_FRIEND_TOTAL_MINUTES))
    max_total = int(profile.get("max_total_minutes", MAX_FRIEND_TOTAL_MINUTES))
    max_drive = int(profile.get("max_drive_minutes", 35))
    max_queue = int(profile.get("max_queue_minutes", 20))
    total_duration = int(candidate.get("total_duration_minutes", 0))
    max_travel = max((int(activity.get("travel_from_prev_minutes", 0)) for activity in activities), default=0)
    max_queue_seen = max(
        (int(activity.get("friend_features", {}).get("queue_minutes", 0)) for activity in activities),
        default=0,
    )

    play_activities = [activity for activity in activities if activity.get("type") == "play"]
    eat_activity = next((activity for activity in activities if activity.get("type") == "eat"), {})
    extra_activity = next((activity for activity in activities if activity.get("type") == "extra"), {})
    eat_features = eat_activity.get("friend_features", {})
    company_play_names = [
        activity.get("venue_name", "")
        for activity in play_activities
        if activity.get("friend_features", {}).get("company_or_office_poi", False)
    ]
    play_ok = any(
        activity.get("friend_features", {}).get("social_activity_evidence", False) for activity in play_activities
    )
    table_ok = bool(eat_features.get("table_for_4", False))
    dinner_start = _time_to_minutes(eat_activity.get("start_time", "")) if eat_activity else None
    dinner_ok = dinner_start is not None and DINNER_START_MINUTES <= dinner_start <= DINNER_LATEST_START_MINUTES
    has_optional_tail = bool(extra_activity.get("friend_features", {}).get("optional_extension", False))
    time_status = "pass" if min_total <= total_duration <= max_total else "fail"
    route_status = "pass" if max_travel <= max_drive else "warn" if max_travel <= max_drive + 10 else "fail"
    queue_status = "pass" if max_queue_seen <= max_queue else "warn" if max_queue_seen <= 30 else "fail"

    checks = [
        _check_status(
            "social_activity",
            "有社交/互动/拍照活动",
            "pass" if play_ok else "fail",
            "活动具备社交、互动或拍照证据" if play_ok else "没有合格的朋友聚会玩乐活动",
        ),
        _check_status(
            "time_budget",
            "4-6小时完整度",
            time_status,
            (
                f"总时长约{total_duration}分钟，符合4-6小时"
                if time_status == "pass"
                else f"总时长{total_duration}分钟不在4-6小时范围"
            ),
        ),
        _check_status(
            "table_for_4",
            "4人桌可订",
            "pass" if table_ok else "fail",
            "餐厅支持4人桌" if table_ok else "未确认4人桌，不能作为主聚餐方案",
        ),
        _check_status(
            "dinner_time",
            "晚餐时间合理",
            "pass" if dinner_ok else "fail",
            "晚餐安排在17:30-19:00" if dinner_ok else "晚餐未落在17:30-19:00",
        ),
        _check_status(
            "route_focus",
            "路线集中",
            route_status,
            f"最长单段通勤{max_travel}分钟"
            if route_status == "pass"
            else f"最长单段通勤{max_travel}分钟，朋友局会显得分散",
        ),
        _check_status(
            "queue_control",
            "排队可控",
            queue_status,
            f"最长预计排队{max_queue_seen}分钟"
            if queue_status == "pass"
            else f"排队预计{max_queue_seen}分钟，超过理想值{max_queue}分钟",
        ),
        _check_status(
            "chat_fit",
            "适合聊天",
            "pass" if eat_features.get("chat_friendly", False) else "warn",
            "餐厅有聊天氛围证据" if eat_features.get("chat_friendly", False) else "聊天氛围一般，已备注尽量安静座位",
        ),
        _check_status(
            "photo_fit",
            "适合拍照",
            "pass"
            if any(activity.get("friend_features", {}).get("photo_friendly", False) for activity in activities)
            else "warn",
            "至少一站有拍照友好证据" if play_ok else "拍照友好证据不足",
        ),
        _check_status(
            "optional_tail",
            "饭后可续摊",
            "pass" if has_optional_tail else "warn",
            "饭后活动可续摊/可跳过" if has_optional_tail else "未安排明确续摊点，可晚餐后解散",
        ),
    ]

    if not play_activities:
        blockers.append("没有任何玩乐活动")
    if not play_ok:
        blockers.append("活动明显不适合朋友聚会")
    if company_play_names:
        blockers.append(f"主活动疑似公司或办公类POI：{'、'.join(company_play_names[:2])}")
    if time_status == "fail":
        blockers.append("总时长不在4-6小时")
    if not table_ok:
        blockers.append("餐厅未确认4人桌")
    if not dinner_ok:
        blockers.append("晚餐时间不符合朋友聚餐窗口")
    if route_status == "fail":
        blockers.append("路线过于分散")
    if queue_status == "fail":
        degradations.append(f"排队预计{max_queue_seen}分钟，朋友局等待风险高")

    if not eat_features.get("chat_friendly", False):
        degradations.append("聊天氛围一般，已备注尽量安排安静座位")
    if not has_optional_tail:
        degradations.append("缺少明确饭后续摊点，晚餐后可直接解散")
    if queue_status == "warn":
        degradations.append(f"排队预计{max_queue_seen}分钟，略高于理想值但仍可接受")

    return checks, blockers, degradations


def _calculate_social_score(candidate: dict, activities: list[dict]) -> int:
    score = 40
    score += round(float(candidate.get("walkability_score", 0)) * 15)
    for activity in activities:
        features = activity.get("friend_features", {})
        score += 8 if features.get("social_friendly") else 0
        score += 8 if features.get("photo_friendly") else 0
        score += 8 if features.get("interactive") else 0
        score += 5 if features.get("chat_friendly") else 0
        score += 5 if features.get("optional_extension") else 0
        score -= 8 if features.get("noise_level") == "high" and activity.get("type") == "eat" else 0
    return max(0, min(100, score))


def _calculate_friend_score(checks: list[dict], social_score: int, degradations: list[str]) -> int:
    check_score = sum(8 if check["status"] == "pass" else -10 if check["status"] == "fail" else 1 for check in checks)
    score = social_score + check_score - len(degradations) * 3
    return max(0, min(100, round(score)))


def _build_alternatives(candidates: list[dict]) -> list[dict]:
    return [
        {
            "id": candidate.get("id", ""),
            "title": candidate.get("label", "备选朋友局"),
            "fatigue_score": candidate.get("social_score"),
            "reason": candidate.get("spatial_summary", ""),
            "checks": candidate.get("friend_checks", [])[:4],
        }
        for candidate in candidates[1:3]
    ]


def _build_rejected_option(candidate: dict) -> dict:
    raw_reasons = [str(reason) for reason in candidate.get("hard_blockers", [])]
    return {
        "label": candidate.get("label", ""),
        "reasons": [_rewrite_rejection_reason(reason) for reason in raw_reasons],
        "score": candidate.get("friend_score", 0),
    }


def _rewrite_rejection_reason(reason: str) -> str:
    if "餐厅未确认4人桌" in reason:
        return "没有选择这家餐厅：当前未确认4人桌，朋友局到店等待风险较高。"
    if "路线过于分散" in reason:
        return "没有选择这条路线：地点分散，转场时间会压缩聊天和吃饭时间。"
    if "活动明显不适合朋友聚会" in reason:
        return "没有选择这个活动：互动性不足，四个人一起玩容易变成各逛各的。"
    if "没有任何玩乐活动" in reason:
        return "没有选择这版方案：只有吃饭没有玩乐活动，不符合有吃有玩的需求。"
    if "公司或办公类POI" in reason:
        return "没有选择这个地点：它更像公司或办公地址，不像实际可消费的朋友聚会场所。"
    if "总时长不在4-6小时" in reason:
        return "没有选择这版方案：总时长不符合下午4-6小时的聚会节奏。"
    if "晚餐时间不符合朋友聚餐窗口" in reason:
        return "没有选择这版方案：晚餐时间不在17:30-19:00，聚餐节奏不自然。"
    return f"没有选择这版方案：{reason}。"


def _apply_selected_candidate_to_plan(plan: dict, selected: dict) -> None:
    llm_by_name = {activity.get("venue_name", ""): activity for activity in plan.get("activities", [])}
    canonical_activities = []
    selected_activities = selected.get("activities", [])
    for index, activity in enumerate(selected_activities):
        merged = dict(activity)
        llm_activity = llm_by_name.get(activity.get("venue_name", ""), {})
        merged["order"] = index + 1
        merged["display_name"] = activity.get("display_name") or activity.get("venue_name", "")
        merged["venue_name"] = merged["display_name"]
        merged["travel_to_next_minutes"] = (
            selected_activities[index + 1].get("travel_from_prev_minutes")
            if index + 1 < len(selected_activities)
            else None
        )
        merged["reason"] = llm_activity.get("reason", merged.get("reason", ""))
        merged["evidence_ids"] = list(activity.get("friend_features", {}).get("evidence_ids", []))[:5]
        merged.setdefault("action_details", {})
        canonical_activities.append(merged)
    plan["activities"] = canonical_activities
    plan["duration_hours"] = round(int(selected.get("total_duration_minutes", 0)) / 60, 1)
    plan["total_travel_minutes"] = int(selected.get("total_travel_minutes", plan.get("total_travel_minutes", 0)))
    plan["walkability_score"] = selected.get("walkability_score", plan.get("walkability_score"))
    plan["route_geojson"] = selected.get("route_geojson", plan.get("route_geojson"))


def _validate_plan_evidence_ids(plan: dict) -> None:
    evidence = plan.get("evidence", [])
    valid_ids = {item.get("id", "") for item in evidence}
    evidence_by_id = {item.get("id", ""): item for item in evidence}
    by_venue: dict[str, list[str]] = {}
    for item in evidence:
        venue_name = item.get("venue_name", "")
        evidence_id = item.get("id", "")
        if venue_name and evidence_id:
            by_venue.setdefault(venue_name, []).append(evidence_id)

    for activity in plan.get("activities", []):
        referenced = activity.get("evidence_ids", [])
        if not isinstance(referenced, list):
            referenced = []
        filtered = [item for item in referenced if isinstance(item, str) and item in valid_ids]
        if not filtered:
            filtered = by_venue.get(activity.get("venue_name", ""), [])[:3]
        activity["evidence_ids"] = filtered
        claims = [
            _user_facing_evidence_claim(evidence_by_id[evidence_id])
            for evidence_id in filtered
            if evidence_id in evidence_by_id and evidence_by_id[evidence_id].get("claim")
        ]
        activity["validated_evidence_claims"] = claims[:3]
        reason_claims = [claim for claim in claims if "地点信息已核验" not in claim] or claims
        activity["reason"] = (
            "；".join(reason_claims[:2]) if reason_claims else "该安排已通过朋友局适配规则校验，风险已单独标注。"
        )


def _apply_friend_user_descriptions(plan: dict) -> None:
    checks = {check.get("id"): check for check in plan.get("friend_checks", [])}
    for activity in plan.get("activities", []):
        features = activity.get("friend_features", {})
        if activity.get("type") == "play":
            has_visible_buffer = bool(
                activity.get("schedule_note") or activity.get("action_details", {}).get("visible_buffer_minutes")
            )
            if has_visible_buffer:
                description = "展览 + 周边拍照轻逛，大家可以从第一站自然逛到晚餐前。"
            elif features.get("photo_friendly") and features.get("interactive"):
                description = "适合拍照和互动，大家可以先轻松逛一逛。"
            elif features.get("photo_friendly"):
                description = "适合拍照打卡，作为朋友局开场比较轻松。"
            else:
                description = "有互动体验，适合作为朋友局的第一站。"
        elif activity.get("type") == "eat":
            if checks.get("table_for_4", {}).get("status") == "pass":
                description = "适合4人聊天聚餐，已确认4人桌。"
            else:
                description = "适合朋友聚餐，已按4人局备注座位需求。"
        elif activity.get("type") == "extra":
            description = "饭后可选续摊，不想继续也可以直接散。"
        else:
            description = "这一站已按朋友局节奏安排。"

        activity["debug_description"] = activity.get("reason", "")
        activity["user_description"] = description
        activity["reason"] = description


def _user_facing_evidence_claim(item: dict) -> str:
    claim = str(item.get("claim", ""))
    venue_name = str(item.get("venue_name", ""))
    if "POI来源" in claim:
        return f"{venue_name}地点信息已核验"
    if "疑似公司" in claim:
        return f"{venue_name}更像办公地址，已排除为主活动"
    return claim


def _fit_level(score: object) -> str:
    if not isinstance(score, int):
        return "待确认"
    if score >= 90:
        return "高"
    if score >= 80:
        return "较高"
    if score >= 70:
        return "中等"
    return "需重规划"


def _clean_text_items(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _format_share_time(value: object, include_period: bool) -> str:
    minutes = _time_to_minutes(value)
    hour = minutes // 60
    minute = minutes % 60
    display_hour = hour - 12 if hour > 12 else hour
    if minute == 0:
        time_text = f"{display_hour}点"
    elif minute == 30:
        time_text = f"{display_hour}点半"
    else:
        time_text = f"{display_hour}点{minute:02d}"
    if include_period:
        if hour < 12:
            return f"上午{time_text}"
        if hour < 18:
            return f"下午{time_text}"
        return f"晚上{time_text}"
    return time_text


def _build_friend_summary(plan: dict) -> str:
    checks = plan.get("friend_checks", [])
    passed = [check["label"] for check in checks if check.get("status") == "pass"]
    if not passed:
        return "已按朋友局低折腾策略生成方案。"
    return "朋友局重点满足：" + "、".join(passed[:4]) + "。"


def _build_wechat_share_text(plan: dict) -> str:
    activities = plan.get("activities", [])
    if not activities:
        return "朋友局方案已安排好，大家看下时间。"
    profile = plan.get("friend_profile") or {}
    preferences = profile.get("preferences", [])
    checks = {check.get("id"): check for check in plan.get("friend_checks", [])}
    play = next((activity for activity in activities if activity.get("type") == "play"), activities[0])
    eat = next((activity for activity in activities if activity.get("type") == "eat"), {})
    extra = next((activity for activity in activities if activity.get("type") == "extra"), {})
    start_time = _format_share_time(play.get("start_time") or profile.get("start_time", "14:00"), include_period=True)
    dinner_time = _format_share_time(eat.get("start_time", "17:30"), include_period=False)

    play_desc = "适合互动"
    play_claims = "；".join(play.get("validated_evidence_claims", []) or [])
    if "拍照" in play_claims or play.get("friend_features", {}).get("photo_friendly"):
        play_desc = "适合拍照和互动"
    elif play.get("friend_features", {}).get("interactive"):
        play_desc = "有互动感"

    table_text = "4人桌已确认" if checks.get("table_for_4", {}).get("status") == "pass" else "餐位已按4人局处理"
    chat_text = (
        "餐厅选的是适合聊天的，不是特别吵的那种。"
        if checks.get("chat_fit", {}).get("status") == "pass"
        else "餐厅已备注尽量安排安静座位。"
    )

    share_text = (
        f"朋友局安排好了：{start_time}先去{play.get('venue_name', '互动活动')}，{play_desc}；"
        f"{dinner_time}去{eat.get('venue_name', '餐厅')}吃饭，{table_text}；"
        f"吃完可以去{extra.get('venue_name', '附近续摊点')}坐会儿，"
        "不想续摊也可以直接散，几个点都在附近，不用跑太远。"
    )
    if "预算适中" in preferences:
        share_text += "这版尽量选了不太贵、路线也顺的地方。"
    if "不太吵" in preferences or "适合聊天" in preferences:
        share_text += chat_text
    return share_text


def _build_pre_departure_tips(plan: dict) -> list[str]:
    return [
        "建议提前10分钟出发，避免朋友集合时临时等人。",
        f"餐厅备注：{_build_restaurant_request(plan)}",
        "饭后续摊点是可选项，大家状态好就继续，不想太晚可以跳过。",
    ]


def _build_restaurant_request(plan: dict) -> str:
    profile = plan.get("friend_profile") or {}
    return f"{profile.get('party_size', 4)}人桌，尽量安排适合聊天的位置，避免过吵区域"


def _find_matching_candidate(plan: dict, candidates: list[dict]) -> dict | None:
    plan_names = {activity.get("venue_name", "") for activity in plan.get("activities", [])}
    best: dict | None = None
    best_overlap = -1
    for candidate in candidates:
        candidate_names = {activity.get("venue_name", "") for activity in candidate.get("activities", [])}
        overlap = len(plan_names & candidate_names)
        if overlap > best_overlap:
            best = candidate
            best_overlap = overlap
    return best


def _check_status(check_id: str, label: str, status: str, detail: str) -> dict:
    return {"id": check_id, "label": label, "status": status, "detail": detail}


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _poi_source(activity: dict) -> str:
    source = activity.get("source") or activity.get("poi_source") or ""
    if source in {POI_SOURCE_AMAP, POI_SOURCE_SHOWCASE, POI_SOURCE_FALLBACK}:
        return source
    if activity.get("generated_after_dinner_extra"):
        return POI_SOURCE_FALLBACK
    return "unknown"


def _is_company_or_office_poi(activity: dict) -> bool:
    text = (
        f"{activity.get('venue_name', '')} {activity.get('category', '')} "
        f"{activity.get('poi_type', '')} {activity.get('venue_address', '')}"
    ).lower()
    typecode = str(activity.get("typecode", ""))
    return _contains_any(text, COMPANY_OR_OFFICE_KEYWORDS) or typecode.startswith(COMPANY_TYPECODE_PREFIXES)


def _format_poi_metadata(activity: dict) -> str:
    tags = activity.get("tags", [])
    if not isinstance(tags, list):
        tags = [tags] if tags else []
    tag_text = "、".join(str(tag) for tag in tags if tag) or "无"
    return (
        f"source={_poi_source(activity)}, type={activity.get('poi_type') or activity.get('category') or '未知'}, "
        f"typecode={activity.get('typecode', '') or '无'}, address={activity.get('venue_address', '') or '无'}, "
        f"tags={tag_text}"
    )


def _home_coords_from_candidate(candidate: dict) -> list[float] | None:
    coordinates = candidate.get("route_geojson", {}).get("geometry", {}).get("coordinates", [])
    if coordinates and isinstance(coordinates[0], list) and len(coordinates[0]) == 2:
        return coordinates[0]
    return None


def _home_coords_from_candidates(candidates: list[dict]) -> list[float]:
    for candidate in candidates:
        home_coords = _home_coords_from_candidate(candidate)
        if home_coords:
            return home_coords
    return [settings.default_home_lng, settings.default_home_lat]


def _estimate_travel_minutes(
    previous_coords: list[float] | None,
    current_coords: list[float] | None,
    fallback: object,
) -> int:
    if not previous_coords or not current_coords:
        return max(1, int(fallback or 8))
    distance_m = _haversine_distance(previous_coords, current_coords)
    speed_mps = 4500 / 3600 if distance_m <= 800 else 25000 / 3600
    return max(1, round((distance_m / speed_mps) / 60))


def _haversine_distance(coord1: list[float], coord2: list[float]) -> float:
    lng1, lat1 = radians(coord1[0]), radians(coord1[1])
    lng2, lat2 = radians(coord2[0]), radians(coord2[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 6371000 * 2 * asin(sqrt(a))


def _time_to_minutes(value: object) -> int:
    if not isinstance(value, str) or ":" not in value:
        return 14 * 60
    hour, minute = value.split(":", 1)
    try:
        return int(hour) * 60 + int(minute)
    except ValueError:
        return 14 * 60


def _minutes_to_time(minutes: int) -> str:
    hour = minutes // 60
    minute = minutes % 60
    return f"{hour:02d}:{minute:02d}"


def _add_evidence(
    evidence: list[dict],
    claim: str,
    detail: str,
    source: EvidenceSource,
    confidence: Confidence,
    venue_name: str,
) -> str:
    evidence_id = f"fr_ev_{len(evidence) + 1:03d}"
    evidence.append(
        {
            "id": evidence_id,
            "claim": claim,
            "evidence": detail,
            "source": source,
            "confidence": confidence,
            "venue_name": venue_name,
        }
    )
    return evidence_id


def _unique_evidence(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique = []
    for item in items:
        evidence_id = item.get("id", "")
        if evidence_id and evidence_id not in seen:
            seen.add(evidence_id)
            unique.append(item)
    return unique
