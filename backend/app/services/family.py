"""Family-safety planning helpers.

This service turns family concerns into structured facts before LLM narration:
profile defaults, family feature enrichment, mock availability checks, evidence,
constraint handling, and fatigue scoring.
"""

from __future__ import annotations

import re
from math import asin, cos, radians, sin, sqrt

import structlog

from app.config import settings
from app.services.spatial import build_curated_family_candidate
from app.tools.availability import check_family_availability

logger = structlog.get_logger()

EvidenceSource = str
Confidence = str

STRONG_CHILD_INTENT_RE = re.compile(r"亲子乐园|儿童乐园|带孩子玩|娃能玩的地方|室内游乐|亲子馆|儿童活动|亲子活动")
EAT_FIRST_RE = re.compile(r"先吃|先喝|下午茶|先休息|先.*咖啡")
STRONG_CHILD_ACTIVITY_KEYWORDS = [
    "儿童乐园",
    "亲子乐园",
    "亲子馆",
    "科学馆",
    "儿童活动",
    "儿童中心",
    "室内游乐",
    "游乐场",
    "儿童手作",
    "儿童剧场",
    "儿童运动",
    "亲子农场",
    "亲子营地",
    "儿童营地",
    "儿童游乐",
]
WEAK_CHILD_ACTIVITY_KEYWORDS = ["公园", "商场", "书店", "咖啡", "甜品", "展览", "广场", "博物馆"]
CHILD_FRIENDLY_KEYWORDS = STRONG_CHILD_ACTIVITY_KEYWORDS + WEAK_CHILD_ACTIVITY_KEYWORDS + ["亲子", "儿童", "绘本"]
INDOOR_KEYWORDS = ["馆", "商场", "中心", "mall", "书店", "影院", "乐园", "亲子", "室内", "综合体"]
REST_SUPPORT_KEYWORDS = ["商场", "中心", "mall", "书店", "综合体", "公园", "广场"]
DIET_LOW_RISK_KEYWORDS = ["轻食", "沙拉", "健康", "低卡", "低脂", "素食", "简餐", "日料", "蒸", "粥"]
DIET_MEDIUM_RISK_KEYWORDS = ["粤菜", "茶餐", "清淡", "家常菜", "面", "粉", "粥"]
DIET_HIGH_RISK_KEYWORDS = [
    "甜品",
    "奶茶",
    "火锅",
    "烧烤",
    "炸鸡",
    "炸物",
    "川菜",
    "湘菜",
    "重辣",
    "自助",
    "高糖",
    "网红",
]
DIET_KEYWORDS = DIET_LOW_RISK_KEYWORDS + DIET_MEDIUM_RISK_KEYWORDS
NOISY_FOOD_KEYWORDS = ["火锅", "烧烤", "酒吧", "夜宵", "网红", "自助"]
BAD_WEATHER_KEYWORDS = ["雨", "雪", "霾", "沙", "大风", "暴"]
COMPANY_OR_OFFICE_KEYWORDS = ["公司企业", "有限公司", "公司", "写字楼", "办公室", "产业园", "广告装饰"]
COMPANY_TYPECODE_PREFIXES = ("17",)
POI_SOURCE_AMAP = "amap_real_poi"
POI_SOURCE_SHOWCASE = "showcase_curated"
POI_SOURCE_FALLBACK = "fallback_generated"
MIN_FAMILY_TOTAL_MINUTES = 240
TARGET_FAMILY_TOTAL_MINUTES = 300
MAX_FAMILY_TOTAL_MINUTES = 360
FIRST_PLAY_EARLIEST_MINUTES = 14 * 60 + 30
DINNER_START_MINUTES = 17 * 60
DINNER_LATEST_START_MINUTES = 18 * 60 + 30


def build_family_profile(user_input: str, scenario: str, scenario_description: str = "") -> dict:
    """Build a structured family profile from user text plus safe defaults."""
    text = f"{user_input} {scenario_description}"
    age_match = re.search(r"(\d{1,2})\s*岁", text)
    child_age = int(age_match.group(1)) if age_match else 5

    party_size = 3
    party_match = re.search(r"(\d{1,2})\s*(个人|人|口)", text)
    if party_match:
        party_size = max(2, int(party_match.group(1)))

    diet_goal = "减脂/轻食" if re.search(r"减肥|减脂|低脂|轻食|少油|健康", text) else "清淡均衡"
    nearby = bool(re.search(r"附近|别.*太远|不远|近一点|少折腾", text))

    profile = {
        "scenario": scenario,
        "party_size": party_size,
        "adults": max(1, party_size - 1),
        "children": 1,
        "child_age": child_age,
        "child_age_band": "4-6" if 4 <= child_age <= 6 else "child",
        "diet_goal": diet_goal,
        "nearby_preference": nearby,
        "start_time": "14:00",
        "min_total_minutes": MIN_FAMILY_TOTAL_MINUTES,
        "target_total_minutes": TARGET_FAMILY_TOTAL_MINUTES,
        "max_total_minutes": MAX_FAMILY_TOTAL_MINUTES,
        "max_drive_minutes": 30,
        "max_walk_minutes": 15,
        "max_queue_minutes": 15,
        "prefer_indoor": True,
        "need_child_seat": True,
        "risk_level": "low",
        "strong_child_intent": bool(STRONG_CHILD_INTENT_RE.search(text)),
        "prefer_eat_first": bool(EAT_FIRST_RE.search(text)),
    }
    logger.info("family_profile_built", child_age=child_age, party_size=party_size, diet_goal=diet_goal)
    return profile


