"""Tests for the staged mock collaborative room contract."""

import asyncio

import pytest

from app.config import settings
from app.services.llm_room_agent import LLMRoomAgentError, generate_room_patch
from app.services.room import (
    add_reaction,
    add_room_message_stream,
    add_vote,
    advance_room,
    advance_room_agentic,
    execute_room,
    get_room,
    reset_room,
    set_room_scenario,
    simulate_room,
)
from app.services.room_agent_schemas import (
    ConsensusPatch,
    FinalCopyPatch,
    MemoryDelta,
    MessageDraft,
    PlanCopyUpdate,
    RoomPatch,
    VenueSignalDraft,
)

FORBIDDEN_USER_TOKENS = [
    "showcase_curated",
    "fallback_generated",
    "typecode",
    "source=",
    "raw_source",
    "debug",
]


def _visible_text(value: object) -> str:
    return str(value)


def _clear_llm_keys(monkeypatch) -> None:
    for attr in ("dashscope_api_key", "gemini_api_key", "deepseek_api_key", "openai_api_key"):
        monkeypatch.setattr(settings, attr, "")


def test_reset_room_starts_idle_without_preloaded_script() -> None:
    room = reset_room("test_room", active_user_id="red")

    assert room["room_id"] == "test_room"
    assert room["active_user_id"] == "red"
    assert room["stage"] == "idle"
    assert room["messages"] == []
    assert room["plan_options"] == []
    assert room["votes"] == []
    assert room["reactions"] == []
    assert len(room["participants"]) == 5


def test_advance_progresses_visible_events_before_options() -> None:
    reset_room("advance_room", active_user_id="red")

    first = advance_room("advance_room", active_user_id="red")
    assert first["stage"] == "host_prompted"
    assert len(first["messages"]) == 1
    assert first["plan_options"] == []

    second = advance_room("advance_room", active_user_id="red")
    assert second["stage"] == "agent_planning"
    assert any(message["actor_id"] == "agent" for message in second["messages"])

    third = advance_room("advance_room", active_user_id="red")
    assert third["stage"] == "members_invited"
    assert third["typing_participants"] == ["green"]


def test_simulate_applies_stable_group_script_without_raw_sources() -> None:
    room = simulate_room("simulate_room", active_user_id="pink")

    assert room["active_user_id"] == "pink"
    assert room["stage"] == "final_plan_ready"
    assert room["active_plan_id"] == "plan_b"
    assert room["group_memory"]["confirmed_constraints"]
    assert len(room["plan_options"]) == 3
    assert len(room["votes"]) == 4
    assert len(room["reactions"]) >= 3
    assert "投票信号" in _visible_text(room)

    visible = _visible_text(room)
    for token in FORBIDDEN_USER_TOKENS:
        assert token not in visible


def test_vote_updates_consensus_and_supporters_after_options_ready() -> None:
    reset_room("vote_room", active_user_id="blue")
    simulate_room("vote_room", active_user_id="blue")

    updated = add_vote("vote_room", participant_id="red", plan_id="plan_b", reason="照顾最多人")
    active = next(option for option in updated["plan_options"] if option["option_id"] == "plan_b")

    assert "red" in active["vote_summary"]["supporters"]
    assert updated["consensus"]["current_votes"] >= 3
    assert updated["consensus"]["status"] == "consensus_reached"


def test_reaction_updates_voting_signal_evidence() -> None:
    simulate_room("reaction_room", active_user_id="blue")

    updated = add_reaction(
        "reaction_room",
        participant_id="blue",
        venue_id="venue_hotpot",
        reaction_type="food_exclusion",
        reason="不要火锅",
    )
    active = next(option for option in updated["plan_options"] if option["option_id"] == updated["active_plan_id"])

    assert updated["active_plan_id"] == "plan_b"
    assert any(card["source_label"] == "投票信号" for card in active["plan_canvas"]["evidence_cards"])


def test_family_scenario_has_wife_child_constraints_and_options() -> None:
    room = set_room_scenario("family_room", scenario="family", active_user_id="red")

    assert room["stage"] == "idle"
    assert room["scenario"] == "family"
    assert any(participant["id"] == "wife" for participant in room["participants"])
    assert any(
        participant["id"] == "child" and participant["role"] == "profile" for participant in room["participants"]
    )

    ready = simulate_room("family_room", active_user_id="wife", scenario="family")
    assert ready["active_user_id"] == "wife"
    assert ready["stage"] == "final_plan_ready"
    assert ready["active_plan_id"] == "plan_b"
    assert ready["consensus"]["current_votes"] == 2
    assert "清淡少油" in _visible_text(ready["group_memory"])
    assert ready["plan_options"][1]["plan_canvas"]["scenario"] == "family"


