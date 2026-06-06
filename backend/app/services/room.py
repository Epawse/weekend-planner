"""Deterministic mock collaborative room service."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from app.services.canvas import build_plan_canvas

DEFAULT_ROOM_ID = "demo_friends_room"
HOME_LOCATION = [116.481, 39.998]

_ROOMS: dict[str, dict] = {}


def get_room(room_id: str = DEFAULT_ROOM_ID, active_user_id: str = "red") -> dict:
    """Return a collaborative room, creating the deterministic demo room if needed."""
    room = _ROOMS.setdefault(room_id, _build_demo_room(room_id))
    return _serialize_room(room, active_user_id)


def reset_room(room_id: str = DEFAULT_ROOM_ID, active_user_id: str = "red") -> dict:
    """Reset a room to its deterministic demo baseline."""
    _ROOMS[room_id] = _build_demo_room(room_id)
    return _serialize_room(_ROOMS[room_id], active_user_id)


def add_room_message(room_id: str, actor_id: str, content: str) -> dict:
    """Add a participant message and a deterministic Agent summary."""
    room = _ROOMS.setdefault(room_id, _build_demo_room(room_id))
    actor = _participant(room, actor_id)
    room["messages"].append(_message(actor, "user_message", content))
    _apply_text_preference(room, actor_id, content)
    room["messages"].append(
        _agent_message(
            room,
            "我已更新群体偏好，会把大家的反馈转成约束：排除不想吃的餐饮，优先保留室内、拍照和路线集中。",
        )
    )
    _refresh_room(room)
    return _serialize_room(room, actor_id)


def add_vote(room_id: str, participant_id: str, plan_id: str, reason: str = "") -> dict:
    """Add or replace a participant plan vote."""
    room = _ROOMS.setdefault(room_id, _build_demo_room(room_id))
    room["votes"] = [
        vote
        for vote in room["votes"]
        if not (vote["participant_id"] == participant_id and vote["target_type"] == "plan")
    ]
    room["votes"].append(
        {
            "participant_id": participant_id,
            "target_type": "plan",
            "target_id": plan_id,
            "vote_type": "support",
            "reason": reason or _vote_reason(participant_id, plan_id),
        }
    )
    _refresh_room(room)
    return _serialize_room(room, participant_id)


def add_reaction(
    room_id: str,
    participant_id: str,
    venue_id: str,
    reaction_type: str,
    reason: str = "",
) -> dict:
    """Add or replace a participant venue reaction."""
    room = _ROOMS.setdefault(room_id, _build_demo_room(room_id))
    room["reactions"] = [
        reaction
        for reaction in room["reactions"]
        if not (
            reaction["participant_id"] == participant_id
            and reaction["target_type"] == "venue"
            and reaction["target_id"] == venue_id
        )
    ]
    label = _reaction_label(reaction_type)
    room["reactions"].append(
        {
            "participant_id": participant_id,
            "target_type": "venue",
            "target_id": venue_id,
            "reaction_type": reaction_type,
            "label": label,
            "reason": reason or _reaction_reason(participant_id, reaction_type),
        }
    )
    _apply_reaction_preference(room, participant_id, venue_id, reaction_type)
    _refresh_room(room)
    return _serialize_room(room, participant_id)


def simulate_room(room_id: str = DEFAULT_ROOM_ID, active_user_id: str = "red") -> dict:
    """Apply the stable friends collaboration demo script."""
    room = _build_demo_room(room_id)
    for actor_id, content in [
        ("green", "最好室内，最近有点热，也希望安静一点。"),
        ("blue", "不要火锅，预算别太高，饭后我可能想早点回。"),
        ("pink", "我想去拍照好看的地方，饭后可以喝咖啡。"),
    ]:
        actor = _participant(room, actor_id)
        room["messages"].append(_message(actor, "user_message", content))
    room["votes"] = [
        _vote("red", "plan_a", "体验最好"),
        _vote("green", "plan_b", "室内和路线更稳"),
        _vote("blue", "plan_b", "避开火锅且预算适中"),
        _vote("pink", "plan_b", "保留拍照和咖啡"),
    ]
    room["reactions"] = [
        {
            "participant_id": "pink",
            "target_type": "venue",
            "target_id": "venue_art",
            "reaction_type": "like",
            "label": "想去",
            "reason": "拍照好看",
        },
        {
            "participant_id": "blue",
            "target_type": "venue",
            "target_id": "venue_hotpot",
            "reaction_type": "food_exclusion",
            "label": "不吃这个",
            "reason": "不要火锅",
        },
        {
            "participant_id": "green",
            "target_type": "venue",
            "target_id": "venue_handcraft",
            "reaction_type": "like",
            "label": "想去",
            "reason": "室内不晒",
        },
    ]
    room["messages"].append(
        _agent_message(
            room,
            "我理解大家的偏好：小红希望别太远，小绿希望室内安静，"
            "小蓝排除火锅且预算适中，小粉想拍照和饭后咖啡。我建议采用折中方案 B。",
        )
    )
    room["active_plan_id"] = "plan_b"
    _refresh_room(room)
    _ROOMS[room_id] = room
    return _serialize_room(room, active_user_id)


def execute_room(room_id: str, actor_id: str) -> dict:
    """Execute the active room plan if the host confirms."""
    room = _ROOMS.setdefault(room_id, _build_demo_room(room_id))
    if actor_id != room["host_user_id"]:
        room["execution_state"] = {
            "status": "ready",
            "host_can_execute": False,
            "summary": "只有发起人小红可以确认执行，其他成员可以继续投票和反馈。",
        }
        return _serialize_room(room, actor_id)

    option = _active_option(room)
    canvas = deepcopy(option["plan_canvas"])
    canvas["status"] = "done"
    canvas["execution_results"] = _execution_results(canvas)
    canvas["pending_actions"] = []
    option["plan_canvas"] = canvas
    room["execution_state"] = {
        "status": "completed",
        "host_can_execute": True,
        "summary": "3/4 已达成共识，小红已确认执行，预约、订座、备注和群聊文案已准备好。",
    }
    room["messages"].append(
        _agent_message(
            room,
            "已按折中方案执行：活动预约、4人桌订座、靠安静区域备注和群聊文案都已完成。",
        )
    )
    _refresh_room(room)
    return _serialize_room(room, actor_id)


def _build_demo_room(room_id: str) -> dict:
    participants = _participants()
    votes = [
        _vote("red", "plan_a", "体验最好"),
        _vote("green", "plan_b", "室内和路线更稳"),
        _vote("blue", "plan_b", "预算适中，不吃火锅"),
        _vote("pink", "plan_b", "拍照和咖啡都保留"),
    ]
    reactions = [
        {
            "participant_id": "pink",
            "target_type": "venue",
            "target_id": "venue_art",
            "reaction_type": "like",
            "label": "想去",
            "reason": "拍照好看",
        },
        {
            "participant_id": "blue",
            "target_type": "venue",
            "target_id": "venue_hotpot",
            "reaction_type": "food_exclusion",
            "label": "不吃这个",
            "reason": "不要火锅",
        },
        {
            "participant_id": "green",
            "target_type": "venue",
            "target_id": "venue_handcraft",
            "reaction_type": "like",
            "label": "想去",
            "reason": "室内不晒",
        },
    ]
    room = {
        "room_id": room_id,
        "scenario": "friends",
        "host_user_id": "red",
        "active_user_id": "red",
        "participants": participants,
        "messages": _initial_messages(participants),
        "group_memory": {},
        "plan_options": [],
        "active_plan_id": "plan_b",
        "votes": votes,
        "reactions": reactions,
        "consensus": {},
        "execution_state": {
            "status": "ready",
            "host_can_execute": True,
            "summary": "3/4 已支持折中方案，小红可以确认执行。",
        },
    }
    room["plan_options"] = _build_plan_options(room)
    _refresh_room(room)
    return room


def _participants() -> list[dict]:
    return [
        {
            "id": "red",
            "name": "小红",
            "color": "red",
            "avatar": "红",
            "role": "host",
            "status": "online",
            "preference_profile": {
                "distance": "near",
                "budget": "normal",
                "vibe": "efficient",
                "food_exclusions": [],
                "likes": ["别太远", "效率"],
            },
        },
        {
            "id": "green",
            "name": "小绿",
            "color": "green",
            "avatar": "绿",
            "role": "member",
            "status": "online",
            "preference_profile": {
                "distance": "near",
                "budget": "normal",
                "vibe": "quiet",
                "food_exclusions": [],
                "likes": ["室内", "安静"],
            },
        },
        {
            "id": "blue",
            "name": "小蓝",
            "color": "blue",
            "avatar": "蓝",
            "role": "member",
            "status": "online",
            "preference_profile": {
                "distance": "medium",
                "budget": "moderate",
                "vibe": "balanced",
                "food_exclusions": ["火锅"],
                "likes": ["预算适中", "早点回"],
            },
        },
        {
            "id": "pink",
            "name": "小粉",
            "color": "pink",
            "avatar": "粉",
            "role": "member",
            "status": "online",
            "preference_profile": {
                "distance": "medium",
                "budget": "normal",
                "vibe": "photo",
                "food_exclusions": [],
                "likes": ["拍照", "饭后咖啡"],
            },
        },
    ]


def _vote(participant_id: str, target_id: str, reason: str) -> dict:
    return {
        "participant_id": participant_id,
        "target_type": "plan",
        "target_id": target_id,
        "vote_type": "support",
        "reason": reason,
    }


def _initial_messages(participants: list[dict]) -> list[dict]:
    red = next(item for item in participants if item["id"] == "red")
    messages = [
        _message(red, "user_message", "周末想和朋友聚一聚，吃点好的再找个地方玩，别太远。"),
        {
            "id": "msg_agent_1",
            "actor_id": "agent",
            "actor_name": "Agent",
            "actor_avatar": "AI",
            "type": "agent_message",
            "content": "我先生成 3 个可选方案，大家可以投票，也可以直接说不喜欢哪里。",
            "created_at": _now(),
            "related_plan_id": None,
        },
    ]
    for actor_id, content in [
        ("green", "最好室内，最近有点热。"),
        ("blue", "不要火锅，预算别太高。"),
        ("pink", "想去拍照好看的地方，饭后可以喝咖啡。"),
    ]:
        actor = next(item for item in participants if item["id"] == actor_id)
        messages.append(_message(actor, "user_message", content))
    messages.append(
        {
            "id": "msg_agent_2",
            "actor_id": "agent",
            "actor_name": "Agent",
            "actor_avatar": "AI",
            "type": "agent_message",
            "content": (
                "我理解大家的偏好：小红希望别太远，小绿希望室内，"
                "小蓝排除火锅且预算适中，小粉想拍照和饭后咖啡。我会推荐折中方案。"
            ),
            "created_at": _now(),
            "related_plan_id": "plan_b",
        }
    )
    return messages


def _build_plan_options(room: dict) -> list[dict]:
    definitions = [
        {
            "option_id": "plan_a",
            "label": "A 最优方案",
            "positioning": "拍照体验最好，活动最丰富，但晚餐风险更高。",
            "score": {"distance": 78, "budget": 70, "photo": 96, "indoor": 72, "consensus": 74},
            "is_recommended": False,
            "plan": _plan_a(),
        },
        {
            "option_id": "plan_b",
            "label": "B 折中方案",
            "positioning": "路线最近，避开火锅，照顾最多成员偏好。",
            "score": {"distance": 92, "budget": 86, "photo": 84, "indoor": 90, "consensus": 91},
            "is_recommended": True,
            "plan": _plan_b(),
        },
        {
            "option_id": "plan_c",
            "label": "C 备选方案",
            "positioning": "全室内、低排队、可直接散，天气不好也稳。",
            "score": {"distance": 88, "budget": 82, "photo": 62, "indoor": 98, "consensus": 80},
            "is_recommended": False,
            "plan": _plan_c(),
        },
    ]
    options = []
    for definition in definitions:
        plan = definition["plan"]
        state = {
            "scenario": "friends",
            "home_location": HOME_LOCATION,
            "candidate_plans": [],
            "candidate_venues": [],
            "feedback_history": [],
            "feedback_change_summary": None,
            "execution_results": [],
        }
        canvas = build_plan_canvas(state, plan, session_id=f"{room['room_id']}_{definition['option_id']}")
        options.append(
            {
                "option_id": definition["option_id"],
                "label": definition["label"],
                "positioning": definition["positioning"],
                "plan_canvas": canvas,
                "vote_summary": {"supporters": [], "opponents": [], "concerns": []},
                "score": definition["score"],
                "is_recommended": definition["is_recommended"],
            }
        )
    return options


def _plan_a() -> dict:
    return _plan(
        title="最优方案",
        summary=(
            "体验优先：先去望京艺文互动展拍照，再去氛围火锅，"
            "饭后清吧续摊；适合想玩得更丰富的一组。"
        ),
        travel=12,
        activities=[
            _activity(
                1,
                "play",
                "望京艺文互动展",
                "花家地艺术街区 9 号",
                [116.4822, 39.9978],
                "14:30",
                110,
                "适合拍照和轻互动，是小粉最想保留的亮点。",
                "book",
                "venue_art",
            ),
            _activity(
                2,
                "eat",
                "排队网红火锅",
                "麒麟社 2 层",
                [116.486, 39.999],
                "17:30",
                80,
                "氛围热闹，但小蓝反对火锅，排队也偏长。",
                "reserve",
                "venue_hotpot",
                queue=35,
            ),
            _activity(
                3,
                "extra",
                "麒麟新天地清吧",
                "麒麟新天地北区",
                [116.489, 40.0005],
                "19:05",
                60,
                "饭后可以续摊聊天，不想继续也可直接散。",
                "no_action",
                "venue_bar",
            ),
        ],
        warning="火锅被小蓝反对，排队预计35分钟。",
    )


def _plan_b() -> dict:
    return _plan(
        title="折中方案",
        summary=(
            "折中方案：保留拍照友好的艺文互动展，晚餐换成轻聚餐厅，"
            "饭后咖啡设为可选；路线集中，避开火锅。"
        ),
        travel=7,
        activities=[
            _activity(
                1,
                "play",
                "望京艺文互动展",
                "花家地艺术街区 9 号",
                [116.4822, 39.9978],
                "14:30",
                105,
                "保留小粉喜欢的拍照点，同时满足小红别太远的要求。",
                "book",
                "venue_art",
            ),
            _activity(
                2,
                "eat",
                "合生麒麟社轻聚餐厅",
                "合生麒麟社 1 层",
                [116.4852, 39.9991],
                "17:30",
                78,
                "已避开火锅，4人桌可订，预算适中，适合聊天。",
                "reserve",
                "venue_light_dinner",
                queue=18,
            ),
            _activity(
                3,
                "extra",
                "方恒书店咖啡",
                "方恒购物中心 3 层",
                [116.4871, 39.9988],
                "18:55",
                50,
                "咖啡作为可选收尾，照顾小粉续摊和小蓝早点回的分歧。",
                "no_action",
                "venue_coffee",
            ),
        ],
        warning="饭后咖啡为可选，不强制所有人参加。",
    )


def _plan_c() -> dict:
    return _plan(
        title="备选方案",
        summary="稳妥备选：桌游馆加商场餐厅，全室内、低排队、晚餐后可直接散，天气不好也稳。",
        travel=5,
        activities=[
            _activity(
                1,
                "play",
                "望京桌游馆",
                "望京 SOHO T2",
                [116.4806, 39.9968],
                "14:30",
                120,
                "全室内、互动强，适合天气不好时直接切换。",
                "book",
                "venue_boardgame",
            ),
            _activity(
                2,
                "eat",
                "商场轻聚餐厅",
                "望京 SOHO B1",
                [116.4816, 39.9972],
                "17:20",
                75,
                "低排队、预算稳，适合聊天但拍照属性较弱。",
                "reserve",
                "venue_mall_dinner",
                queue=10,
            ),
        ],
        warning="拍照体验弱于 A/B，但风险最低。",
    )


def _plan(title: str, summary: str, travel: int, activities: list[dict], warning: str) -> dict:
    duration_minutes = sum(item["duration_minutes"] for item in activities) + travel
    return {
        "scenario": "friends",
        "title": title,
        "friend_summary": summary,
        "duration_hours": round(duration_minutes / 60, 1),
        "total_travel_minutes": travel,
        "friend_fit_level": "高",
        "social_score": 88,
        "activities": _with_travel(activities),
        "friend_checks": [
            {
                "id": "check_social",
                "label": "有互动和聊天空间",
                "detail": "主活动和晚餐都适合朋友局交流。",
                "status": "pass",
            },
            {
                "id": "check_table",
                "label": "4人桌可订",
                "detail": "晚餐按4人聚餐校验。",
                "status": "pass",
            },
            {"id": "check_route", "label": "路线集中", "detail": f"总通勤约{travel}分钟。", "status": "pass"},
            {"id": "warn_tradeoff", "label": "多人偏好折中", "detail": warning, "status": "warn"},
        ],
        "evidence": _evidence(activities),
        "rejected_options": [
            {"label": "跨区展览", "reasons": ["路线太散，不符合别太远"], "score": 62},
            {"label": "纯散步", "reasons": ["互动性不足，拍照和聊天价值不够"], "score": 58},
        ],
        "share_text": "朋友局安排好了：下午2点半出发，先活动再吃饭，饭后可选咖啡；路线集中，不用跑太远。",
        "route_geojson": {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [HOME_LOCATION, *[item["venue_coords"] for item in activities]],
            },
            "properties": {"total_travel_minutes": travel, "source": "sequence_estimate"},
        },
    }


def _activity(
    order: int,
    activity_type: str,
    name: str,
    address: str,
    coords: list[float],
    start: str,
    duration: int,
    description: str,
    action: str,
    venue_id: str,
    queue: int = 8,
) -> dict:
    return {
        "order": order,
        "type": activity_type,
        "venue_name": name,
        "display_name": name,
        "venue_address": address,
        "venue_coords": coords,
        "start_time": start,
        "duration_minutes": duration,
        "travel_from_prev_minutes": 3 if order > 1 else 0,
        "travel_to_next_minutes": None,
        "action": action,
        "action_details": {
            "special_requests": "4人朋友局，尽量安排适合聊天的位置" if activity_type == "eat" else "4人朋友互动体验",
        },
        "user_description": description,
        "reason": description,
        "source": "showcase_curated",
        "evidence_ids": [f"ev_{venue_id}_place", f"ev_{venue_id}_fit"],
        "friend_features": {
            "queue_minutes": queue,
            "table_for_4": activity_type == "eat",
            "chat_friendly": True,
            "photo_friendly": activity_type == "play",
        },
        "room_venue_id": venue_id,
    }


def _with_travel(activities: list[dict]) -> list[dict]:
    updated = deepcopy(activities)
    for index, activity in enumerate(updated):
        activity["travel_to_next_minutes"] = (
            updated[index + 1].get("travel_from_prev_minutes") if index + 1 < len(updated) else None
        )
    return updated


def _evidence(activities: list[dict]) -> list[dict]:
    evidence = []
    for activity in activities:
        venue_id = activity["room_venue_id"]
        evidence.append(
            {
                "id": f"ev_{venue_id}_place",
                "claim": f"{activity['venue_name']}地点信息已核验",
                "evidence": f"{activity['venue_name']}已纳入当前房间候选。",
                "source": "showcase_curated",
                "venue_name": activity["venue_name"],
            }
        )
        evidence.append(
            {
                "id": f"ev_{venue_id}_fit",
                "claim": f"{activity['venue_name']}适合当前群体偏好",
                "evidence": activity["user_description"],
                "source": "keyword_rule",
                "venue_name": activity["venue_name"],
            }
        )
    evidence.extend(
        [
            {
                "id": "ev_vote_blue_hotpot",
                "claim": "小蓝反对火锅",
                "evidence": "小蓝表达不要火锅，因此晚餐优先排除火锅。",
                "source": "voting_signal",
                "venue_name": "排队网红火锅",
            },
            {
                "id": "ev_vote_green_indoor",
                "claim": "小绿支持室内",
                "evidence": "小绿希望室内和安静，因此折中方案提高室内权重。",
                "source": "voting_signal",
                "venue_name": "室内活动",
            },
            {
                "id": "ev_vote_pink_photo",
                "claim": "小粉支持拍照",
                "evidence": "小粉想要拍照好看的地点，因此保留艺文互动展。",
                "source": "voting_signal",
                "venue_name": "望京艺文互动展",
            },
        ]
    )
    return evidence


def _refresh_room(room: dict) -> None:
    _refresh_plan_votes(room)
    room["group_memory"] = _group_memory(room)
    room["consensus"] = _consensus(room)
    _refresh_voting_evidence(room)


def _refresh_plan_votes(room: dict) -> None:
    votes = room["votes"]
    for option in room["plan_options"]:
        supporters = [vote["participant_id"] for vote in votes if vote["target_id"] == option["option_id"]]
        option["vote_summary"] = {
            "supporters": supporters,
            "opponents": [],
            "concerns": _option_concerns(option["option_id"]),
        }
        option["is_recommended"] = option["option_id"] == room["active_plan_id"]


def _refresh_voting_evidence(room: dict) -> None:
    for option in room["plan_options"]:
        canvas = option["plan_canvas"]
        other_cards = [card for card in canvas.get("evidence_cards", []) if card.get("source_label") != "投票信号"]
        vote_cards = [
            {
                "id": f"room_vote_{index}",
                "title": _reaction_title(reaction),
                "source_label": "投票信号",
                "subject": _reaction_subject(reaction),
                "detail": reaction["reason"],
                "related_timeline_ids": [],
                "related_marker_ids": [],
            }
            for index, reaction in enumerate(room["reactions"], 1)
        ]
        canvas["evidence_cards"] = [*other_cards, *vote_cards]


def _group_memory(room: dict) -> dict:
    return {
        "confirmed_constraints": ["4人朋友局", "不要火锅", "室内优先", "别太远"],
        "soft_preferences": ["拍照友好", "饭后咖啡", "预算适中", "安静聊天"],
        "conflicts": [
            {
                "topic": "饭后续摊",
                "supporters": ["pink"],
                "opponents": ["blue"],
                "resolution": "咖啡设为可选，不强制所有人参加。",
            },
            {
                "topic": "体验最好 vs 避开火锅",
                "supporters": ["red", "pink"],
                "opponents": ["blue"],
                "resolution": "保留拍照活动，替换火锅晚餐。",
            },
        ],
        "history": [
            {"round": 1, "summary": "小红发起朋友聚会，Agent 生成三套方案。"},
            {"round": 2, "summary": "小绿、小蓝、小粉表达偏好，Agent 汇总成群体约束。"},
            {"round": 3, "summary": "折中方案获得更多支持，成为当前推荐。"},
        ],
    }


def _consensus(room: dict) -> dict:
    votes = [vote for vote in room["votes"] if vote["target_id"] == room["active_plan_id"]]
    current = len({vote["participant_id"] for vote in votes})
    status = "consensus_reached" if current >= 3 else "collecting"
    return {
        "required_votes": 3,
        "current_votes": current,
        "status": status,
        "active_plan_id": room["active_plan_id"],
        "summary": f"{current}/4 已支持折中方案，小红可以确认执行。"
        if status == "consensus_reached"
        else f"{current}/4 已投票，仍在收集偏好。",
    }


def _execution_results(canvas: dict) -> list[dict]:
    results = []
    for item in canvas.get("timeline", []):
        if item["category_label"] == "收尾":
            results.append(
                {
                    "id": f"execution_{item['step']}",
                    "label": "已保留可选收尾",
                    "status": "done",
                    "target": item["display_name"],
                    "detail": "不想续摊也可以直接散。",
                    "confirmation": None,
                    "scheduled_time": item["time"],
                    "party_size": 4,
                    "note": "可选，不强制所有成员参加。",
                    "next_step": "已加入群聊文案",
                }
            )
            continue
        label = "已预订4人桌" if item["category_label"] == "用餐" else "已预约活动"
        results.append(
            {
                "id": f"execution_{item['step']}",
                "label": label,
                "status": "done",
                "target": item["display_name"],
                "detail": "已完成确认",
                "confirmation": f"WB-202606-{240 + item['step']}",
                "scheduled_time": item["time"],
                "party_size": 4,
                "note": "备注：靠安静区域，适合聊天。"
                if item["category_label"] == "用餐"
                else "备注：4人朋友互动体验。",
                "next_step": "可取消 / 查看详情 / 导航前往",
            }
        )
    results.append(
        {
            "id": "execution_share",
            "label": "已生成群聊文案",
            "status": "done",
            "target": "朋友群",
            "detail": canvas.get("share_text", ""),
            "confirmation": None,
            "scheduled_time": None,
            "party_size": 4,
            "note": "可直接复制发送。",
            "next_step": "发送给群聊成员",
        }
    )
    return results


def _serialize_room(room: dict, active_user_id: str) -> dict:
    serialized = deepcopy(room)
    if active_user_id not in {participant["id"] for participant in serialized["participants"]}:
        active_user_id = "red"
    serialized["active_user_id"] = active_user_id
    return serialized


def _active_option(room: dict) -> dict:
    return next(option for option in room["plan_options"] if option["option_id"] == room["active_plan_id"])


def _participant(room: dict, actor_id: str) -> dict:
    return next((item for item in room["participants"] if item["id"] == actor_id), room["participants"][0])


def _message(actor: dict, message_type: str, content: str) -> dict:
    return {
        "id": f"msg_{actor['id']}_{int(datetime.now().timestamp() * 1000)}",
        "actor_id": actor["id"],
        "actor_name": actor["name"],
        "actor_avatar": actor["avatar"],
        "type": message_type,
        "content": content,
        "created_at": _now(),
        "related_plan_id": None,
    }


def _agent_message(room: dict, content: str) -> dict:
    return {
        "id": f"msg_agent_{len(room['messages']) + 1}",
        "actor_id": "agent",
        "actor_name": "Agent",
        "actor_avatar": "AI",
        "type": "agent_message",
        "content": content,
        "created_at": _now(),
        "related_plan_id": room.get("active_plan_id"),
    }


def _apply_text_preference(room: dict, actor_id: str, content: str) -> None:
    if "不要火锅" in content or "不吃火锅" in content:
        add_reaction(room["room_id"], actor_id, "venue_hotpot", "food_exclusion", "不要火锅")
    if "室内" in content:
        room["active_plan_id"] = "plan_b"
    if "早点" in content or "不续摊" in content:
        add_reaction(room["room_id"], actor_id, "venue_coffee", "neutral", "咖啡可选")


def _apply_reaction_preference(room: dict, participant_id: str, venue_id: str, reaction_type: str) -> None:
    if reaction_type in {"food_exclusion", "veto"} and venue_id == "venue_hotpot":
        room["active_plan_id"] = "plan_b"
    if participant_id == "green" and reaction_type == "like":
        room["active_plan_id"] = "plan_b"


def _option_concerns(option_id: str) -> list[str]:
    if option_id == "plan_a":
        return ["火锅被反对", "排队偏长"]
    if option_id == "plan_b":
        return ["咖啡为可选"]
    return ["拍照体验较弱"]


def _vote_reason(participant_id: str, plan_id: str) -> str:
    if plan_id == "plan_b":
        return "更照顾大家的偏好"
    if participant_id == "red":
        return "整体体验更完整"
    return "这个方案更符合我的偏好"


def _reaction_label(reaction_type: str) -> str:
    return {
        "like": "想去",
        "neutral": "一般",
        "veto": "不想去",
        "too_far": "太远",
        "too_noisy": "太吵",
        "too_expensive": "太贵",
        "food_exclusion": "不吃这个",
    }.get(reaction_type, "一般")


def _reaction_reason(participant_id: str, reaction_type: str) -> str:
    if reaction_type == "food_exclusion":
        return "不想吃这一类"
    if reaction_type == "like" and participant_id == "pink":
        return "拍照好看"
    if reaction_type == "like" and participant_id == "green":
        return "室内更稳"
    return "作为群体偏好信号"


def _reaction_title(reaction: dict) -> str:
    participant = {"red": "小红", "green": "小绿", "blue": "小蓝", "pink": "小粉"}.get(
        reaction["participant_id"],
        "成员",
    )
    return f"{participant}{reaction['label']}"


def _reaction_subject(reaction: dict) -> str:
    return {
        "venue_art": "望京艺文互动展",
        "venue_hotpot": "排队网红火锅",
        "venue_handcraft": "室内手作体验",
        "venue_coffee": "方恒书店咖啡",
    }.get(reaction["target_id"], "计划地点")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