def build_family_strategy(profile: dict) -> dict:
    """Convert the profile into explicit planning strategy buckets."""
    child_age = profile.get("child_age", 5)
    min_total = profile.get("min_total_minutes", MIN_FAMILY_TOTAL_MINUTES)
    max_total = profile.get("max_total_minutes", 330)
    max_drive = profile.get("max_drive_minutes", 30)
    max_queue = profile.get("max_queue_minutes", 15)
    return {
        "title": "家庭安心策略",
        "non_negotiables": [
            f"总时长控制在{round(min_total / 60, 1)}-{round(max_total / 60, 1)}小时",
            f"单段通勤不超过{max_drive}分钟",
            f"主活动不能明显不适合{child_age}岁孩子",
            "路线避免跨区域折腾",
        ],
        "priorities": [
            "低排队",
            "低步行",
            "室内/有休息区优先",
            f"餐厅支持{profile.get('diet_goal', '清淡均衡')}",
            "家庭用餐和儿童椅优先",
        ],
        "compensations": [
            f"排队超过{max_queue}分钟时优先换同类地点或准备备选",
            "儿童椅未完全确认时自动备注靠边座位",
            "低脂信息不足时选择可备注少油/清淡的餐厅",
            "孩子累了时最后一段设为可跳过",
        ],
    }


async def enrich_and_score_family_candidates(
    candidates: list[dict],
    profile: dict,
    weather: dict | None,
) -> dict:
    """Add family features, availability evidence, checks, alternatives, and ranking."""
    strategy = build_family_strategy(profile)
    evidence: list[dict] = []
    enhanced: list[dict] = []
    rejected: list[dict] = []

    for candidate in candidates:
        enriched = await _enrich_candidate(candidate, profile, weather, evidence)
        if enriched.get("hard_blockers"):
            rejected.append(
                {
                    "label": enriched.get("label", ""),
                    "reasons": enriched["hard_blockers"],
                    "score": enriched.get("family_score", 0),
                }
            )
        else:
            enhanced.append(enriched)

    enhanced.sort(key=lambda item: item.get("family_score", 0), reverse=True)

    if not enhanced and profile.get("strong_child_intent"):
        home_coords = _home_coords_from_candidates(candidates)
        fallback = await _enrich_candidate(
            build_curated_family_candidate(home_coords),
            profile,
            weather,
            evidence,
            allow_degraded=True,
        )
        fallback["degradations"].append("真实 AMap POI 未找到合格强亲子主活动，已启用 Showcase curated 家庭场馆")
        enhanced.append(fallback)
    elif not enhanced and candidates:
        fallback = await _enrich_candidate(candidates[0], profile, weather, evidence, allow_degraded=True)
        fallback["degradations"].append("未找到完全满足家庭硬约束的方案，已启用降级备选")
        enhanced.append(fallback)

    top = enhanced[0] if enhanced else None
    context = {
        "family_profile": profile,
        "family_strategy": strategy,
        "candidate_plans": enhanced,
        "family_checks": top.get("family_checks", []) if top else [],
        "fatigue_score": top.get("fatigue_score") if top else None,
        "evidence": evidence,
        "alternatives": _build_alternatives(enhanced),
        "rejected_options": rejected,
    }
    logger.info(
        "family_candidates_scored",
        candidates=len(candidates),
        enhanced=len(enhanced),
        rejected=len(rejected),
        top_score=top.get("family_score") if top else None,
    )
    return context


def attach_family_context_to_plan(plan: dict, candidates: list[dict], state: dict) -> dict:
    """Attach the selected candidate's family evidence to the LLM plan."""
    selected = _find_matching_candidate(plan, candidates)
    if not selected and candidates:
        selected = candidates[0]

    plan["family_profile"] = state.get("family_profile")
    plan["family_strategy"] = state.get("family_strategy")
    plan["family_checks"] = selected.get("family_checks", []) if selected else state.get("family_checks", [])
    plan["fatigue_score"] = selected.get("fatigue_score") if selected else state.get("fatigue_score")
    plan["fatigue_level"] = _fatigue_level(plan.get("fatigue_score"))
    plan["evidence"] = selected.get("evidence", []) if selected else state.get("evidence", [])
    plan["degradations"] = selected.get("degradations", []) if selected else []
    plan["alternatives"] = state.get("alternatives", [])
    plan["rejected_options"] = state.get("rejected_options", [])
    if selected:
        _apply_selected_candidate_to_plan(plan, selected)
    plan["family_summary"] = _build_family_summary(plan)
    plan["pre_departure_tips"] = _build_pre_departure_tips(plan)
    _validate_plan_evidence_ids(plan)

    for activity in plan.get("activities", []):
        if activity.get("type") == "eat":
            action_details = activity.setdefault("action_details", {})
            action_details.setdefault("special_requests", _build_restaurant_request(plan))
        elif activity.get("type") == "play":
            action_details = activity.setdefault("action_details", {})
            profile = plan.get("family_profile") or {}
            action_details.setdefault(
                "special_requests",
                f"{profile.get('party_size', 3)}人亲子活动，孩子{profile.get('child_age', 5)}岁",
            )

    return plan