def test_execute_room_host_only_and_updates_canvas_after_final_plan() -> None:
    simulate_room("execute_room", active_user_id="red")

    non_host = execute_room("execute_room", actor_id="blue")
    assert non_host["execution_state"]["host_can_execute"] is False
    assert non_host["execution_state"]["status"] == "ready"

    executed = execute_room("execute_room", actor_id="red")
    active = next(option for option in executed["plan_options"] if option["option_id"] == executed["active_plan_id"])

    assert executed["stage"] == "done"
    assert executed["execution_state"]["status"] == "completed"
    assert active["plan_canvas"]["status"] == "done"
    assert active["plan_canvas"]["execution_results"]
    assert any(action["confirmation"] for action in active["plan_canvas"]["execution_results"])


def test_get_room_normalizes_unknown_active_user() -> None:
    room = get_room("normalize_room", active_user_id="unknown")

    assert room["active_user_id"] == "red"


def test_room_patch_rejects_extra_fields() -> None:
    with pytest.raises(ValueError):
        RoomPatch.model_validate({"next_phase_hint": "continue_chat", "unexpected": "field"})


async def test_agentic_advance_without_llm_key_uses_scripted_fallback(monkeypatch) -> None:
    _clear_llm_keys(monkeypatch)
    reset_room("agentic_no_key_room", active_user_id="red")

    room = await advance_room_agentic("agentic_no_key_room", active_user_id="red", agent_mode="auto")

    assert room["stage"] == "host_prompted"
    assert room["agent_mode"] == "scripted"
    assert room["room_version"] == 1
    assert room["messages"][0]["actor_id"] == "red"


