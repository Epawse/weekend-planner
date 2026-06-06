"""Tests for the mock collaborative room contract."""

from app.services.room import add_reaction, add_vote, execute_room, get_room, reset_room, simulate_room

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


def test_demo_room_builds_three_plan_options_without_raw_sources() -> None:
    room = reset_room("test_room", active_user_id="red")

    assert room["room_id"] == "test_room"
    assert room["active_user_id"] == "red"
    assert len(room["participants"]) == 4
    assert len(room["plan_options"]) == 3
    assert room["active_plan_id"] == "plan_b"
    assert any(option["is_recommended"] for option in room["plan_options"])
    assert "投票信号" in _visible_text(room)

    visible = _visible_text(room)
    for token in FORBIDDEN_USER_TOKENS:
        assert token not in visible


def test_vote_updates_consensus_and_supporters() -> None:
    reset_room("vote_room", active_user_id="blue")

    updated = add_vote("vote_room", participant_id="red", plan_id="plan_b", reason="照顾最多人")
    active = next(option for option in updated["plan_options"] if option["option_id"] == "plan_b")

    assert "red" in active["vote_summary"]["supporters"]
    assert updated["consensus"]["current_votes"] >= 3
    assert updated["consensus"]["status"] == "consensus_reached"


def test_reaction_updates_voting_signal_evidence() -> None:
    reset_room("reaction_room", active_user_id="blue")

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


def test_simulate_applies_stable_group_script() -> None:
    room = simulate_room("simulate_room", active_user_id="pink")

    assert room["active_user_id"] == "pink"
    assert room["active_plan_id"] == "plan_b"
    assert room["group_memory"]["confirmed_constraints"]
    assert len(room["votes"]) == 4
    assert len(room["reactions"]) >= 3


def test_execute_room_host_only_and_updates_canvas() -> None:
    reset_room("execute_room", active_user_id="red")

    non_host = execute_room("execute_room", actor_id="blue")
    assert non_host["execution_state"]["host_can_execute"] is False
    assert non_host["execution_state"]["status"] == "ready"

    executed = execute_room("execute_room", actor_id="red")
    active = next(option for option in executed["plan_options"] if option["option_id"] == executed["active_plan_id"])

    assert executed["execution_state"]["status"] == "completed"
    assert active["plan_canvas"]["status"] == "done"
    assert active["plan_canvas"]["execution_results"]
    assert any(action["confirmation"] for action in active["plan_canvas"]["execution_results"])


def test_get_room_normalizes_unknown_active_user() -> None:
    room = get_room("normalize_room", active_user_id="unknown")

    assert room["active_user_id"] == "red"