def _apply_selected_candidate_to_plan(plan: dict, selected: dict) -> None:
    """Use backend-validated route/timing as the canonical final timeline."""
    llm_by_name = {activity.get("venue_name", ""): activity for activity in plan.get("activities", [])}
    canonical_activities = []
    selected_activities = selected.get("activities", [])
    for index, activity in enumerate(selected_activities):
        merged = dict(activity)
        llm_activity = llm_by_name.get(activity.get("venue_name", ""), {})
        merged["order"] = index + 1
        merged["travel_to_next_minutes"] = (
            selected_activities[index + 1].get("travel_from_prev_minutes")
            if index + 1 < len(selected_activities)
            else None
        )
        merged["reason"] = llm_activity.get("reason", merged.get("reason", ""))
        merged["evidence_ids"] = list(activity.get("family_features", {}).get("evidence_ids", []))[:5]
        merged.setdefault("action_details", {})
        canonical_activities.append(merged)

    plan["activities"] = canonical_activities
    plan["duration_hours"] = round(int(selected.get("total_duration_minutes", 0)) / 60, 1)
    plan["total_travel_minutes"] = int(selected.get("total_travel_minutes", plan.get("total_travel_minutes", 0)))
    plan["walkability_score"] = selected.get("walkability_score", plan.get("walkability_score"))
    plan["route_geojson"] = selected.get("route_geojson", plan.get("route_geojson"))


def _validate_plan_evidence_ids(plan: dict) -> None:
    """Ensure LLM-referenced evidence ids exist in backend-generated evidence."""
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
            evidence_by_id[evidence_id]["claim"]
            for evidence_id in filtered
            if evidence_id in evidence_by_id and evidence_by_id[evidence_id].get("claim")
        ]
        activity["validated_evidence_claims"] = claims[:3]
        activity["reason"] = _build_validated_reason(activity, claims)


def _build_validated_reason(activity: dict, claims: list[str]) -> str:
    if claims:
        return "；".join(claims[:2])
    if activity.get("type") == "eat":
        return "餐饮细节未完全确认，已在风险提醒中标注并添加少油/清淡备注。"
    if activity.get("type") == "play":
        return "主活动已通过家庭安心规则校验，未确认细节已在风险提醒中标注。"
    return "轻量收尾站点可根据孩子状态跳过。"