async def test_agentic_advance_applies_valid_room_patch(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    reset_room("agentic_valid_room", active_user_id="red")

    async def fake_generate_room_patch(room):
        return RoomPatch(
            messages=[
                MessageDraft(speaker_id="red", text="周末想轻松聚一下，别太远。"),
                MessageDraft(speaker_id="agent", text="好，我先按近一点、能聊天、预算适中来收偏好。"),
            ],
            memory_delta=MemoryDelta(
                constraints=["别太远"],
                preferences=["预算适中", "适合聊天"],
                decisions=["Agent 已开始动态收集群体偏好。"],
            ),
        )

    monkeypatch.setattr("app.services.room.generate_room_patch", fake_generate_room_patch)

    room = await advance_room_agentic("agentic_valid_room", active_user_id="red", agent_mode="llm")

    assert room["stage"] == "host_prompted"
    assert room["agent_mode"] == "llm"
    assert [message["actor_id"] for message in room["messages"]] == ["red", "agent"]
    assert "预算适中" in _visible_text(room["group_memory"])


async def test_agentic_advance_invalid_speaker_falls_back_to_scripted(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    reset_room("agentic_invalid_room", active_user_id="red")

    async def fake_generate_room_patch(room):
        return RoomPatch(messages=[MessageDraft(speaker_id="wife", text="我不在这个朋友房间里。")])

    monkeypatch.setattr("app.services.room.generate_room_patch", fake_generate_room_patch)

    room = await advance_room_agentic("agentic_invalid_room", active_user_id="red", agent_mode="llm")

    assert room["stage"] == "host_prompted"
    assert room["agent_mode"] == "fallback"
    assert room["messages"][0]["actor_id"] == "red"


async def test_agentic_advance_invalid_venue_falls_back_to_scripted(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    reset_room("agentic_invalid_venue_room", active_user_id="red")

    async def fake_generate_room_patch(room):
        return RoomPatch(
            venue_signals=[
                VenueSignalDraft(
                    participant_id="red",
                    venue_id="venue_not_in_catalog",
                    reaction_type="like",
                    reason="不存在的地点",
                )
            ]
        )

    monkeypatch.setattr("app.services.room.generate_room_patch", fake_generate_room_patch)

    room = await advance_room_agentic("agentic_invalid_venue_room", active_user_id="red", agent_mode="llm")

    assert room["stage"] == "host_prompted"
    assert room["agent_mode"] == "fallback"
    assert room["reactions"] == []


async def test_agentic_patch_updates_plan_copy_consensus_and_final_share(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    simulate_room("agentic_copy_room", active_user_id="red")

    async def fake_generate_room_patch(room):
        return RoomPatch(
            plan_copy_updates={
                "plan_b": PlanCopyUpdate(
                    title="折中稳妥",
                    positioning="路线集中，避开火锅，也保留拍照和咖啡。",
                    risks=["咖啡仍为可选"],
                    reason="最能照顾四个人的分歧。",
                )
            },
            consensus=ConsensusPatch(
                proposed_active_plan_id="plan_b",
                consensus_summary="3/4 支持 B：避开火锅、路线集中，拍照和咖啡也都保留。",
                minority_concerns=["小粉的拍照体验不是最强"],
            ),
            final_copy=FinalCopyPatch(
                final_summary="最终用 B：路线近、避开火锅，饭后咖啡可选。",
                share_text="朋友局安排好了：2点半先拍照互动，5点半吃轻聚餐，饭后咖啡可选。",
            ),
        )

    monkeypatch.setattr("app.services.room.generate_room_patch", fake_generate_room_patch)

    room = await advance_room_agentic("agentic_copy_room", active_user_id="red", agent_mode="llm")
    active = next(option for option in room["plan_options"] if option["option_id"] == "plan_b")

    assert room["agent_mode"] == "llm"
    assert active["label"] == "B 折中稳妥"
    assert active["positioning"] == "路线集中，避开火锅，也保留拍照和咖啡。"
    assert room["consensus"]["summary"] == "3/4 支持 B：避开火锅、路线集中，拍照和咖啡也都保留。"
    assert active["plan_canvas"]["summary"] == "最终用 B：路线近、避开火锅，饭后咖啡可选。"
    assert active["plan_canvas"]["share_text"] == "朋友局安排好了：2点半先拍照互动，5点半吃轻聚餐，饭后咖啡可选。"
    assert active["plan_canvas"]["map"]["markers"]


async def test_agentic_concurrent_advance_is_serialized(monkeypatch) -> None:
    _clear_llm_keys(monkeypatch)
    reset_room("agentic_lock_room", active_user_id="red")

    await asyncio.gather(
        advance_room_agentic("agentic_lock_room", active_user_id="red", agent_mode="auto"),
        advance_room_agentic("agentic_lock_room", active_user_id="red", agent_mode="auto"),
    )

    room = get_room("agentic_lock_room", active_user_id="red")
    assert room["demo_step_index"] == 2
    assert room["stage"] == "agent_planning"
    assert len(room["messages"]) == 2


async def _collect_message_stream(room_id: str, actor_id: str, content: str) -> tuple[str, dict | None]:
    reasoning = ""
    room: dict | None = None
    async for event in add_room_message_stream(room_id, actor_id=actor_id, content=content):
        if event["type"] == "reasoning":
            reasoning += event["delta"]
        elif event["type"] == "done":
            room = event["room"]
    return reasoning, room


async def test_message_stream_without_llm_key_uses_scripted_reply(monkeypatch) -> None:
    _clear_llm_keys(monkeypatch)
    reset_room("msg_stream_no_key", active_user_id="red")

    reasoning, room = await _collect_message_stream("msg_stream_no_key", "red", "周末想和朋友聚一聚，别太远。")

    assert reasoning == ""
    assert room is not None
    assert room["agent_mode"] == "scripted"
    assert room["stage"] == "agent_planning"
    assert [message["actor_id"] for message in room["messages"]] == ["red", "agent"]
    assert room["messages"][0]["content"] == "周末想和朋友聚一聚，别太远。"


async def test_message_stream_applies_patch_and_attaches_reasoning(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    reset_room("msg_stream_llm", active_user_id="red")

    async def fake_stream_room_patch(room):
        yield {"type": "reasoning", "delta": "先看大家的硬约束，"}
        yield {"type": "reasoning", "delta": "再决定取舍。"}
        yield {
            "type": "patch",
            "patch": RoomPatch(
                messages=[MessageDraft(speaker_id="agent", text="好，我按近一点、能聊天来收偏好。")],
                reasoning="先看硬约束，再取舍。",
            ),
        }

    monkeypatch.setattr("app.services.room.stream_room_patch", fake_stream_room_patch)

    reasoning, room = await _collect_message_stream("msg_stream_llm", "red", "周末想轻松点，别太远。")

    assert reasoning == "先看大家的硬约束，再决定取舍。"
    assert room is not None
    assert room["agent_mode"] == "llm"
    assert [message["actor_id"] for message in room["messages"]] == ["red", "agent"]
    assert room["messages"][1]["content"] == "好，我按近一点、能聊天来收偏好。"
    assert room["messages"][1]["reasoning"] == "先看硬约束，再取舍。"


async def test_message_stream_without_agent_reply_falls_back_to_scripted(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "g-key")
    reset_room("msg_stream_no_agent", active_user_id="red")

    async def fake_stream_room_patch(room):
        yield {"type": "reasoning", "delta": "想了想，"}
        yield {"type": "patch", "patch": RoomPatch(messages=[MessageDraft(speaker_id="red", text="我自己又补一句。")])}

    monkeypatch.setattr("app.services.room.stream_room_patch", fake_stream_room_patch)

    _, room = await _collect_message_stream("msg_stream_no_agent", "red", "周末想轻松点，别太远。")

    assert room is not None
    assert room["agent_mode"] == "fallback"
    assert [message["actor_id"] for message in room["messages"]] == ["red", "agent"]


async def test_generate_room_patch_invalid_json_raises(monkeypatch) -> None:
    class FakeResponse:
        content = "not-json"

    async def fake_invoke_with_fallback(messages, temperature=0.7, tools=None):
        return FakeResponse()

    monkeypatch.setattr("app.services.llm_room_agent.llm_factory.invoke_with_fallback", fake_invoke_with_fallback)

    with pytest.raises(LLMRoomAgentError):
        await generate_room_patch(reset_room("invalid_json_room", active_user_id="red"))
