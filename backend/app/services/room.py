"""Deterministic staged mock collaborative room service."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from app.services.canvas import build_plan_canvas

DEFAULT_ROOM_ID = "demo_friends_room"
HOME_LOCATION = [116.481, 39.998]

_ROOMS: dict[str, dict] = {}
_FRIENDS_FINAL_STEP = 10
_FAMILY_FINAL_STEP = 8


def get_room(room_id: str = DEFAULT_ROOM_ID, active_user_id: str = "red") -> dict:
    """Return a collaborative room, creating an idle demo room if needed."""
    room = _ROOMS.setdefault(room_id, _build_idle_room(room_id, _scenario_from_room_id(room_id)))
    return _serialize_room(room, active_user_id)


def reset_room(room_id: str = DEFAULT_ROOM_ID, active_user_id: str = "red", scenario: str | None = None) -> dict:
    """Reset a room to an idle staged baseline."""
    next_scenario = _normalize_scenario(scenario or _scenario_from_room_id(room_id))
    _ROOMS[room_id] = _build_idle_room(room_id, next_scenario)
    return _serialize_room(_ROOMS[room_id], active_user_id)


def set_room_scenario(room_id: str, scenario: str, active_user_id: str = "red") -> dict:
    """Switch a room scenario and reset it to a clean idle state."""
    return reset_room(room_id, active_user_id=active_user_id, scenario=scenario)


def advance_room(room_id: str = DEFAULT_ROOM_ID, active_user_id: str = "red") -> dict:
    """Advance one deterministic demo event."""
    room = _ROOMS.setdefault(room_id, _build_idle_room(room_id, _scenario_from_room_id(room_id)))
    if room["scenario"] == "family":
        _advance_family(room)
    else:
        _advance_friends(room)
    _refresh_room(room)
    return _serialize_room(room, active_user_id)


def add_room_message(room_id: str, actor_id: str, content: str) -> dict:
    """Add a participant message and a deterministic Agent response."""
    scenario = _scenario_from_text(content) or _scenario_from_room_id(room_id)
    room = _ROOMS.setdefault(room_id, _build_idle_room(room_id, scenario))
    if scenario != room["scenario"] and room["stage"] == "idle":
        room = _build_idle_room(room_id, scenario)
        _ROOMS[room_id] = room

    actor = _participant(room, actor_id)
    room["messages"].append(_message(room, actor, "user_message", content))
    _set_typing(room)

    if room["stage"] == "idle":
        room["stage"] = "agent_planning"
        room["stage_title"] = "Agent 正在拆解需求"
        room["stage_description"] = _planning_description(room["scenario"])
        room["demo_step_index"] = 2 if room["scenario"] == "friends" else 2
        room["messages"].append(_agent_message(room, _agent_start_copy(room["scenario"])))
    else:
        _apply_text_preference(room, actor["id"], content)
        room["messages"].append(_agent_message(room, _member_feedback_copy(room["scenario"], actor["id"], content)))

    _refresh_room(room)
    return _serialize_room(room, actor["id"])


def add_vote(room_id: str, participant_id: str, plan_id: str, reason: str = "") -> dict:
    """Add or replace a participant plan vote."""
    room = _ROOMS.setdefault(room_id, _build_idle_room(room_id, _scenario_from_room_id(room_id)))
    if not room["plan_options"]:
        _ensure_plan_options(room)
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
            "reason": reason or _vote_reason(participant_id, plan_id, room["scenario"]),
        }
    )
    _apply_vote_preference(room)
    if room["stage"] in {"idle", "host_prompted", "agent_planning", "members_invited", "members_typing"}:
        room["stage"] = "voting"
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
    room = _ROOMS.setdefault(room_id, _build_idle_room(room_id, _scenario_from_room_id(room_id)))
    if not room["plan_options"]:
        _ensure_plan_options(room)
    room["reactions"] = [
        reaction
        for reaction in room["reactions"]
        if not (
            reaction["participant_id"] == participant_id
            and reaction["target_type"] == "venue"
            and reaction["target_id"] == venue_id
        )
    ]
    room["reactions"].append(
        {
            "participant_id": participant_id,
            "target_type": "venue",
            "target_id": venue_id,
            "reaction_type": reaction_type,
            "label": _reaction_label(reaction_type),
            "reason": reason or _reaction_reason(participant_id, reaction_type, room["scenario"]),
        }
    )
    _apply_reaction_preference(room, participant_id, venue_id, reaction_type)
    if room["stage"] in {"options_ready", "voting"}:
        room["stage"] = "consensus_ready"
    _refresh_room(room)
    return _serialize_room(room, participant_id)


def simulate_room(room_id: str = DEFAULT_ROOM_ID, active_user_id: str = "red", scenario: str | None = None) -> dict:
    """Apply the stable collaborative demo script to final-plan-ready state."""
    room = _build_idle_room(room_id, _normalize_scenario(scenario or _scenario_from_room_id(room_id)))
    _ROOMS[room_id] = room
    final_step = _FAMILY_FINAL_STEP if room["scenario"] == "family" else _FRIENDS_FINAL_STEP
    while room["demo_step_index"] < final_step:
        if room["scenario"] == "family":
            _advance_family(room)
        else:
            _advance_friends(room)
        _refresh_room(room)
    return _serialize_room(room, active_user_id)


def execute_room(room_id: str, actor_id: str) -> dict:
    """Execute the active room plan if the host confirms."""
    room = _ROOMS.setdefault(room_id, _build_idle_room(room_id, _scenario_from_room_id(room_id)))
    if actor_id != room["host_user_id"]:
        room["execution_state"] = {
            "status": "ready" if room["plan_options"] else "not_started",
            "host_can_execute": False,
            "summary": f"只有发起人{_host_name(room)}可以确认执行，其他成员可以继续投票和反馈。",
        }
        return _serialize_room(room, actor_id)

    if not room["plan_options"]:
        room["execution_state"] = {
            "status": "not_started",
            "host_can_execute": True,
            "summary": "还没有生成最终方案，先发起需求或播放演示。",
        }
        return _serialize_room(room, actor_id)

    room["stage"] = "done"
    room["stage_title"] = "执行完成"
    room["stage_description"] = "预约、订座、备注和分享文案已准备好。"
    _set_typing(room)
    option = _active_option(room)
    canvas = deepcopy(option["plan_canvas"])
    canvas["status"] = "done"
    canvas["execution_results"] = _execution_results(canvas, room["scenario"])
    canvas["pending_actions"] = []
    option["plan_canvas"] = canvas
    room["execution_state"] = {
        "status": "completed",
        "host_can_execute": True,
        "summary": _execution_summary(room["scenario"]),
    }
    room["messages"].append(_agent_message(room, _execution_message(room["scenario"])))
    _refresh_room(room)
    return _serialize_room(room, actor_id)


def _build_idle_room(room_id: str, scenario: str) -> dict:
    scenario = _normalize_scenario(scenario)
    return {
        "room_id": room_id,
        "scenario": scenario,
        "available_scenarios": ["friends", "family"],
        "stage": "idle",
        "stage_title": "等待发起需求",
        "stage_description": "先输入一句想法，或点击自动演示动作。",
        "typing_participants": [],
        "demo_step_index": 0,
        "host_user_id": "red",
        "active_user_id": "red",
        "participants": _participants(scenario),
        "messages": [],
        "group_memory": _empty_group_memory(),
        "plan_options": [],
        "active_plan_id": "",
        "votes": [],
        "reactions": [],
        "consensus": _empty_consensus(),
        "execution_state": {
            "status": "not_started",
            "host_can_execute": True,
            "summary": "等待发起需求。",
        },
    }


def _advance_friends(room: dict) -> None:
    step = room["demo_step_index"]
    participants = {item["id"]: item for item in room["participants"]}
    if step == 0:
        room["messages"].append(
            _message(room, participants["red"], "user_message", "周末想和朋友聚一聚，吃点好的再找个地方玩，别太远。")
        )
        room["stage"] = "host_prompted"
        room["stage_title"] = "小红已发起朋友局"
        room["stage_description"] = "Agent 将先拆解活动、晚餐、续摊、路线和可用性。"
    elif step == 1:
        room["messages"].append(
            _agent_message(room, "我会先拆成活动、4人桌餐厅、续摊、路线和排队余位几个子任务，随后邀请大家补充偏好。")
        )
        room["stage"] = "agent_planning"
        room["stage_title"] = "Agent 正在拆解任务"
        room["stage_description"] = "本地生活 fan-out 已启动。"
    elif step == 2:
        room["messages"].append(_agent_message(room, "已邀请小绿、小蓝、小粉进入房间。先收集偏好，再给大家 3 个方向。"))
        room["stage"] = "members_invited"
        room["stage_title"] = "成员已邀请"
        room["stage_description"] = "小绿正在补充室内和安静偏好。"
        _set_typing(room, "green")
    elif step == 3:
        _set_typing(room)
        room["messages"].append(
            _message(room, participants["green"], "user_message", "最好室内，最近有点热，也希望安静一点。")
        )
        room["messages"].append(
            _agent_message(room, "收到小绿的反馈：我会把室外市集降级为备选，优先保留室内、安静、适合聊天的活动。")
        )
        room["stage"] = "members_typing"
        room["stage_title"] = "成员正在表达偏好"
        room["stage_description"] = "小蓝正在输入餐饮和预算约束。"
        _set_typing(room, "blue")
    elif step == 4:
        _set_typing(room)
        room["messages"].append(
            _message(room, participants["blue"], "user_message", "不要火锅，预算别太高，饭后我可能想早点回。")
        )
        room["messages"].append(
            _agent_message(room, "小蓝排除了火锅，我会把火锅加入排除项；饭后续摊改成可选，不强制所有人参加。")
        )
        room["stage_description"] = "小粉正在输入拍照和饭后偏好。"
        _set_typing(room, "pink")
    elif step == 5:
        _set_typing(room)
        room["messages"].append(
            _message(room, participants["pink"], "user_message", "想去拍照好看的地方，饭后可以喝咖啡。")
        )
        room["messages"].append(
            _agent_message(
                room,
                "我已汇总大家的偏好：小红要近，小绿要室内安静，"
                "小蓝不要火锅且想早点回，小粉要拍照和咖啡。接下来先给 3 个方向。",
            )
        )
        room["stage"] = "opinions_collected"
        room["stage_title"] = "成员意见已收集"
        room["stage_description"] = "正在生成体验优先、折中推荐、稳妥备选三套方案。"
    elif step == 6:
        _ensure_plan_options(room)
        room["messages"].append(
            _agent_message(room, "第 1 步：我生成了 A 体验优先、B 折中推荐、C 稳妥备选。大家先看方向，再投票。")
        )
        room["stage"] = "options_ready"
        room["stage_title"] = "三套方案已生成"
        room["stage_description"] = "点击方案可切换右侧地图和来源。"
    elif step == 7:
        room["votes"] = [
            _vote("red", "plan_a", "体验最好"),
            _vote("green", "plan_b", "室内和路线更稳"),
            _vote("blue", "plan_b", "避开火锅且预算适中"),
            _vote("pink", "plan_b", "保留拍照和咖啡"),
        ]
        room["active_plan_id"] = "plan_b"
        room["messages"].append(_agent_message(room, "第 2 步：B 折中推荐获得 3/4 支持，同时避开小蓝反对的火锅。"))
        room["stage"] = "voting"
        room["stage_title"] = "投票中"
        room["stage_description"] = "折中方案正在形成共识。"
    elif step == 8:
        room["reactions"] = _friends_reactions()
        room["messages"].append(
            _agent_message(
                room,
                "第 3 步：我把地点反应转成约束，保留小粉喜欢的艺文互动展，把火锅换成轻聚餐厅，咖啡设为可选。",
            )
        )
        room["stage"] = "consensus_ready"
        room["stage_title"] = "共识已形成"
        room["stage_description"] = "3/4 支持 B 折中方案，小红可以确认执行。"
    elif step == 9:
        room["messages"].append(
            _agent_message(
                room,
                "最终采用 B 折中方案：它照顾小红的路线集中、小绿的室内安静、小蓝的不吃火锅和小粉的拍照咖啡需求。",
            )
        )
        room["stage"] = "final_plan_ready"
        room["stage_title"] = "最终方案已生成"
        room["stage_description"] = "可查看完整 Plan Canvas，并由小红确认执行。"
        room["execution_state"] = {
            "status": "ready",
            "host_can_execute": True,
            "summary": "3/4 已支持 B 折中方案，小红可以确认执行。",
        }
    room["demo_step_index"] = min(step + 1, _FRIENDS_FINAL_STEP)


def _advance_family(room: dict) -> None:
    step = room["demo_step_index"]
    participants = {item["id"]: item for item in room["participants"]}
    if step == 0:
        room["messages"].append(
            _message(
                room,
                participants["red"],
                "user_message",
                "今天下午想和老婆孩子去亲子乐园玩 4 到 6 个小时，孩子 5 岁，老婆最近减肥，别离家太远。",
            )
        )
        room["stage"] = "host_prompted"
        room["stage_title"] = "小明已发起家庭出游"
        room["stage_description"] = "Agent 将优先考虑孩子年龄、少走路、少排队和清淡用餐。"
    elif step == 1:
        room["messages"].append(_agent_message(room, _agent_start_copy("family")))
        room["stage"] = "agent_planning"
        room["stage_title"] = "Agent 正在拆解家庭约束"
        room["stage_description"] = "亲子活动、清淡餐、儿童椅、路线疲劳度同步校验。"
    elif step == 2:
        room["messages"].append(
            _agent_message(room, "已把方案发给老婆确认。孩子作为 5 岁亲子画像约束，不需要单独投票。")
        )
        room["stage"] = "members_invited"
        room["stage_title"] = "家庭成员已加入"
        room["stage_description"] = "老婆正在补充饮食和回家时间。"
        _set_typing(room, "wife")
    elif step == 3:
        _set_typing(room)
        room["messages"].append(
            _message(room, participants["wife"], "user_message", "别太油，最好早点回来，孩子累了就别续太久。")
        )
        room["messages"].append(
            _agent_message(
                room,
                "收到老婆的反馈：晚餐改为少油清淡优先，儿童椅和靠边座位会备注；饭后书店只作为可选，孩子累了直接回家。",
            )
        )
        room["stage"] = "opinions_collected"
        room["stage_title"] = "家庭约束已收集"
        room["stage_description"] = "正在生成主方案、早点回家方案和雨天备选。"
    elif step == 4:
        _ensure_plan_options(room)
        room["messages"].append(
            _agent_message(room, "第 1 步：我生成了 A 亲子体验优先、B 早点回家优先、C 雨天室内备选。")
        )
        room["stage"] = "options_ready"
        room["stage_title"] = "家庭三方案已生成"
        room["stage_description"] = "默认推荐 B：保留亲子体验，同时更早结束。"
    elif step == 5:
        room["votes"] = [
            _vote("red", "plan_b", "路线近，孩子不容易累"),
            _vote("wife", "plan_b", "清淡少油，也能早点回"),
        ]
        room["active_plan_id"] = "plan_b"
        room["messages"].append(_agent_message(room, "第 2 步：小明和老婆都支持 B，孩子约束也满足，因此进入家庭共识。"))
        room["stage"] = "voting"
        room["stage_title"] = "家庭确认中"
        room["stage_description"] = "2/2 已支持 B 早点回家优先。"
    elif step == 6:
        room["reactions"] = _family_reactions()
        room["messages"].append(
            _agent_message(room, "第 3 步：我把清淡少油、儿童椅、少走路和早点回家写入最终方案与执行备注。")
        )
        room["stage"] = "consensus_ready"
        room["stage_title"] = "家庭共识已形成"
        room["stage_description"] = "小明可以确认执行。"
    elif step == 7:
        room["messages"].append(
            _agent_message(
                room, "最终采用 B：孩子有室内亲子活动，晚餐清淡少油并备注儿童椅，书店收尾可跳过，预计 18:30 左右回家。"
            )
        )
        room["stage"] = "final_plan_ready"
        room["stage_title"] = "最终家庭方案已生成"
        room["stage_description"] = "可查看完整家庭 Plan Canvas，并由小明确认执行。"
        room["execution_state"] = {
            "status": "ready",
            "host_can_execute": True,
            "summary": "2/2 已确认 B 早点回家方案，小明可以执行。",
        }
    room["demo_step_index"] = min(step + 1, _FAMILY_FINAL_STEP)


def _participants(scenario: str) -> list[dict]:
    if scenario == "family":
        return [
            _participant_data(
                "red", "小明", "red", "明", "host", "online", ["别太远", "少走路"], "near", "normal", "family"
            ),
            _participant_data(
                "wife", "老婆", "purple", "妻", "member", "online", ["清淡少油", "早点回"], "near", "normal", "calm"
            ),
            _participant_data(
                "child", "孩子", "amber", "童", "profile", "profile", ["5岁", "亲子适配"], "near", "normal", "playful"
            ),
            _participant_data(
                "agent", "Agent", "zinc", "AI", "agent", "agent", ["规划", "校验", "执行"], "near", "normal", "planner"
            ),
        ]
    return [
        _participant_data(
            "red", "小红", "red", "红", "host", "online", ["别太远", "效率"], "near", "normal", "efficient"
        ),
        _participant_data(
            "green", "小绿", "green", "绿", "member", "online", ["室内", "安静"], "near", "normal", "quiet"
        ),
        _participant_data(
            "blue",
            "小蓝",
            "blue",
            "蓝",
            "member",
            "online",
            ["预算适中", "早点回"],
            "medium",
            "moderate",
            "balanced",
            ["火锅"],
        ),
        _participant_data(
            "pink", "小粉", "pink", "粉", "member", "online", ["拍照", "饭后咖啡"], "medium", "normal", "photo"
        ),
        _participant_data(
            "agent", "Agent", "zinc", "AI", "agent", "agent", ["规划", "校验", "执行"], "near", "normal", "planner"
        ),
    ]


def _participant_data(
    participant_id: str,
    name: str,
    color: str,
    avatar: str,
    role: str,
    status: str,
    likes: list[str],
    distance: str,
    budget: str,
    vibe: str,
    food_exclusions: list[str] | None = None,
) -> dict:
    return {
        "id": participant_id,
        "name": name,
        "color": color,
        "avatar": avatar,
        "role": role,
        "status": status,
        "preference_profile": {
            "distance": distance,
            "budget": budget,
            "vibe": vibe,
            "food_exclusions": food_exclusions or [],
            "likes": likes,
        },
    }


def _ensure_plan_options(room: dict) -> None:
    if room["plan_options"]:
        return
    room["active_plan_id"] = "plan_b"
    room["plan_options"] = _build_plan_options(room)


def _build_plan_options(room: dict) -> list[dict]:
    definitions = _family_option_definitions() if room["scenario"] == "family" else _friends_option_definitions()
    options = []
    for definition in definitions:
        plan = definition["plan"]
        state = {
            "scenario": room["scenario"],
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
                "is_recommended": definition["option_id"] == room["active_plan_id"],
            }
        )
    return options


def _friends_option_definitions() -> list[dict]:
    return [
        {
            "option_id": "plan_a",
            "label": "A 体验优先",
            "positioning": "拍照体验最好，活动最丰富，但火锅和排队风险更高。",
            "score": {"distance": 78, "budget": 70, "photo": 96, "indoor": 72, "consensus": 74},
            "plan": _friends_plan_a(),
        },
        {
            "option_id": "plan_b",
            "label": "B 折中推荐",
            "positioning": "路线最近，避开火锅，照顾最多成员偏好。",
            "score": {"distance": 92, "budget": 86, "photo": 84, "indoor": 90, "consensus": 91},
            "plan": _friends_plan_b(),
        },
        {
            "option_id": "plan_c",
            "label": "C 稳妥备选",
            "positioning": "全室内、低排队、可直接散，天气不好也稳。",
            "score": {"distance": 88, "budget": 82, "photo": 62, "indoor": 98, "consensus": 80},
            "plan": _friends_plan_c(),
        },
    ]


def _family_option_definitions() -> list[dict]:
    return [
        {
            "option_id": "plan_a",
            "label": "A 亲子体验优先",
            "positioning": "亲子体验更完整，但总时长更接近 5 小时。",
            "score": {"distance": 82, "budget": 80, "photo": 70, "indoor": 92, "consensus": 78},
            "plan": _family_plan_a(),
        },
        {
            "option_id": "plan_b",
            "label": "B 早点回家优先",
            "positioning": "保留亲子活动，晚餐清淡少油，收尾可跳过。",
            "score": {"distance": 94, "budget": 86, "photo": 64, "indoor": 94, "consensus": 93},
            "plan": _family_plan_b(),
        },
        {
            "option_id": "plan_c",
            "label": "C 雨天室内备选",
            "positioning": "全室内、最低疲劳，适合天气变化或孩子状态一般。",
            "score": {"distance": 90, "budget": 84, "photo": 58, "indoor": 98, "consensus": 84},
            "plan": _family_plan_c(),
        },
    ]


def _friends_plan_a() -> dict:
    return _friends_plan(
        title="体验优先",
        summary="体验优先：先去望京艺文互动展拍照，再去氛围火锅，饭后清吧续摊；适合想玩得更丰富的一组。",
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


def _friends_plan_b() -> dict:
    return _friends_plan(
        title="折中推荐",
        summary="折中方案：保留拍照友好的艺文互动展，晚餐换成轻聚餐厅，饭后咖啡设为可选；路线集中，避开火锅。",
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


def _friends_plan_c() -> dict:
    return _friends_plan(
        title="稳妥备选",
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


def _family_plan_a() -> dict:
    return _family_plan(
        title="亲子体验优先",
        summary="亲子体验优先：室内亲子科学馆玩得更完整，晚餐安排清淡家庭餐，饭后绘本书店轻松收尾。",
        travel=10,
        fatigue=24,
        activities=[
            _activity(
                1,
                "play",
                "太阳宫亲子科学馆",
                "太阳宫亲子中心 3 层",
                [116.482, 39.998],
                "14:30",
                125,
                "适合5岁孩子的室内探索活动，互动性强，排队可控。",
                "book",
                "venue_family_science",
                queue=8,
                scenario="family",
            ),
            _activity(
                2,
                "eat",
                "轻氧低脂家庭餐厅",
                "合生麒麟社 1 层",
                [116.4852, 39.9991],
                "17:20",
                70,
                "清淡少油可选，已备注儿童椅和靠边座位。",
                "reserve",
                "venue_family_light_dinner",
                queue=8,
                scenario="family",
            ),
            _activity(
                3,
                "extra",
                "方恒绘本书店",
                "方恒购物中心 3 层",
                [116.4871, 39.9988],
                "18:35",
                35,
                "孩子状态好就轻松收尾，累了可以直接回家。",
                "no_action",
                "venue_picture_book",
                scenario="family",
            ),
        ],
        warning="总时长更完整，但孩子累了建议跳过书店。",
    )


def _family_plan_b() -> dict:
    return _family_plan(
        title="早点回家优先",
        summary="家庭折中方案：先去室内亲子乐园，5点左右吃清淡家庭餐，绘本书店作为可选收尾；孩子累了可直接回家。",
        travel=6,
        fatigue=18,
        activities=[
            _activity(
                1,
                "play",
                "太阳宫室内亲子乐园",
                "太阳宫亲子中心 2 层",
                [116.4818, 39.9977],
                "14:30",
                105,
                "适合5岁孩子，室内、少走路、排队可控。",
                "book",
                "venue_family_play",
                queue=7,
                scenario="family",
            ),
            _activity(
                2,
                "eat",
                "轻氧低脂家庭餐厅",
                "合生麒麟社 1 层",
                [116.4852, 39.9991],
                "17:00",
                60,
                "清淡少油可选，已备注儿童椅、靠边座位和少油口味。",
                "reserve",
                "venue_family_light_dinner",
                queue=8,
                scenario="family",
            ),
            _activity(
                3,
                "extra",
                "方恒绘本书店",
                "方恒购物中心 3 层",
                [116.4871, 39.9988],
                "18:05",
                25,
                "可选收尾，不影响18:30左右回家。",
                "no_action",
                "venue_picture_book",
                scenario="family",
            ),
        ],
        warning="绘本书店为可选，优先保证早点回家。",
    )


def _family_plan_c() -> dict:
    return _family_plan(
        title="雨天室内备选",
        summary="雨天室内备选：商场亲子体验加家庭餐厅，全程室内，路线最稳，晚餐后直接回家。",
        travel=5,
        fatigue=15,
        activities=[
            _activity(
                1,
                "play",
                "望京商场亲子体验馆",
                "望京 SOHO T1",
                [116.4808, 39.9969],
                "14:30",
                95,
                "全室内、低疲劳，适合天气变化或孩子状态一般。",
                "book",
                "venue_family_indoor",
                queue=6,
                scenario="family",
            ),
            _activity(
                2,
                "eat",
                "商场清淡家庭餐厅",
                "望京 SOHO B1",
                [116.4816, 39.9972],
                "16:45",
                55,
                "低排队，清淡少油可选，已备注儿童椅。",
                "reserve",
                "venue_family_mall_dinner",
                queue=6,
                scenario="family",
            ),
        ],
        warning="体验丰富度低于 A/B，但风险最低。",
    )


def _friends_plan(title: str, summary: str, travel: int, activities: list[dict], warning: str) -> dict:
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
            {"id": "check_table", "label": "4人桌可订", "detail": "晚餐按4人聚餐校验。", "status": "pass"},
            {"id": "check_route", "label": "路线集中", "detail": f"总通勤约{travel}分钟。", "status": "pass"},
            {"id": "warn_tradeoff", "label": "多人偏好折中", "detail": warning, "status": "warn"},
        ],
        "evidence": _evidence(activities, "friends"),
        "rejected_options": [
            {"label": "跨区展览", "reasons": ["路线太散，不符合别太远"], "score": 62},
            {"label": "纯散步", "reasons": ["互动性不足，拍照和聊天价值不够"], "score": 58},
        ],
        "share_text": "朋友局安排好了：下午2点半先活动再吃饭，饭后可选咖啡；路线集中，不用跑太远。",
        "route_geojson": _route_geojson(activities, travel),
    }


def _family_plan(title: str, summary: str, travel: int, fatigue: int, activities: list[dict], warning: str) -> dict:
    duration_minutes = sum(item["duration_minutes"] for item in activities) + travel
    return {
        "scenario": "family",
        "title": title,
        "family_summary": summary,
        "duration_hours": round(duration_minutes / 60, 1),
        "total_travel_minutes": travel,
        "fatigue_score": fatigue,
        "fatigue_level": "low",
        "activities": _with_travel(activities),
        "family_checks": [
            {"id": "check_child", "label": "适合5岁孩子", "detail": "活动按5岁亲子适配校验。", "status": "pass"},
            {
                "id": "check_walk",
                "label": "少走路少排队",
                "detail": f"总通勤约{travel}分钟，最长等待不超过8分钟。",
                "status": "pass",
            },
            {"id": "check_diet", "label": "清淡少油可选", "detail": "晚餐已备注少油、清淡和儿童椅。", "status": "pass"},
            {"id": "warn_tail", "label": "轻量收尾可跳过", "detail": warning, "status": "warn"},
        ],
        "evidence": _evidence(activities, "family"),
        "rejected_options": [
            {"label": "油炸小吃", "reasons": ["不符合老婆减脂和清淡需求"], "score": 52},
            {"label": "户外长距离乐园", "reasons": ["步行和天气风险偏高"], "score": 58},
        ],
        "share_text": (
            "家庭下午安排好了：先去室内亲子活动，5点左右吃清淡家庭餐，"
            "儿童椅和少油已备注；孩子累了就直接回家。"
        ),
        "route_geojson": _route_geojson(activities, travel),
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
    scenario: str = "friends",
) -> dict:
    features_key = "family_features" if scenario == "family" else "friend_features"
    features = {
        "queue_minutes": queue,
        "table_for_4": scenario == "friends" and activity_type == "eat",
        "chat_friendly": True,
        "photo_friendly": activity_type == "play",
        "child_friendly": scenario == "family",
        "diet_friendly": scenario == "family" and activity_type == "eat",
        "child_seat": scenario == "family" and activity_type == "eat",
        "indoor": True,
    }
    special_requests = (
        "儿童椅、少油/清淡、靠边座位"
        if scenario == "family" and activity_type == "eat"
        else "4人朋友局，尽量安排适合聊天的位置"
        if scenario == "friends" and activity_type == "eat"
        else "亲子室内体验"
        if scenario == "family"
        else "4人朋友互动体验"
    )
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
        "action_details": {"special_requests": special_requests},
        "user_description": description,
        "reason": description,
        "source": "showcase_curated",
        "evidence_ids": [f"ev_{venue_id}_place", f"ev_{venue_id}_fit"],
        features_key: features,
        "room_venue_id": venue_id,
    }


def _with_travel(activities: list[dict]) -> list[dict]:
    updated = deepcopy(activities)
    for index, activity in enumerate(updated):
        activity["travel_to_next_minutes"] = (
            updated[index + 1].get("travel_from_prev_minutes") if index + 1 < len(updated) else None
        )
    return updated


def _route_geojson(activities: list[dict], travel: int) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [HOME_LOCATION, *[item["venue_coords"] for item in activities]],
        },
        "properties": {"total_travel_minutes": travel, "source": "sequence_estimate"},
    }


def _evidence(activities: list[dict], scenario: str) -> list[dict]:
    evidence = []
    for activity in activities:
        venue_id = activity["room_venue_id"]
        evidence.extend(
            [
                {
                    "id": f"ev_{venue_id}_place",
                    "claim": f"{activity['venue_name']}地点信息已核验",
                    "evidence": f"{activity['venue_name']}已纳入当前房间候选。",
                    "source": "showcase_curated",
                    "venue_name": activity["venue_name"],
                },
                {
                    "id": f"ev_{venue_id}_fit",
                    "claim": f"{activity['venue_name']}适合当前群体偏好",
                    "evidence": activity["user_description"],
                    "source": "keyword_rule",
                    "venue_name": activity["venue_name"],
                },
            ]
        )
    if scenario == "family":
        evidence.extend(
            [
                {
                    "id": "ev_vote_wife_light",
                    "claim": "老婆要求清淡少油",
                    "evidence": "晚餐已备注少油、清淡和儿童椅。",
                    "source": "voting_signal",
                    "venue_name": "轻氧低脂家庭餐厅",
                },
                {
                    "id": "ev_child_profile",
                    "claim": "孩子5岁亲子约束",
                    "evidence": "活动按5岁孩子、室内、少走路和低排队组织。",
                    "source": "voting_signal",
                    "venue_name": "太阳宫室内亲子乐园",
                },
            ]
        )
    else:
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
    if room["stage"] in {"final_plan_ready", "done"} and room["execution_state"]["status"] == "not_started":
        room["execution_state"] = {
            "status": "ready",
            "host_can_execute": True,
            "summary": _ready_summary(room),
        }


def _refresh_plan_votes(room: dict) -> None:
    for option in room["plan_options"]:
        supporters = [vote["participant_id"] for vote in room["votes"] if vote["target_id"] == option["option_id"]]
        option["vote_summary"] = {
            "supporters": supporters,
            "opponents": [],
            "concerns": _option_concerns(option["option_id"], room["scenario"]),
        }
        option["is_recommended"] = option["option_id"] == room["active_plan_id"]


def _refresh_voting_evidence(room: dict) -> None:
    for option in room["plan_options"]:
        canvas = option["plan_canvas"]
        other_cards = [card for card in canvas.get("evidence_cards", []) if card.get("source_label") != "投票信号"]
        vote_cards = [
            {
                "id": f"room_vote_{index}",
                "title": _reaction_title(reaction, room["scenario"]),
                "source_label": "投票信号",
                "subject": _reaction_subject(reaction, room["scenario"]),
                "detail": reaction["reason"],
                "related_timeline_ids": [],
                "related_marker_ids": [],
            }
            for index, reaction in enumerate(room["reactions"], 1)
        ]
        canvas["evidence_cards"] = [*other_cards, *vote_cards]


def _group_memory(room: dict) -> dict:
    if room["stage"] in {"idle", "host_prompted", "agent_planning"}:
        if room["scenario"] == "family" and room["messages"]:
            return {
                "confirmed_constraints": ["孩子5岁", "别太远"],
                "soft_preferences": ["亲子适配", "少走路"],
                "conflicts": [],
                "history": [{"round": 1, "summary": "小明发起家庭出游，Agent 正在拆解约束。"}],
            }
        if room["messages"]:
            return {
                "confirmed_constraints": ["4人朋友局", "别太远"],
                "soft_preferences": ["吃点好的", "有吃有玩"],
                "conflicts": [],
                "history": [{"round": 1, "summary": "小红发起朋友聚会，Agent 正在拆解任务。"}],
            }
        return _empty_group_memory()
    if room["scenario"] == "family":
        return {
            "confirmed_constraints": ["孩子5岁", "清淡少油", "儿童椅", "少走路", "早点回家"],
            "soft_preferences": ["室内亲子", "低排队", "可跳过收尾"],
            "conflicts": [
                {
                    "topic": "亲子体验 vs 早点回家",
                    "supporters": ["red"],
                    "opponents": ["wife"],
                    "resolution": "保留亲子活动，饭后收尾设为可选。",
                }
            ],
            "history": [
                {"round": 1, "summary": "小明发起家庭出游，说明孩子5岁和别太远。"},
                {"round": 2, "summary": "老婆补充清淡少油和早点回家。"},
                {"round": 3, "summary": "Agent 推荐 B 早点回家优先方案。"},
            ],
        }
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
    if not room["plan_options"]:
        return _empty_consensus()
    votes = [vote for vote in room["votes"] if vote["target_id"] == room["active_plan_id"]]
    current = len({vote["participant_id"] for vote in votes})
    required = 2 if room["scenario"] == "family" else 3
    total = 2 if room["scenario"] == "family" else 4
    status = "consensus_reached" if current >= required else "collecting"
    plan_name = "B 早点回家方案" if room["scenario"] == "family" else "B 折中方案"
    return {
        "required_votes": required,
        "current_votes": current,
        "status": status,
        "active_plan_id": room["active_plan_id"],
        "summary": f"{current}/{total} 已支持{plan_name}，{_host_name(room)}可以确认执行。"
        if status == "consensus_reached"
        else f"{current}/{total} 已投票，仍在收集偏好。",
    }


def _empty_group_memory() -> dict:
    return {"confirmed_constraints": [], "soft_preferences": [], "conflicts": [], "history": []}


def _empty_consensus() -> dict:
    return {
        "required_votes": 3,
        "current_votes": 0,
        "status": "collecting",
        "active_plan_id": "",
        "summary": "尚未开始投票。",
    }


def _friends_reactions() -> list[dict]:
    return [
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


def _vote(participant_id: str, target_id: str, reason: str) -> dict:
    return {
        "participant_id": participant_id,
        "target_type": "plan",
        "target_id": target_id,
        "vote_type": "support",
        "reason": reason,
    }


def _family_reactions() -> list[dict]:
    return [
        {
            "participant_id": "wife",
            "target_type": "venue",
            "target_id": "venue_family_light_dinner",
            "reaction_type": "like",
            "label": "想去",
            "reason": "清淡少油，还能备注儿童椅",
        },
        {
            "participant_id": "red",
            "target_type": "venue",
            "target_id": "venue_family_play",
            "reaction_type": "like",
            "label": "想去",
            "reason": "孩子能玩，路也近",
        },
        {
            "participant_id": "wife",
            "target_type": "venue",
            "target_id": "venue_picture_book",
            "reaction_type": "neutral",
            "label": "可选",
            "reason": "孩子累了就跳过",
        },
    ]


def _execution_results(canvas: dict, scenario: str) -> list[dict]:
    results = []
    party_size = 3 if scenario == "family" else 4
    for item in canvas.get("timeline", []):
        category = item["category_label"]
        if category == "收尾":
            results.append(
                {
                    "id": f"execution_{item['step']}",
                    "label": "已保留可选收尾",
                    "status": "done",
                    "target": item["display_name"],
                    "detail": "可跳过，不影响主方案完成。",
                    "confirmation": None,
                    "scheduled_time": item["time"],
                    "party_size": party_size,
                    "note": "孩子累了直接回家。" if scenario == "family" else "不想续摊也可以直接散。",
                    "next_step": "已加入分享文案",
                }
            )
            continue
        if category == "用餐":
            label = "已预订家庭餐厅" if scenario == "family" else "已预订4人桌"
            note = "备注：儿童椅、少油/清淡、靠边座位。" if scenario == "family" else "备注：靠安静区域，适合聊天。"
        else:
            label = "已预约亲子活动" if scenario == "family" else "已预约活动"
            note = "备注：适合5岁孩子，少走路。" if scenario == "family" else "备注：4人朋友互动体验。"
        results.append(
            {
                "id": f"execution_{item['step']}",
                "label": label,
                "status": "done",
                "target": item["display_name"],
                "detail": "已完成确认",
                "confirmation": f"WB-202606-{240 + item['step']}",
                "scheduled_time": item["time"],
                "party_size": party_size,
                "note": note,
                "next_step": "可取消 / 查看详情 / 导航前往",
            }
        )
    results.append(
        {
            "id": "execution_share",
            "label": "已生成群聊文案" if scenario == "friends" else "已生成发给老婆的文案",
            "status": "done",
            "target": "朋友群" if scenario == "friends" else "老婆",
            "detail": canvas.get("share_text", ""),
            "confirmation": None,
            "scheduled_time": None,
            "party_size": party_size,
            "note": "可直接复制发送。",
            "next_step": "发送给群聊成员" if scenario == "friends" else "发送给老婆确认",
        }
    )
    return results


def _serialize_room(room: dict, active_user_id: str) -> dict:
    serialized = deepcopy(room)
    valid_ids = {participant["id"] for participant in serialized["participants"] if participant["role"] != "profile"}
    if active_user_id not in valid_ids:
        active_user_id = "red"
    serialized["active_user_id"] = active_user_id
    return serialized


def _active_option(room: dict) -> dict:
    return next(option for option in room["plan_options"] if option["option_id"] == room["active_plan_id"])


def _participant(room: dict, actor_id: str) -> dict:
    return next(
        (item for item in room["participants"] if item["id"] == actor_id and item["role"] != "profile"),
        room["participants"][0],
    )


def _message(room: dict, actor: dict, message_type: str, content: str) -> dict:
    return {
        "id": f"msg_{actor['id']}_{len(room['messages']) + 1}_{int(datetime.now().timestamp() * 1000)}",
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
        "id": f"msg_agent_{len(room['messages']) + 1}_{int(datetime.now().timestamp() * 1000)}",
        "actor_id": "agent",
        "actor_name": "Agent",
        "actor_avatar": "AI",
        "type": "agent_message",
        "content": content,
        "created_at": _now(),
        "related_plan_id": room.get("active_plan_id") or None,
    }


def _set_typing(room: dict, *participant_ids: str) -> None:
    room["typing_participants"] = list(participant_ids)


def _apply_vote_preference(room: dict) -> None:
    counts: dict[str, int] = {}
    for vote in room["votes"]:
        counts[vote["target_id"]] = counts.get(vote["target_id"], 0) + 1
    if not counts:
        return
    top_plan_id = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    has_hotpot_veto = any(reaction["target_id"] == "venue_hotpot" for reaction in room["reactions"])
    room["active_plan_id"] = "plan_b" if top_plan_id == "plan_a" and has_hotpot_veto else top_plan_id


def _apply_text_preference(room: dict, actor_id: str, content: str) -> None:
    if "不要火锅" in content or "不吃火锅" in content:
        _append_reaction(room, actor_id, "venue_hotpot", "food_exclusion", "不要火锅")
        room["active_plan_id"] = "plan_b"
    if "室内" in content:
        room["active_plan_id"] = "plan_b"
    if "早点" in content or "不续摊" in content:
        target = "venue_picture_book" if room["scenario"] == "family" else "venue_coffee"
        _append_reaction(room, actor_id, target, "neutral", "设为可选")


def _apply_reaction_preference(room: dict, participant_id: str, venue_id: str, reaction_type: str) -> None:
    if reaction_type in {"food_exclusion", "veto"} and venue_id == "venue_hotpot":
        room["active_plan_id"] = "plan_b"
    if participant_id in {"green", "wife"} and reaction_type == "like":
        room["active_plan_id"] = "plan_b"


def _append_reaction(room: dict, participant_id: str, venue_id: str, reaction_type: str, reason: str) -> None:
    room["reactions"].append(
        {
            "participant_id": participant_id,
            "target_type": "venue",
            "target_id": venue_id,
            "reaction_type": reaction_type,
            "label": _reaction_label(reaction_type),
            "reason": reason,
        }
    )


def _option_concerns(option_id: str, scenario: str) -> list[str]:
    if scenario == "family":
        if option_id == "plan_a":
            return ["总时长略长"]
        if option_id == "plan_b":
            return ["书店收尾可跳过"]
        return ["体验丰富度较低"]
    if option_id == "plan_a":
        return ["火锅被反对", "排队偏长"]
    if option_id == "plan_b":
        return ["咖啡为可选"]
    return ["拍照体验较弱"]


def _vote_reason(participant_id: str, plan_id: str, scenario: str) -> str:
    if scenario == "family":
        if plan_id == "plan_b":
            return "更照顾孩子和早点回家"
        return "这个方向可以作为备选"
    if plan_id == "plan_b":
        return "更照顾大家的偏好"
    if participant_id == "red":
        return "整体体验更完整"
    return "这个方案更符合我的偏好"


def _reaction_label(reaction_type: str) -> str:
    return {
        "like": "想去",
        "neutral": "可选",
        "veto": "不想去",
        "too_far": "太远",
        "too_noisy": "太吵",
        "too_expensive": "太贵",
        "food_exclusion": "不吃这个",
    }.get(reaction_type, "一般")


def _reaction_reason(participant_id: str, reaction_type: str, scenario: str) -> str:
    if scenario == "family":
        if participant_id == "wife":
            return "清淡、轻松、早点回"
        return "照顾孩子状态"
    if reaction_type == "food_exclusion":
        return "不想吃这一类"
    if reaction_type == "like" and participant_id == "pink":
        return "拍照好看"
    if reaction_type == "like" and participant_id == "green":
        return "室内更稳"
    return "作为群体偏好信号"


def _reaction_title(reaction: dict, scenario: str) -> str:
    participant = _participant_name(reaction["participant_id"], scenario)
    return f"{participant}{reaction['label']}"


def _reaction_subject(reaction: dict, scenario: str) -> str:
    mapping = {
        "venue_art": "望京艺文互动展",
        "venue_hotpot": "排队网红火锅",
        "venue_handcraft": "室内手作体验",
        "venue_coffee": "方恒书店咖啡",
        "venue_family_light_dinner": "轻氧低脂家庭餐厅",
        "venue_family_play": "太阳宫室内亲子乐园",
        "venue_picture_book": "方恒绘本书店",
    }
    if scenario == "family" and reaction["target_id"] not in mapping:
        return "家庭计划地点"
    return mapping.get(reaction["target_id"], "计划地点")


def _participant_name(participant_id: str, scenario: str) -> str:
    if scenario == "family":
        return {"red": "小明", "wife": "老婆", "child": "孩子", "agent": "Agent"}.get(participant_id, "成员")
    return {"red": "小红", "green": "小绿", "blue": "小蓝", "pink": "小粉", "agent": "Agent"}.get(
        participant_id, "成员"
    )


def _host_name(room: dict) -> str:
    return "小明" if room["scenario"] == "family" else "小红"


def _planning_description(scenario: str) -> str:
    if scenario == "family":
        return "亲子活动、清淡餐、儿童椅、路线疲劳度同步校验。"
    return "活动、餐厅、续摊、路线、排队余位同步校验。"


def _agent_start_copy(scenario: str) -> str:
    if scenario == "family":
        return "我会优先考虑适合5岁孩子、少走路、排队可控、晚餐清淡少油，并把饭后收尾设为可选。"
    return "我会先生成 3 个方向，大家可以投票，也可以直接说不喜欢哪里。"


def _member_feedback_copy(scenario: str, actor_id: str, content: str) -> str:
    if scenario == "family":
        if actor_id == "wife":
            return "根据老婆的反馈，我已把晚餐改成清淡少油优先，并把儿童椅、靠边座位和早点回家写入执行备注。"
        return "我已把这条反馈加入家庭约束，继续保持孩子适配、少走路和清淡用餐。"
    if actor_id == "blue" or "火锅" in content:
        return "根据小蓝的“不要火锅”，我已排除火锅，只替换晚餐候选，活动和咖啡不受影响。"
    if actor_id == "green" or "室内" in content:
        return "根据小绿的室内偏好，我会优先保留室内活动，并降低户外地点权重。"
    if actor_id == "pink" or "拍照" in content:
        return "根据小粉的拍照和咖啡偏好，我会保留艺文互动展，并把饭后咖啡设为可选收尾。"
    return "我已把这条反馈加入当前群体约束，并会在现有计划上增量调整。"


def _ready_summary(room: dict) -> str:
    if room["scenario"] == "family":
        return "2/2 已确认 B 早点回家方案，小明可以执行。"
    return "3/4 已支持 B 折中方案，小红可以确认执行。"


def _execution_summary(scenario: str) -> str:
    if scenario == "family":
        return "家庭方案已确认，亲子活动、家庭餐厅、儿童椅、少油备注和发给老婆的文案已准备好。"
    return "3/4 已达成共识，小红已确认执行，预约、订座、备注和群聊文案已准备好。"


def _execution_message(scenario: str) -> str:
    if scenario == "family":
        return "已按家庭方案执行：亲子活动预约、家庭餐厅订座、儿童椅和少油备注、发给老婆的文案都已完成。"
    return "已按折中方案执行：活动预约、4人桌订座、靠安静区域备注和群聊文案都已完成。"


def _scenario_from_room_id(room_id: str) -> str:
    return "family" if "family" in room_id else "friends"


def _scenario_from_text(content: str) -> str | None:
    family_keywords = ["老婆", "孩子", "亲子", "家庭", "儿童"]
    friends_keywords = ["朋友", "聚会", "续摊", "拍照"]
    if any(keyword in content for keyword in family_keywords):
        return "family"
    if any(keyword in content for keyword in friends_keywords):
        return "friends"
    return None


def _normalize_scenario(scenario: str) -> str:
    return "family" if scenario == "family" else "friends"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