def build_execution_notes(plan: dict) -> dict:
    """Build family-specific execution notes after user approval."""
    profile = plan.get("family_profile") or {}
    return {
        "party_size": profile.get("party_size", 3),
        "restaurant_request": _build_restaurant_request(plan),
        "activity_request": f"{profile.get('party_size', 3)}人亲子活动，孩子{profile.get('child_age', 5)}岁",
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
    enriched = _prepare_family_candidate(candidate, profile)
    activities: list[dict] = []
    candidate_evidence: list[dict] = []

    for activity in enriched.get("activities", []):
        enriched_activity = dict(activity)
        features = _infer_family_features(enriched_activity, profile, global_evidence)
        availability = await _get_family_availability(enriched_activity, profile, global_evidence)
        keyword_evidence_ids = list(features.get("evidence_ids", []))
        availability_features = _features_from_availability(
            enriched_activity,
            availability,
            global_evidence,
            features,
        )
        availability_evidence_ids = list(availability_features.get("evidence_ids", []))
        features.update(availability_features)
        features["evidence_ids"] = keyword_evidence_ids + availability_evidence_ids
        enriched_activity["family_features"] = features
        enriched_activity["availability"] = availability
        activities.append(enriched_activity)
        candidate_evidence.extend([item for item in global_evidence if item["id"] in features.get("evidence_ids", [])])

    checks, blockers, degradations = _build_candidate_checks(enriched, activities, profile, weather)
    if allow_degraded:
        blockers = []
    fatigue_score = _calculate_fatigue_score(enriched, activities, weather)
    family_score = _calculate_family_score(checks, fatigue_score, degradations)

    enriched["activities"] = activities
    enriched["family_checks"] = checks
    enriched["hard_blockers"] = blockers
    enriched["degradations"] = degradations
    enriched["fatigue_score"] = fatigue_score
    enriched["fatigue_level"] = _fatigue_level(fatigue_score)
    enriched["family_score"] = family_score
    enriched["evidence"] = _unique_evidence(candidate_evidence)
    return enriched


def _prepare_family_candidate(candidate: dict, profile: dict) -> dict:
    """Apply family rhythm and minimum-time guardrails before facts are checked."""
    prepared = {**candidate}
    activities = [dict(activity) for activity in candidate.get("activities", [])]
    if not activities:
        prepared["activities"] = []
        return prepared

    activities = _order_family_activities(activities, profile)
    _apply_family_schedule(prepared, activities, profile)
    if _needs_light_extra(prepared, activities, profile):
        activities.append(_build_light_extra_activity(prepared, activities))
        activities = _order_family_activities(activities, profile)
        _apply_family_schedule(prepared, activities, profile)

    prepared["activities"] = activities
    _refresh_candidate_metrics(prepared, activities)
    return prepared


def _order_family_activities(activities: list[dict], profile: dict) -> list[dict]:
    """Keep the route in a family-natural order unless the user asked to eat first."""
    original_index = {id(activity): index for index, activity in enumerate(activities)}

    def priority(activity: dict) -> tuple[int, int, int]:
        activity_type = activity.get("type", "")
        if profile.get("prefer_eat_first"):
            type_rank = {"eat": 0, "play": 1, "extra": 2}.get(activity_type, 3)
        else:
            type_rank = {"play": 0, "eat": 1, "extra": 2}.get(activity_type, 3)
        strong_rank = 0 if _is_strong_child_activity(activity) else 1
        return type_rank, strong_rank, original_index.get(id(activity), 99)

    ordered = sorted(activities, key=priority)
    for index, activity in enumerate(ordered, 1):
        activity["order"] = index
    return ordered


def _apply_family_schedule(candidate: dict, activities: list[dict], profile: dict) -> None:
    """Rewrite start times so the plan reads like a realistic family afternoon."""
    current = _time_to_minutes(profile.get("start_time", "14:00"))
    prev_coords = _home_coords_from_candidate(candidate)
    total_travel = 0

    for index, activity in enumerate(activities):
        coords = activity.get("venue_coords")
        travel = _estimate_travel_minutes(prev_coords, coords, activity.get("travel_from_prev_minutes", 8))
        total_travel += travel
        current += travel

        if index == 0 and activity.get("type") == "play" and current < FIRST_PLAY_EARLIEST_MINUTES:
            current = FIRST_PLAY_EARLIEST_MINUTES
        if activity.get("type") == "eat" and not profile.get("prefer_eat_first") and current < DINNER_START_MINUTES:
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

        current += int(activity.get("duration_minutes", 0))
        prev_coords = coords or prev_coords

    candidate["total_travel_minutes"] = total_travel
    candidate["total_duration_minutes"] = current - _time_to_minutes(profile.get("start_time", "14:00"))


def _needs_light_extra(candidate: dict, activities: list[dict], profile: dict) -> bool:
    has_extra = any(activity.get("type") == "extra" for activity in activities)
    if has_extra:
        return False
    total = int(candidate.get("total_duration_minutes", 0))
    target_total = int(profile.get("target_total_minutes", TARGET_FAMILY_TOTAL_MINUTES))
    return total < target_total and any(activity.get("type") == "eat" for activity in activities)


def _build_light_extra_activity(candidate: dict, activities: list[dict]) -> dict:
    previous = activities[-1] if activities else {}
    coords = previous.get("venue_coords") or _home_coords_from_candidate(candidate) or []
    return {
        "order": len(activities) + 1,
        "type": "extra",
        "venue_name": "附近儿童书店轻松收尾",
        "venue_address": "餐厅附近商场/书店休息区",
        "venue_coords": coords,
        "start_time": "",
        "duration_minutes": 45,
        "travel_from_prev_minutes": 5,
        "action": "no_action",
        "action_details": {"skippable": True},
        "category": "儿童书店;亲子阅读;商场休息区",
        "poi_type": "fallback_generated",
        "typecode": "",
        "tags": ["轻量收尾", "可跳过"],
        "biz_type": [],
        "source": POI_SOURCE_FALLBACK,
        "trust_level": "generated_fallback",
        "rating": None,
        "distance_from_home": previous.get("distance_from_home", 0),
        "generated_light_extra": True,
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
        candidate["label"] = f"{play.get('venue_name', '亲子活动')} + {eat.get('venue_name', '家庭餐厅')}"


def _normalized_duration(activity: dict) -> int:
    duration = int(activity.get("duration_minutes", 0) or 0)
    if activity.get("type") == "play":
        return max(duration, 110 if _is_strong_child_activity(activity) else 90)
    if activity.get("type") == "eat":
        return max(duration, 70)
    if activity.get("type") == "extra":
        return max(duration, 35)
    return max(duration, 30)


def _infer_family_features(activity: dict, profile: dict, evidence: list[dict]) -> dict:
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
    strong_keyword = _contains_any(text, STRONG_CHILD_ACTIVITY_KEYWORDS)
    strong_child_activity_evidence = bool(
        activity_type == "play"
        and (
            poi_source == POI_SOURCE_SHOWCASE
            or (poi_source == POI_SOURCE_AMAP and strong_keyword and not company_or_office_poi)
        )
    )
    strong_child_activity = strong_child_activity_evidence
    weak_child_activity = (
        activity_type == "play"
        and not strong_child_activity
        and _contains_any(text, WEAK_CHILD_ACTIVITY_KEYWORDS)
        and not company_or_office_poi
    )
    child_friendly = activity_type != "play" or strong_child_activity or weak_child_activity
    indoor = _contains_any(text, INDOOR_KEYWORDS)
    rest_support = _contains_any(text, REST_SUPPORT_KEYWORDS)
    explicit_diet_fit = activity_type == "eat" and _contains_any(text, DIET_LOW_RISK_KEYWORDS)
    medium_diet_fit = activity_type == "eat" and _contains_any(text, DIET_MEDIUM_RISK_KEYWORDS)
    high_diet_risk = activity_type == "eat" and _contains_any(text, DIET_HIGH_RISK_KEYWORDS)
    diet_risk = "none"
    if activity_type == "eat":
        if explicit_diet_fit:
            diet_risk = "low"
        elif high_diet_risk:
            diet_risk = "high"
        else:
            diet_risk = "medium" if medium_diet_fit or activity_type == "eat" else "none"
    diet_friendly = explicit_diet_fit
    noisy = activity_type == "eat" and _contains_any(text, NOISY_FOOD_KEYWORDS)

    evidence_ids.append(
        _add_evidence(
            evidence,
            f"{name} POI来源为{poi_source}",
            _format_poi_metadata(activity),
            poi_source,
            trust_level,
            name,
        )
    )

    if strong_child_activity:
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}是强亲子主活动",
                (
                    "Showcase curated 家庭场馆"
                    if poi_source == POI_SOURCE_SHOWCASE
                    else f"AMap真实POI且命中强亲子关键词，{_format_poi_metadata(activity)}"
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
                f"{name}疑似工商主体或办公地址",
                f"POI type/typecode 不像可消费亲子场馆，{_format_poi_metadata(activity)}",
                poi_source,
                trust_level,
                name,
            )
        )
    elif weak_child_activity:
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}仅作为弱亲子备选",
                f"名称或品类命中公园/书店/商场等弱亲子关键词：{category or name}",
                "keyword_rule",
                "medium",
                name,
            )
        )
    if indoor:
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}天气风险较低",
                f"名称或品类显示为室内/场馆/商场类：{category or name}",
                "keyword_rule",
                "medium",
                name,
            )
        )
    if diet_friendly:
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}匹配减脂/轻食需求",
                f"名称或品类命中轻食/健康/低脂关键词：{category or name}",
                "keyword_rule",
                "medium",
                name,
            )
        )
    elif activity_type == "eat" and diet_risk == "medium":
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}可按清淡少油处理",
                f"未命中高糖高油风险关键词，可通过少油/清淡备注补偿：{category or name}",
                "keyword_rule",
                "medium",
                name,
            )
        )
    elif activity_type == "eat" and diet_risk == "high":
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}存在减脂饮食风险",
                f"名称或品类命中甜品/火锅/烧烤/高糖高油等谨慎推荐关键词：{category or name}",
                "keyword_rule",
                "medium",
                name,
            )
        )
    if activity.get("generated_light_extra"):
        evidence_ids.append(
            _add_evidence(
                evidence,
                f"{name}是可跳过轻量收尾",
                "为补足4-6小时家庭下午节奏生成，孩子累了可直接跳过。",
                "keyword_rule",
                "medium",
                name,
            )
        )

    return {
        "child_friendly": child_friendly,
        "source": poi_source,
        "trust_level": trust_level,
        "poi_type": poi_type,
        "typecode": typecode,
        "tags": tags,
        "company_or_office_poi": company_or_office_poi,
        "strong_child_activity": strong_child_activity,
        "strong_child_activity_evidence": strong_child_activity_evidence,
        "weak_child_activity": weak_child_activity,
        "age_range": [3, 8] if strong_child_activity else [4, 10] if weak_child_activity else [],
        "indoor": indoor,
        "rest_area": rest_support,
        "restroom": rest_support,
        "diet_friendly": diet_friendly,
        "diet_risk": diet_risk,
        "skippable": bool(activity.get("generated_light_extra") or activity.get("action_details", {}).get("skippable")),
        "family_friendly": child_friendly or rest_support or "家庭" in text or "亲子" in text,
        "noise_level": "high" if noisy else "medium",
        "activity_intensity": "medium" if activity_type == "play" else "low",
        "evidence_ids": evidence_ids,
    }


