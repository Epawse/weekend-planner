"""Tests for the Plan Canvas contract and feedback updates."""

from copy import deepcopy

from app.agents.orchestrator import _build_template_plan_from_top_candidate
from app.services.canvas import build_plan_canvas
from app.services.family import build_family_profile, enrich_and_score_family_candidates
from app.services.feedback import apply_feedback_to_state
from app.services.friends import build_friend_profile, enrich_and_score_friend_candidates
from app.services.spatial import build_curated_family_candidate, build_curated_friends_candidate

FORBIDDEN_USER_TOKENS = [
    "showcase_curated",
    "fallback_generated",
    "typecode",
    "source=",
    "raw_source",
    "POI来源为",
]


def _visible_text(value: object) -> str:
    return str(value)


async def _friends_state() -> dict:
    profile = build_friend_profile("今天下午4个朋友聚会，有吃有玩，别太远，适合聊天拍照，吃完还能续摊。", "friends", "")
    context = await enrich_and_score_friend_candidates(
        [build_curated_friends_candidate([116.481, 39.998])],
        profile,
        weather=None,
    )
    state = {
        "scenario": "friends",
        "home_location": [116.481, 39.998],
        "friend_profile": profile,
        "friend_strategy": context["friend_strategy"],
        "friend_checks": context["friend_checks"],
        "social_score": context["social_score"],
        "candidate_plans": context["candidate_plans"],
        "candidate_venues": [],
        "evidence": context["evidence"],
        "alternatives": context["alternatives"],
        "rejected_options": context["rejected_options"],
        "feedback_history": [],
        "execution_results": [],
    }
    plan = _build_template_plan_from_top_candidate(state, context["candidate_plans"])
    state["plan"] = plan
    return state


async def _family_state() -> dict:
    profile = build_family_profile(
        "今天下午想和老婆孩子去亲子乐园玩4到6个小时，孩子5岁，老婆最近减肥，别离家太远，少走路少排队。",
        "family",
        "",
    )
    context = await enrich_and_score_family_candidates(
        [build_curated_family_candidate([116.481, 39.998])],
        profile,
        weather=None,
    )
    state = {
        "scenario": "family",
        "home_location": [116.481, 39.998],
        "family_profile": profile,
        "family_strategy": context["family_strategy"],
        "family_checks": context["family_checks"],
        "fatigue_score": context["fatigue_score"],
        "candidate_plans": context["candidate_plans"],
        "candidate_venues": [],
        "evidence": context["evidence"],
        "alternatives": context["alternatives"],
        "rejected_options": context["rejected_options"],
        "feedback_history": [],
        "execution_results": [],
    }
    plan = _build_template_plan_from_top_candidate(state, context["candidate_plans"])
    state["plan"] = plan
    return state


async def test_plan_canvas_builds_friends_without_raw_sources() -> None:
    state = await _friends_state()

    canvas = build_plan_canvas(state, state["plan"], session_id="test")

    assert canvas["scenario"] == "friends"
    assert canvas["title"] == "朋友局安排好了"
    assert len(canvas["timeline"]) == 3
    assert canvas["map"]["markers"]
    assert canvas["evidence_cards"]
    assert canvas["pending_actions"]
    assert canvas["tool_tasks"]
    visible = _visible_text(canvas)
    for token in FORBIDDEN_USER_TOKENS:
        assert token not in visible
    assert "演示业务接口" in visible


async def test_plan_canvas_builds_family_with_execution_actions() -> None:
    state = await _family_state()

    canvas = build_plan_canvas(state, state["plan"], session_id="test")

    assert canvas["scenario"] == "family"
    assert canvas["title"] == "家庭安心下午"
    assert canvas["checks"]["passed"]
    assert any(action["label"] in {"预约活动", "预订家庭餐厅"} for action in canvas["pending_actions"])
    assert any(action["scheduled_time"] for action in canvas["pending_actions"])
    assert any(action["party_size"] == 3 for action in canvas["pending_actions"])
    visible = _visible_text(canvas)
    for token in FORBIDDEN_USER_TOKENS:
        assert token not in visible


async def test_feedback_closer_and_indoor_rebuild_canvas() -> None:
    state = await _friends_state()

    closer = apply_feedback_to_state(state, "太远了", session_id="test")
    indoor = apply_feedback_to_state({**state, **closer}, "换室内", session_id="test")

    assert closer["plan_canvas"]["status"] == "feedback_applied"
    assert closer["plan_canvas"]["feedback"]["change_summary"]
    assert closer["plan_canvas"]["feedback"]["change_summary"]["before"]
    assert closer["plan_canvas"]["feedback"]["change_summary"]["after"]
    assert indoor["plan_canvas"]["feedback"]["history"]
    assert indoor["plan_canvas"]["feedback"]["change_summary"]["changed"]


async def test_feedback_restaurant_exclusion_replaces_hotpot_slot() -> None:
    state = await _friends_state()
    hotpot_plan = deepcopy(state["plan"])
    dinner = next(activity for activity in hotpot_plan["activities"] if activity["type"] == "eat")
    dinner["venue_name"] = "排队网红火锅"
    dinner["display_name"] = "排队网红火锅"
    dinner["category"] = "火锅;网红餐厅"
    state["plan"] = hotpot_plan

    update = apply_feedback_to_state(state, "不要火锅", session_id="test")
    dinner_after = next(activity for activity in update["plan"]["activities"] if activity["type"] == "eat")

    assert "火锅" not in dinner_after["venue_name"]
    assert "已排除火锅" in update["feedback_message"]
    assert update["plan_canvas"]["feedback"]["history"]
    assert update["plan_canvas"]["feedback"]["change_summary"]["changed"]


async def test_feedback_earlier_home_removes_optional_tail() -> None:
    state = await _friends_state()

    update = apply_feedback_to_state(state, "早点回家", session_id="test")

    assert all(item["category_label"] != "收尾" for item in update["plan_canvas"]["timeline"])
    assert "提前结束" in update["feedback_message"]
    assert update["plan_canvas"]["feedback"]["change_summary"]["changed"]
