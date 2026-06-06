"""Tests for friends-gathering planning helpers."""

import pytest

from app.agents.orchestrator import _build_template_plan_from_top_candidate
from app.services.friends import (
    attach_friend_context_to_plan,
    build_friend_profile,
    enrich_and_score_friend_candidates,
)
from app.services.spatial import build_curated_friends_candidate
from app.tools.availability import check_friends_availability


def _time_to_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _sample_friend_candidate() -> dict:
    return {
        "id": "friend_plan_a",
        "label": "望京艺术互动展 + 四人桌氛围小馆",
        "total_duration_minutes": 285,
        "total_travel_minutes": 22,
        "walkability_score": 0.9,
        "spatial_summary": "活动集中在1公里范围内，步行为主",
        "route_geojson": {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[116.481, 39.998]]},
            "properties": {"total_travel_minutes": 22},
        },
        "activities": [
            {
                "order": 1,
                "type": "play",
                "venue_name": "望京艺术互动展",
                "venue_address": "望京商业中心L3",
                "venue_coords": [116.491, 40.002],
                "start_time": "14:20",
                "duration_minutes": 90,
                "travel_from_prev_minutes": 12,
                "action": "book",
                "action_details": {},
                "category": "展览;艺术空间;互动体验;拍照",
                "poi_type": "展览;艺术空间;互动体验;拍照",
                "typecode": "140100",
                "tags": ["展览", "拍照"],
                "source": "amap_real_poi",
                "trust_level": "real_api",
                "rating": 4.7,
                "distance_from_home": 900,
            },
            {
                "order": 2,
                "type": "eat",
                "venue_name": "四人桌氛围小馆",
                "venue_address": "望京SOHO商业街2层",
                "venue_coords": [116.494, 40.003],
                "start_time": "16:10",
                "duration_minutes": 80,
                "travel_from_prev_minutes": 5,
                "action": "reserve",
                "action_details": {},
                "category": "西餐;小馆;朋友聚餐;适合聊天",
                "poi_type": "西餐;小馆;朋友聚餐;适合聊天",
                "typecode": "050000",
                "tags": ["西餐", "聊天"],
                "source": "amap_real_poi",
                "trust_level": "real_api",
                "rating": 4.6,
                "distance_from_home": 1100,
            },
        ],
    }


async def _build_plan_for_friend_input(user_input: str, candidate: dict | None = None) -> dict:
    profile = build_friend_profile(user_input, "friends", "")
    context = await enrich_and_score_friend_candidates([candidate or _sample_friend_candidate()], profile, weather=None)
    candidate = context["candidate_plans"][0]
    plan = {
        "title": "轻松朋友局",
        "duration_hours": 4.8,
        "activities": [
            {
                "order": activity["order"],
                "type": activity["type"],
                "venue_name": activity["venue_name"],
                "venue_address": activity.get("venue_address", ""),
                "venue_coords": activity.get("venue_coords", []),
                "start_time": activity.get("start_time", ""),
                "duration_minutes": activity.get("duration_minutes", 0),
                "travel_to_next_minutes": None,
                "action": activity.get("action", "no_action"),
                "action_details": {},
                "reason": "",
                "evidence_ids": activity.get("friend_features", {}).get("evidence_ids", [])[:3],
            }
            for activity in candidate["activities"]
        ],
        "total_travel_minutes": candidate["total_travel_minutes"],
        "share_text": "",
    }
    state = {
        "friend_profile": profile,
        "friend_strategy": context["friend_strategy"],
        "friend_checks": context["friend_checks"],
        "social_score": context["social_score"],
        "evidence": context["evidence"],
        "alternatives": context["alternatives"],
        "rejected_options": context["rejected_options"],
    }
    return attach_friend_context_to_plan(plan, [candidate], state)


def test_build_friend_profile_extracts_group_and_preferences() -> None:
    profile = build_friend_profile("今天下午2男2女朋友聚会，想轻松有吃有玩，适合聊天拍照，别太远。", "friends", "")

    assert profile["party_size"] == 4
    assert profile["group_composition"] == "2男2女"
    assert profile["chat_preference"] is True
    assert profile["photo_preference"] is True
    assert "有吃有玩" in profile["preferences"]
    assert profile["dinner_window"] == "17:30-19:00"


async def test_check_friends_availability_returns_group_fields() -> None:
    result = await check_friends_availability.ainvoke(
        {
            "venue_name": "四人桌氛围小馆",
            "activity_type": "eat",
            "party_size": 4,
            "preferences": ["适合聊天"],
        }
    )

    assert result["status"] == "success"
    data = result["data"]
    assert data["source"] == "mock_business_api"
    assert "table_for_4" in data
    assert "chat_friendly" in data
    assert isinstance(data["queue_minutes"], int)