async def _get_family_availability(activity: dict, profile: dict, evidence: list[dict]) -> dict:
    result = await check_family_availability.ainvoke(
        {
            "venue_name": activity.get("venue_name", ""),
            "activity_type": activity.get("type", "play"),
            "party_size": profile.get("party_size", 3),
            "child_age": profile.get("child_age", 5),
            "diet_goal": profile.get("diet_goal", ""),
        }
    )
    if result.get("status") == "success":
        return result["data"]

    venue_name = activity.get("venue_name", "")
    _add_evidence(
        evidence,
        f"{venue_name}可用性未确认",
        result.get("message", "mock business API failed"),
        "mock_business_api",
        "simulated",
        venue_name,
    )
    return {
        "venue_name": venue_name,
        "available": True,
        "queue_minutes": 15,
        "source": "mock_business_api",
        "message": "可用性接口失败，按保守15分钟排队估算",
    }


def _features_from_availability(
    activity: dict,
    availability: dict,
    evidence: list[dict],
    base_features: dict,
) -> dict:
    venue_name = activity.get("venue_name", "")
    queue_minutes = availability.get("queue_minutes", 15)
    evidence_ids = []
    evidence_ids.append(
        _add_evidence(
            evidence,
            f"{venue_name}已完成可用性校验",
            availability.get("message", "mock business API returned availability"),
            "mock_business_api",
            "simulated",
            venue_name,
        )
    )
    evidence_ids.append(
        _add_evidence(
            evidence,
            f"{venue_name}预计排队{queue_minutes}分钟",
            f"Mock Availability API 返回 queue_minutes={queue_minutes}",
            "mock_business_api",
            "simulated",
            venue_name,
        )
    )
    updates = {
        "queue_minutes": queue_minutes,
        "available": availability.get("available", True),
        "reservation_required": availability.get("reservation_required", False),
        "evidence_ids": evidence_ids,
    }
    if activity.get("type") == "eat":
        high_risk = base_features.get("diet_risk") == "high"
        low_fat = bool(availability.get("low_fat_options", False)) and not high_risk
        child_seat = availability.get("child_seat_available", False)
        table_available = availability.get("table_available", True)
        if table_available:
            evidence_ids.append(
                _add_evidence(
                    evidence,
                    f"{venue_name}17:00有位",
                    "Mock Availability API 返回 table_available=true，time_slot=17:00",
                    "mock_business_api",
                    "simulated",
                    venue_name,
                )
            )
        if low_fat:
            evidence_ids.append(
                _add_evidence(
                    evidence,
                    f"{venue_name}支持低脂/轻食选项",
                    "Mock Availability API 返回 low_fat_options=true，且未命中高糖高油风险类别",
                    "mock_business_api",
                    "simulated",
                    venue_name,
                )
            )
        if child_seat:
            evidence_ids.append(
                _add_evidence(
                    evidence,
                    f"{venue_name}可备注儿童椅",
                    "Mock Availability API 返回 child_seat_available=true",
                    "mock_business_api",
                    "simulated",
                    venue_name,
                )
            )
        updates.update(
            {
                "table_available": table_available,
                "child_seat": child_seat,
                "diet_friendly": base_features.get("diet_friendly", False) or low_fat,
                "low_fat_options": low_fat,
                "can_note_less_oil": availability.get("can_note_less_oil", True),
            }
        )
    else:
        age_supported = availability.get("age_supported", True)
        tickets_available = availability.get("tickets_available", availability.get("available", True))
        if tickets_available:
            evidence_ids.append(
                _add_evidence(
                    evidence,
                    f"{venue_name}余票可用",
                    "Mock Availability API 返回 tickets_available=true",
                    "mock_business_api",
                    "simulated",
                    venue_name,
                )
            )
        if age_supported:
            evidence_ids.append(
                _add_evidence(
                    evidence,
                    f"{venue_name}支持当前孩子年龄",
                    f"Mock Availability API 返回 age_supported=true，孩子年龄={availability.get('child_age', '')}",
                    "mock_business_api",
                    "simulated",
                    venue_name,
                )
            )
        updates.update(
            {
                "tickets_available": tickets_available,
                "age_supported": age_supported,
            }
        )
    return updates


