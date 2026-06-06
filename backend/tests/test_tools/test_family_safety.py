"""Tests for family-safety planning helpers."""

import pytest

from app.config import settings
from app.services.family import (
    attach_family_context_to_plan,
    build_family_profile,
    enrich_and_score_family_candidates,
)
from app.services.spatial import SpatialAnalysisEngine
from app.tools.availability import check_family_availability


def _sample_candidate() -> dict:
    return {
        "id": "plan_a",
        "label": "望京室内亲子科学馆 + 轻氧低脂家庭餐厅",
        "total_duration_minutes": 285,
        "total_travel_minutes": 24,
        "walkability_score": 0.9,
        "spatial_summary": "活动集中在1公里范围内，步行为主",
        "activities": [
            {
                "order": 1,
                "type": "play",
                "venue_name": "望京室内亲子科学馆",
                "venue_address": "望京SOHO附近亲子中心3层",
                "venue_coords": [116.491, 40.002],
                "start_time": "14:20",
                "duration_minutes": 90,
                "travel_from_prev_minutes": 12,
                "action": "book",
                "action_details": {},
                "category": "亲子科学馆;室内活动;儿童乐园",
                "poi_type": "亲子科学馆;室内活动;儿童乐园",
                "typecode": "080501",
                "tags": ["亲子", "儿童乐园"],
                "source": "amap_real_poi",
                "trust_level": "real_api",
                "rating": 4.8,
                "distance_from_home": 900,
            },
            {
                "order": 2,
                "type": "eat",
                "venue_name": "轻氧低脂家庭餐厅",
                "venue_address": "望京SOHO商业街B1",
                "venue_coords": [116.494, 40.003],
                "start_time": "16:05",
                "duration_minutes": 75,
                "travel_from_prev_minutes": 5,
                "action": "reserve",
                "action_details": {},
                "category": "轻食;沙拉;健康餐;家庭餐厅",
                "poi_type": "轻食;沙拉;健康餐;家庭餐厅",
                "typecode": "050000",
                "tags": ["轻食"],
                "source": "amap_real_poi",
                "trust_level": "real_api",
                "rating": 4.6,
                "distance_from_home": 1100,
            },
        ],
    }


def test_build_family_profile_extracts_constraints() -> None:
    profile = build_family_profile(
        "今天下午想和老婆孩子去亲子乐园玩几个小时，孩子 5 岁，老婆最近减肥，别离家太远。",
        "family",
        "",
    )

    assert profile["party_size"] == 3
    assert profile["child_age"] == 5
    assert profile["diet_goal"] == "减脂/轻食"
    assert profile["nearby_preference"] is True
    assert profile["max_queue_minutes"] == 15
    assert profile["strong_child_intent"] is True
    assert profile["min_total_minutes"] == 240
    assert profile["max_total_minutes"] == 360


async def test_check_family_availability_returns_family_fields() -> None:
    result = await check_family_availability.ainvoke(
        {
            "venue_name": "轻氧低脂家庭餐厅",
            "activity_type": "eat",
            "party_size": 3,
            "child_age": 5,
            "diet_goal": "减脂/轻食",
        }
    )

    assert result["status"] == "success"
    data = result["data"]
    assert data["source"] == "mock_business_api"
    assert isinstance(data["queue_minutes"], int)
    assert data["low_fat_options"] is True
    assert "child_seat_available" in data


async def test_enrich_and_score_family_candidates_adds_evidence_and_checks() -> None:
    profile = build_family_profile("孩子5岁，老婆减肥，别太远", "family", "")
    context = await enrich_and_score_family_candidates([_sample_candidate()], profile, weather=None)

    assert len(context["candidate_plans"]) == 1
    top = context["candidate_plans"][0]
    assert top["family_score"] > 0
    assert top["fatigue_score"] is not None
    assert top["family_checks"]
    assert context["evidence"]
    assert top["total_duration_minutes"] >= 240
    assert [activity["type"] for activity in top["activities"]] == ["play", "eat", "extra"]
    assert top["activities"][1]["start_time"] == "17:00"

    sources = {item["source"] for item in context["evidence"]}
    assert "keyword_rule" in sources
    assert "mock_business_api" in sources


async def test_strong_child_intent_blocks_weak_main_activity_without_silent_swap() -> None:
    weak_candidate = _sample_candidate()
    weak_candidate["label"] = "公园亲子备选 + 轻氧低脂家庭餐厅"
    weak_candidate["activities"][0].update(
        {
            "venue_name": "望京公园",
            "category": "公园;广场;户外活动",
            "poi_type": "公园;广场;户外活动",
            "typecode": "110101",
            "tags": ["公园"],
        }
    )
    profile = build_family_profile("今天下午想带孩子去亲子乐园，老婆减肥，别太远", "family", "")

    context = await enrich_and_score_family_candidates([weak_candidate], profile, weather=None)

    assert context["rejected_options"]
    assert any("可信强亲子" in reason for reason in context["rejected_options"][0]["reasons"])
    assert context["candidate_plans"][0]["id"] == "showcase_curated_family"
    top_checks = {check["id"]: check for check in context["candidate_plans"][0]["family_checks"]}
    assert top_checks["main_intent"]["status"] == "pass"