async def test_enrich_friend_candidate_adds_checks_evidence_and_optional_tail() -> None:
    profile = build_friend_profile("四个朋友有吃有玩，适合聊天拍照，别太远", "friends", "")
    context = await enrich_and_score_friend_candidates([_sample_friend_candidate()], profile, weather=None)

    assert len(context["candidate_plans"]) == 1
    top = context["candidate_plans"][0]
    assert top["friend_score"] > 0
    assert top["social_score"] is not None
    assert [activity["type"] for activity in top["activities"]] == ["play", "eat", "extra"]
    assert top["activities"][1]["start_time"] == "17:30"
    assert top["activities"][2]["action_details"]["optional_extension"] is True
    assert context["friend_checks"]
    assert context["evidence"]


async def test_unsuitable_play_activity_falls_back_to_curated_friends_plan() -> None:
    bad_candidate = _sample_friend_candidate()
    bad_candidate["label"] = "普通公园散步 + 四人桌氛围小馆"
    bad_candidate["activities"][0].update(
        {
            "venue_name": "普通公园散步",
            "category": "公园;户外散步",
            "poi_type": "公园;户外散步",
            "tags": ["公园"],
        }
    )
    profile = build_friend_profile("四个朋友聚会，有吃有玩，适合聊天拍照", "friends", "")

    context = await enrich_and_score_friend_candidates([bad_candidate], profile, weather=None)

    assert context["rejected_options"]
    assert context["candidate_plans"][0]["id"] == "showcase_curated_friends"
    checks = {check["id"]: check for check in context["candidate_plans"][0]["friend_checks"]}
    assert checks["social_activity"]["status"] == "pass"


async def test_attach_friend_context_filters_invalid_evidence_and_rewrites_reason() -> None:
    profile = build_friend_profile("四个朋友聚会，适合聊天拍照", "friends", "")
    context = await enrich_and_score_friend_candidates([_sample_friend_candidate()], profile, weather=None)
    candidate = context["candidate_plans"][0]
    plan = {
        "title": "轻松朋友局",
        "duration_hours": 4.5,
        "activities": [
            {
                "order": 1,
                "type": "play",
                "venue_name": "望京艺术互动展",
                "venue_address": "",
                "venue_coords": [],
                "start_time": "14:20",
                "duration_minutes": 90,
                "travel_to_next_minutes": 5,
                "action": "book",
                "action_details": {},
                "reason": "这里有4人桌、排队5分钟、特别适合聊天",
                "evidence_ids": ["not-real"],
            }
        ],
        "total_travel_minutes": 22,
        "share_text": "朋友局安排好了。",
    }
    state = {
        "friend_profile": profile,
        "friend_strategy": context["friend_strategy"],
        "friend_checks": context["friend_checks"],
        "social_score": context["social_score"],
        "evidence": context["evidence"],
        "alternatives": context["alternatives"],
        "rejected_options": context["rejected_options"],
    }

    enriched = attach_friend_context_to_plan(plan, [candidate], state)

    assert enriched["activities"][0]["evidence_ids"]
    assert "not-real" not in enriched["activities"][0]["evidence_ids"]
    assert enriched["activities"][0]["validated_evidence_claims"]
    assert "排队5分钟" not in enriched["activities"][0]["reason"]
    assert "微信群" not in enriched["share_text"]
    assert "friend_summary" in enriched


@pytest.mark.parametrize(
    "user_input",
    [
        "4个朋友聚会，有吃有玩",
        "2男2女，想拍照吃饭",
        "朋友局别太远，适合聊天",
        "想热闹一点",
        "预算别太高",
        "不想太吵",
        "吃完还能续摊",
        "先玩再吃",
    ],
)
async def test_real_friend_inputs_regression(user_input: str) -> None:
    plan = await _build_plan_for_friend_input(user_input)
    checks = {check["id"]: check for check in plan["friend_checks"]}
    activities = plan["activities"]
    family_terms = ["孩子", "老婆", "家庭", "亲子", "儿童椅", "减脂"]

    assert plan["friend_profile"]["party_size"] == 4
    assert any(activity["type"] == "play" for activity in activities)
    assert any(activity["type"] == "extra" for activity in activities)
    assert checks["social_activity"]["status"] == "pass"
    assert checks["table_for_4"]["status"] == "pass"
    assert checks["dinner_time"]["status"] == "pass"
    assert checks["optional_tail"]["status"] == "pass"
    assert checks["route_focus"]["status"] == "pass"

    dinner = next(activity for activity in activities if activity["type"] == "eat")
    play = next(activity for activity in activities if activity["type"] == "play")
    assert "17:30" <= dinner["start_time"] <= "19:00"
    assert (
        _time_to_minutes(play["start_time"])
        + int(play["duration_minutes"])
        + int(dinner.get("travel_from_prev_minutes", 0))
        == _time_to_minutes(dinner["start_time"])
    )
    extra = next(activity for activity in activities if activity["type"] == "extra")
    assert extra["action_details"]["optional_extension"] is True
    assert "朋友局安排好了" in plan["share_text"]
    assert "不用跑太远" in plan["share_text"]
    assert "family_profile" not in plan
    assert "family_checks" not in plan

    serialized = str(plan)
    for term in family_terms:
        assert term not in serialized