def _build_candidate_checks(
    candidate: dict,
    activities: list[dict],
    profile: dict,
    weather: dict | None,
) -> tuple[list[dict], list[str], list[str]]:
    blockers: list[str] = []
    degradations: list[str] = []
    min_total = int(profile.get("min_total_minutes", MIN_FAMILY_TOTAL_MINUTES))
    max_total = int(profile.get("max_total_minutes", 330))
    max_drive = int(profile.get("max_drive_minutes", 30))
    max_queue = int(profile.get("max_queue_minutes", 15))
    child_age = int(profile.get("child_age", 5))

    total_duration = int(candidate.get("total_duration_minutes", 0))
    max_travel = max((int(activity.get("travel_from_prev_minutes", 0)) for activity in activities), default=0)
    max_queue_seen = max(
        (int(activity.get("family_features", {}).get("queue_minutes", 0)) for activity in activities),
        default=0,
    )

    first_activity = activities[0] if activities else {}
    main_play = next((activity for activity in activities if activity.get("type") == "play"), {})
    main_play_features = main_play.get("family_features", {})
    eat_activity = next((activity for activity in activities if activity.get("type") == "eat"), {})
    eat_features = eat_activity.get("family_features", {})
    dinner_start = _time_to_minutes(eat_activity.get("start_time", "")) if eat_activity else None
    has_skippable_tail = bool(
        activities
        and activities[-1].get("type") == "extra"
        and activities[-1].get("family_features", {}).get("skippable", False)
    )
    strong_intent = bool(profile.get("strong_child_intent"))
    main_matches_intent = not strong_intent or _is_trusted_strong_child_main_activity(main_play_features)
    rhythm_ok = bool(first_activity) and (profile.get("prefer_eat_first") or first_activity.get("type") == "play")
    play_ok = all(
        activity.get("family_features", {}).get("child_friendly", True)
        and activity.get("family_features", {}).get("age_supported", True)
        for activity in activities
        if activity.get("type") == "play"
    )
    diet_risk = str(eat_features.get("diet_risk", "none"))
    diet_friendly = bool(eat_features.get("diet_friendly", False))
    is_weight_loss = "减" in str(profile.get("diet_goal", ""))
    if diet_friendly or diet_risk == "low":
        diet_status = "pass"
        diet_detail = "餐厅支持轻食/低脂/少油"
    elif diet_risk == "medium":
        diet_status = "warn" if is_weight_loss else "pass"
        diet_detail = "未命中低脂餐厅，但可用少油/清淡备注补偿"
    else:
        diet_status = "fail" if is_weight_loss else "warn"
        diet_detail = "餐饮类别与减脂需求冲突，不能作为优先餐厅"

    child_seat_ok = any(
        activity.get("family_features", {}).get("child_seat", False)
        for activity in activities
        if activity.get("type") == "eat"
    )
    indoor_count = sum(1 for activity in activities if activity.get("family_features", {}).get("indoor", False))
    weather_bad = _is_bad_weather(weather)
    queue_status = "pass" if max_queue_seen <= max_queue else "warn" if max_queue_seen <= 30 else "fail"
    route_status = "pass" if max_travel <= max_drive else "warn" if max_travel <= max_drive + 10 else "fail"
    time_status = "pass" if min_total <= total_duration <= max_total else "fail"
    dinner_status = (
        "pass"
        if profile.get("prefer_eat_first")
        or (dinner_start is not None and DINNER_START_MINUTES <= dinner_start <= DINNER_LATEST_START_MINUTES)
        else "fail"
    )
    weather_status = "pass" if not weather_bad or indoor_count >= 2 else "warn"

    checks = [
        _check_status(
            "main_intent",
            "主活动命中意图",
            "pass" if main_matches_intent else "fail",
            ("已优先选择强亲子主活动" if strong_intent else "用户未指定亲子乐园，按家庭低风险活动匹配")
            if main_matches_intent
            else "用户明确想去亲子乐园，但当前主活动缺少可信强亲子POI来源/证据",
        ),
        _check_status(
            "child_fit",
            "适合孩子",
            "pass" if play_ok else "fail",
            f"主活动适配{child_age}岁儿童" if play_ok else "主活动儿童适配证据不足",
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
            "rhythm",
            "家庭出游节奏",
            "pass" if rhythm_ok else "fail",
            "默认按主亲子活动 → 健康晚餐 → 轻量收尾安排" if rhythm_ok else "首站不是亲子活动，和家庭出游习惯不一致",
        ),
        _check_status(
            "dinner_time",
            "晚餐时间合理",
            dinner_status,
            "晚餐安排在17:00-18:30家庭用餐窗口" if dinner_status == "pass" else "晚餐未落在17:00-18:30的家庭用餐窗口",
        ),
        _check_status(
            "route_comfort",
            "路程不折腾",
            route_status,
            f"最长单段通勤{max_travel}分钟"
            if route_status == "pass"
            else f"最长单段通勤{max_travel}分钟，超过理想{max_drive}分钟",
        ),
        _check_status(
            "queue_control",
            "排队可控",
            queue_status,
            f"最长预计排队{max_queue_seen}分钟"
            if queue_status == "pass"
            else (
                f"排队预计{max_queue_seen}分钟，超过理想值{max_queue}分钟但低于高风险阈值30分钟"
                if queue_status == "warn"
                else f"排队预计{max_queue_seen}分钟，超过家庭高风险阈值30分钟"
            ),
        ),
        _check_status("diet_fit", "照顾减脂饮食", diet_status, diet_detail),
        _check_status(
            "child_seat",
            "家庭用餐备注",
            "pass" if child_seat_ok else "warn",
            "可备注儿童椅" if child_seat_ok else "儿童椅需到店确认，已备注靠边座位",
        ),
        _check_status(
            "weather_backup",
            "天气风险低",
            weather_status,
            "室内/场馆比例较高" if weather_status == "pass" else "天气不稳，已准备室内备选",
        ),
        _check_status(
            "skippable_tail",
            "孩子累了可调整",
            "pass" if has_skippable_tail else "warn",
            "最后一段为可跳过轻量收尾，孩子累了可直接回家"
            if has_skippable_tail
            else "未安排轻量收尾，保留直接回家的弹性",
        ),
    ]

    if strong_intent and not main_matches_intent:
        blockers.append("用户明确想去亲子乐园，但主活动不是可信强亲子消费场所")
    if not play_ok:
        blockers.append("主活动儿童适配不足")
    if total_duration < min_total:
        blockers.append("总时长不足4小时，下午规划不完整")
    if total_duration > max_total:
        blockers.append("总时长超出6小时家庭下午窗口")
    if dinner_status == "fail":
        blockers.append("晚餐时间不符合家庭用餐窗口")
    if route_status == "fail":
        blockers.append("单段通勤过长，路线折腾")
    if queue_status == "fail":
        blockers.append("排队时间过长")
    if diet_status == "fail":
        blockers.append("餐饮与减脂饮食目标冲突")

    if strong_intent and not main_matches_intent:
        degradations.append("附近真实POI缺少可信强亲子主活动证据，需切换为Showcase curated家庭场馆")
    if diet_status == "warn":
        degradations.append("未完全确认低脂餐厅，已使用少油/清淡备注补偿")
    if not child_seat_ok:
        degradations.append("儿童椅库存未完全确认，已备注靠边座位")
    if queue_status == "warn":
        degradations.append(f"排队预计{max_queue_seen}分钟，超过理想值{max_queue}分钟但仍可接受")
    if weather_bad and indoor_count < len(activities):
        degradations.append("天气不稳定，户外/半户外活动需要室内备选")
    if not has_skippable_tail:
        degradations.append("没有额外收尾站点，孩子累了可在晚餐后直接回家")

    return checks, blockers, degradations