async def test_amap_company_poi_is_rejected_and_curated_family_venue_is_used() -> None:
    company_candidate = _sample_candidate()
    company_candidate["id"] = "plan_company"
    company_candidate["label"] = "游美营地（北京）教育科技有限公司 + 轻氧低脂家庭餐厅"
    company_candidate["activities"][0].update(
        {
            "venue_name": "游美营地(北京)教育科技有限公司",
            "venue_address": "阜通东大街1号院6号楼18层3单元",
            "category": "公司企业;公司;广告装饰",
            "poi_type": "公司企业;公司;广告装饰",
            "typecode": "170201",
            "tags": [],
            "source": "amap_real_poi",
            "trust_level": "real_api",
        }
    )
    profile = build_family_profile("今天下午想带孩子去亲子乐园，老婆减肥，别太远", "family", "")

    context = await enrich_and_score_family_candidates([company_candidate], profile, weather=None)
    top = context["candidate_plans"][0]

    assert top["id"] == "showcase_curated_family"
    assert top["activities"][0]["source"] == "showcase_curated"
    assert top["activities"][0]["family_features"]["strong_child_activity_evidence"] is True
    assert any("可信强亲子消费场所" in "；".join(item["reasons"]) for item in context["rejected_options"])
    assert any("疑似工商主体" in item["claim"] for item in context["evidence"])


async def test_weight_loss_context_rejects_high_risk_restaurant_when_alternative_exists() -> None:
    good_candidate = _sample_candidate()
    risky_candidate = _sample_candidate()
    risky_candidate["id"] = "plan_hotpot"
    risky_candidate["label"] = "望京室内亲子科学馆 + 网红火锅"
    risky_candidate["activities"][1].update(
        {
            "venue_name": "排队网红火锅",
            "category": "火锅;重辣川菜;网红餐厅",
            "poi_type": "火锅;重辣川菜;网红餐厅",
            "typecode": "050117",
            "tags": ["火锅", "网红"],
        }
    )
    profile = build_family_profile("孩子5岁，老婆最近减肥，想去亲子乐园", "family", "")

    context = await enrich_and_score_family_candidates([risky_candidate, good_candidate], profile, weather=None)

    assert context["candidate_plans"][0]["label"].endswith("轻氧低脂家庭餐厅")
    assert any("减脂" in "；".join(item["reasons"]) for item in context["rejected_options"])


async def test_attach_family_context_filters_invalid_llm_evidence_ids() -> None:
    profile = build_family_profile("孩子5岁，老婆减肥，别太远", "family", "")
    context = await enrich_and_score_family_candidates([_sample_candidate()], profile, weather=None)
    candidate = context["candidate_plans"][0]
    plan = {
        "title": "轻松亲子下午",
        "duration_hours": 4.5,
        "activities": [
            {
                "order": 1,
                "type": "play",
                "venue_name": "望京室内亲子科学馆",
                "venue_address": "",
                "venue_coords": [],
                "start_time": "14:20",
                "duration_minutes": 90,
                "travel_to_next_minutes": 5,
                "action": "book",
                "action_details": {},
                "reason": "这里有儿童椅、排队8分钟、低脂餐都确认了",
                "evidence_ids": ["not-real"],
            }
        ],
        "total_travel_minutes": 24,
        "share_text": "下午轻松安排好了。",
    }
    state = {
        "family_profile": profile,
        "family_strategy": context["family_strategy"],
        "family_checks": context["family_checks"],
        "fatigue_score": context["fatigue_score"],
        "evidence": context["evidence"],
        "alternatives": context["alternatives"],
        "rejected_options": context["rejected_options"],
    }

    enriched = attach_family_context_to_plan(plan, [candidate], state)

    assert enriched["activities"][0]["evidence_ids"]
    assert "not-real" not in enriched["activities"][0]["evidence_ids"]
    assert enriched["activities"][0]["validated_evidence_claims"]
    assert "排队8分钟" not in enriched["activities"][0]["reason"]
    assert enriched["pre_departure_tips"]
    assert "family_summary" in enriched


async def test_spatial_showcase_mode_returns_stable_family_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "showcase_mode", True)

    result = await SpatialAnalysisEngine().analyze([116.481, 39.998], "family")

    assert result["stats"]["showcase_mode"] is True
    assert result["candidates"]
    assert result["all_venues"]