async def test_company_or_office_friend_play_poi_falls_back_to_curated_plan() -> None:
    company_candidate = _sample_friend_candidate()
    company_candidate["label"] = "展览文化传媒有限公司 + 四人桌氛围小馆"
    company_candidate["activities"][0].update(
        {
            "venue_name": "展览文化传媒有限公司",
            "venue_address": "望京写字楼A座12层",
            "category": "公司企业;文化传媒;展览策划",
            "poi_type": "公司企业;文化传媒",
            "typecode": "170200",
            "tags": ["公司企业", "文化传媒"],
            "source": "amap_real_poi",
            "trust_level": "real_api",
        }
    )
    profile = build_friend_profile("4个朋友聚会，有吃有玩，想拍照", "friends", "")

    context = await enrich_and_score_friend_candidates([company_candidate], profile, weather=None)

    assert context["rejected_options"]
    assert any("公司或办公地址" in reason for reason in context["rejected_options"][0]["reasons"])
    assert context["candidate_plans"][0]["id"] == "showcase_curated_friends"
    play = next(activity for activity in context["candidate_plans"][0]["activities"] if activity["type"] == "play")
    assert play["friend_features"]["social_activity_evidence"] is True
    assert play["friend_features"]["source"] == "showcase_curated"


def test_curated_friends_venue_covers_demo_categories() -> None:
    candidate = build_curated_friends_candidate([116.481, 39.998])
    categories = "；".join(activity["category"] for activity in candidate["activities"])
    names = [activity["venue_name"] for activity in candidate["activities"]]

    for keyword in ["展览", "手作", "桌游", "市集", "咖啡", "氛围餐厅"]:
        assert keyword in categories
    assert names == ["望京艺文互动展", "合生麒麟社聚餐厅", "麒麟新天地清吧"]


@pytest.mark.parametrize(
    "user_input",
    [
        "今天下午4个朋友聚会，有吃有玩，别太远，适合聊天拍照，吃完还能续摊。",
        "2男2女，想先玩再吃，拍照好看，预算别太高，不想太吵。",
        "周末想和朋友聚一聚，吃点好的再找个地方玩。",
    ],
)
async def test_friend_demo_acceptance_inputs_are_productized(user_input: str) -> None:
    curated = build_curated_friends_candidate([116.481, 39.998])
    plan = await _build_plan_for_friend_input(user_input, curated)
    visible_text = " ".join(
        [
            plan["title"],
            plan["friend_summary"],
            plan["share_text"],
            " ".join(activity["venue_name"] for activity in plan["activities"]),
            " ".join(activity["reason"] for activity in plan["activities"]),
            " ".join(item["claim"] for item in plan["evidence"]),
            " ".join(item["evidence"] for item in plan["evidence"]),
            " ".join(reason for item in plan["rejected_options"] for reason in item["reasons"]),
        ]
    )

    assert [activity["venue_name"] for activity in plan["activities"]] == [
        "望京艺文互动展",
        "合生麒麟社聚餐厅",
        "麒麟新天地清吧",
    ]
    assert [activity["user_description"] for activity in plan["activities"]] == [
        "展览 + 周边拍照轻逛，大家可以从第一站自然逛到晚餐前。",
        "适合4人聊天聚餐，已确认4人桌。",
        "饭后可选续摊，不想继续也可以直接散。",
    ]
    assert plan["friend_fit_level"] == "高"
    assert "朋友局安排好了" in plan["share_text"]
    assert "下午2点半先去" in plan["share_text"]
    assert "5点半去" in plan["share_text"]
    assert "4人桌已确认" in plan["share_text"]
    assert "不用跑太远" in plan["share_text"]
    assert plan["route_geojson"]["properties"]["source"] == "sequence_estimate"
    for banned in [
        "showcase_curated",
        "Mock",
        "mock",
        "fallback_generated",
        "typecode",
        "tags=无",
        "source=",
        "POI来源为",
        "四人桌氛围餐厅",
        "四人氛围餐厅",
        "附近清吧续摊",
        "朋友局主活动",
        "饭后续摊点",
        "质量门槛",
        "工具调用",
    ]:
        assert banned not in visible_text


async def test_llm_json_failure_template_still_returns_complete_friend_plan() -> None:
    profile = build_friend_profile("4个朋友聚会，有吃有玩", "friends", "")
    context = await enrich_and_score_friend_candidates([_sample_friend_candidate()], profile, weather=None)
    state = {
        "scenario": "friends",
        "friend_profile": profile,
        "friend_strategy": context["friend_strategy"],
        "friend_checks": context["friend_checks"],
        "social_score": context["social_score"],
        "evidence": context["evidence"],
        "alternatives": context["alternatives"],
        "rejected_options": context["rejected_options"],
    }

    plan = _build_template_plan_from_top_candidate(state, context["candidate_plans"])

    assert plan is not None
    assert len(plan["activities"]) == 3
    assert plan["share_text"].startswith("朋友局安排好了")
    assert plan["friend_checks"]
    assert all(activity["evidence_ids"] for activity in plan["activities"])
    assert "family_profile" not in plan