def _calculate_fatigue_score(candidate: dict, activities: list[dict], weather: dict | None) -> int:
    total_travel = int(candidate.get("total_travel_minutes", 0))
    total_queue = sum(int(activity.get("family_features", {}).get("queue_minutes", 0)) for activity in activities)
    transfers = max(0, len(activities) - 1)
    high_intensity = sum(
        1 for activity in activities if activity.get("family_features", {}).get("activity_intensity") == "high"
    )
    outdoor_penalty = (
        10
        if _is_bad_weather(weather)
        and any(not activity.get("family_features", {}).get("indoor", False) for activity in activities)
        else 0
    )
    score = round(total_travel * 0.6 + total_queue * 0.7 + transfers * 8 + high_intensity * 10 + outdoor_penalty)
    return max(0, min(100, score))


def _calculate_family_score(checks: list[dict], fatigue_score: int, degradations: list[str]) -> int:
    check_score = sum(8 if check["status"] == "pass" else -6 if check["status"] == "fail" else 1 for check in checks)
    score = 100 - fatigue_score + check_score - len(degradations) * 3
    return max(0, min(100, round(score)))


def _build_alternatives(candidates: list[dict]) -> list[dict]:
    alternatives = []
    for candidate in candidates[1:3]:
        alternatives.append(
            {
                "id": candidate.get("id", ""),
                "title": candidate.get("label", "备选方案"),
                "fatigue_score": candidate.get("fatigue_score"),
                "reason": candidate.get("spatial_summary", ""),
                "checks": candidate.get("family_checks", [])[:4],
            }
        )
    if not alternatives and candidates:
        alternatives.append(
            {
                "id": "skip_tail",
                "title": "孩子累了备选",
                "fatigue_score": max(0, int(candidates[0].get("fatigue_score", 35)) - 8),
                "reason": "保留主活动和晚餐，跳过最后一段轻活动，直接回家。",
                "checks": [
                    check
                    for check in candidates[0].get("family_checks", [])
                    if check.get("id") in {"child_fit", "diet_fit"}
                ],
            }
        )
    return alternatives


def _build_family_summary(plan: dict) -> str:
    checks = plan.get("family_checks", [])
    passed = [check["label"] for check in checks if check.get("status") == "pass"]
    if not passed:
        return "已按家庭低风险策略生成方案。"
    return "已重点照顾：" + "、".join(passed[:4]) + "。"


def _build_pre_departure_tips(plan: dict) -> list[str]:
    profile = plan.get("family_profile") or {}
    tips = [
        "建议提前10分钟出发，给孩子留出换鞋、上厕所和缓冲时间。",
        f"餐厅备注：{_build_restaurant_request(plan)}",
        "如果孩子玩累了，可以跳过最后一段轻活动，直接回家。",
    ]
    if profile.get("prefer_indoor", True):
        tips.insert(1, "室内场地可能空调偏凉，建议给孩子带一件薄外套。")
    return tips


def _build_restaurant_request(plan: dict) -> str:
    profile = plan.get("family_profile") or {}
    return f"{profile.get('party_size', 3)}人桌，需要儿童椅，少油/轻食优先，孩子{profile.get('child_age', 5)}岁"


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


def _check(check_id: str, label: str, ok: bool, pass_detail: str, fail_detail: str) -> dict:
    return {
        "id": check_id,
        "label": label,
        "status": "pass" if ok else "warn",
        "detail": pass_detail if ok else fail_detail,
    }


def _check_status(check_id: str, label: str, status: str, detail: str) -> dict:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "detail": detail,
    }


def _fatigue_level(score: object) -> str:
    if not isinstance(score, int):
        return "unknown"
    if score <= 35:
        return "low"
    if score <= 65:
        return "medium"
    return "high"


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _is_strong_child_activity(activity: dict) -> bool:
    text = (
        f"{activity.get('venue_name', '')} {activity.get('category', '')} "
        f"{activity.get('poi_type', '')} {' '.join(str(tag) for tag in activity.get('tags', []) or [])}"
    ).lower()
    source = _poi_source(activity)
    return bool(
        activity.get("type") == "play"
        and (
            source == POI_SOURCE_SHOWCASE
            or (source == POI_SOURCE_AMAP and _contains_any(text, STRONG_CHILD_ACTIVITY_KEYWORDS))
        )
        and not _is_company_or_office_poi(activity)
    )


def _is_trusted_strong_child_main_activity(features: dict) -> bool:
    source = features.get("source", "")
    if source == POI_SOURCE_SHOWCASE:
        return True
    return bool(source == POI_SOURCE_AMAP and features.get("strong_child_activity_evidence", False))


def _poi_source(activity: dict) -> str:
    source = activity.get("source") or activity.get("poi_source") or ""
    if source in {POI_SOURCE_AMAP, POI_SOURCE_SHOWCASE, POI_SOURCE_FALLBACK}:
        return source
    if activity.get("generated_light_extra"):
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


def _is_bad_weather(weather: dict | None) -> bool:
    if not weather:
        return False
    summary = f"{weather.get('condition', '')} {weather.get('summary', '')}"
    return _contains_any(summary, BAD_WEATHER_KEYWORDS)


def _add_evidence(
    evidence: list[dict],
    claim: str,
    detail: str,
    source: EvidenceSource,
    confidence: Confidence,
    venue_name: str,
) -> str:
    evidence_id = f"ev_{len(evidence) + 1:03d}"
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
