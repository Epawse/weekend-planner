"""LLM RoomPatch generation for the hybrid collaborative room."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Protocol

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.llm.provider import llm_factory
from app.services.room_agent_schemas import RoomPatch

logger = structlog.get_logger()


class LLMRoomAgentError(Exception):
    """LLM RoomPatch generation failed and the caller should use scripted fallback."""


class _LLMResponse(Protocol):
    content: str


async def generate_room_patch(room: dict) -> RoomPatch:
    """Generate a validated RoomPatch for the next room advance."""
    prompt_payload = _build_prompt_payload(room)
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(prompt_payload, ensure_ascii=False)),
    ]

    try:
        response = await llm_factory.invoke_with_fallback(messages, temperature=0.35)
        return _parse_room_patch(_response_content(response))
    except Exception as first_error:
        logger.warning("room_patch_generation_failed", reason=str(first_error))
        try:
            repair_messages = [
                SystemMessage(content=_REPAIR_PROMPT),
                HumanMessage(
                    content=json.dumps(
                        {
                            "schema_summary": _SCHEMA_SUMMARY,
                            "bad_output_or_error": str(first_error),
                            "room_context": prompt_payload,
                        },
                        ensure_ascii=False,
                    )
                ),
            ]
            repaired = await llm_factory.invoke_with_fallback(repair_messages, temperature=0.1)
            return _parse_room_patch(_response_content(repaired))
        except Exception as repair_error:
            logger.warning("room_patch_repair_failed", reason=str(repair_error))
            raise LLMRoomAgentError(str(repair_error)) from repair_error


_PATCH_SENTINEL = "===PATCH==="


async def stream_room_patch(room: dict) -> AsyncGenerator[dict, None]:
    """Stream the agent's *visible* reasoning, then yield the validated RoomPatch.

    Yields ``{"type": "reasoning", "delta": str}`` while the rationale streams,
    then exactly one ``{"type": "patch", "patch": RoomPatch}``. Raises
    LLMRoomAgentError on failure so the caller can fall back to the scripted path.
    """
    prompt_payload = _build_prompt_payload(room)
    messages = [
        SystemMessage(content=_STREAM_SYSTEM_PROMPT),
        HumanMessage(content=json.dumps(prompt_payload, ensure_ascii=False)),
    ]
    order = llm_factory.get_provider_order()
    if not order:
        raise LLMRoomAgentError("No LLM providers configured")
    # Low hidden-thinking effort so the reasoning is produced as visible,
    # streamable text (and the first token arrives sooner).
    model = llm_factory.get_model(provider=order[0], temperature=0.35, reasoning_effort="low")

    buffer = ""
    emitted = 0
    in_json = False
    try:
        async for chunk in model.astream(messages):
            piece = getattr(chunk, "content", "")
            if not isinstance(piece, str) or not piece:
                continue
            buffer += piece
            if in_json:
                continue
            # Reasoning ends at the sentinel, or at the JSON's opening brace.
            candidates = [index for index in (buffer.find(_PATCH_SENTINEL), buffer.find("{")) if index >= 0]
            stop = min(candidates) if candidates else -1
            if stop >= 0:
                if stop > emitted:
                    yield {"type": "reasoning", "delta": buffer[emitted:stop]}
                emitted = stop
                in_json = True
            else:
                # Hold back a sentinel-length tail so a split sentinel never leaks.
                safe = len(buffer) - len(_PATCH_SENTINEL)
                if safe > emitted:
                    yield {"type": "reasoning", "delta": buffer[emitted:safe]}
                    emitted = safe
    except Exception as exc:  # noqa: BLE001 - surfaced as a fallback trigger
        raise LLMRoomAgentError(f"room stream failed: {exc}") from exc

    cut = buffer.find(_PATCH_SENTINEL)
    if cut < 0:
        cut = buffer.find("{")
    reasoning_text = buffer[:cut].replace(_PATCH_SENTINEL, "").strip()[:600] if cut > 0 else ""
    patch = _parse_room_patch(_extract_json(buffer))
    if reasoning_text:
        patch.reasoning = reasoning_text
    yield {"type": "patch", "patch": patch}


def _response_content(response: _LLMResponse | str) -> str:
    if isinstance(response, str):
        return response
    return str(response.content)


def _parse_room_patch(content: str) -> RoomPatch:
    raw = _extract_json(content)
    try:
        return RoomPatch.model_validate_json(raw)
    except ValidationError as exc:
        raise LLMRoomAgentError(f"RoomPatch schema validation failed: {exc}") from exc


def _extract_json(content: str) -> str:
    text = content.strip()
    if "```json" in text:
        start = text.index("```json") + len("```json")
        end = text.index("```", start)
        return text[start:end].strip()
    if "```" in text:
        start = text.index("```") + len("```")
        end = text.index("```", start)
        return text[start:end].strip()
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        return text[first : last + 1]
    raise LLMRoomAgentError("LLM output did not contain a JSON object")


def _build_prompt_payload(room: dict) -> dict:
    return {
        "task": "Generate the next visible RoomPatch. Do not generate RoomState or PlanCanvasState.",
        "scenario": room.get("scenario", "friends"),
        "stage": room.get("stage", "idle"),
        "stage_title": room.get("stage_title", ""),
        "demo_step_index": room.get("demo_step_index", 0),
        "personas": _personas(room),
        "recent_messages": _recent_messages(room),
        "group_memory": room.get("group_memory", {}),
        "available_plans": _available_plans(room),
        "available_venue_ids": _available_venue_ids(room),
        "rules": [
            "每次最多 1 条 Agent 消息 + 0 到 2 条成员消息。",
            "消息必须短，像真实聊天，不要像后台日志。",
            "不要使用规则推断、状态机、来源校验、debug 等技术词。",
            "不要编造地点、坐标、确认码、真实下单或真实订座。",
            "plan_copy_updates 只能改方案文案，不改地点事实。",
            "如果偏好足够，next_phase_hint 可以是 ready_to_plan。",
        ],
        "schema_summary": _SCHEMA_SUMMARY,
    }


def _personas(room: dict) -> list[dict]:
    return [
        {
            "id": participant.get("id"),
            "name": participant.get("name"),
            "role": participant.get("role"),
            "likes": participant.get("preference_profile", {}).get("likes", []),
            "food_exclusions": participant.get("preference_profile", {}).get("food_exclusions", []),
            "vibe": participant.get("preference_profile", {}).get("vibe", ""),
        }
        for participant in room.get("participants", [])
        if participant.get("role") != "profile"
    ]


def _recent_messages(room: dict) -> list[dict]:
    return [
        {
            "speaker_id": message.get("actor_id"),
            "speaker_name": message.get("actor_name"),
            "text": message.get("content", ""),
        }
        for message in room.get("messages", [])[-10:]
    ]


def _available_plans(room: dict) -> list[dict]:
    return [
        {
            "plan_id": option.get("option_id"),
            "label": option.get("label"),
            "positioning": option.get("positioning"),
            "scores": option.get("score", {}),
            "timeline": [
                {
                    "venue_id": marker.get("id"),
                    "name": marker.get("display_name"),
                    "category": marker.get("category_label"),
                }
                for marker in option.get("plan_canvas", {}).get("map", {}).get("markers", [])
            ],
        }
        for option in room.get("plan_options", [])
    ]


def _available_venue_ids(room: dict) -> list[str]:
    venue_ids = set()
    for option in room.get("plan_options", []):
        for item in option.get("plan_canvas", {}).get("timeline", []):
            venue_ids.add(str(item.get("map_marker_id", "")))
        for marker in option.get("plan_canvas", {}).get("map", {}).get("markers", []):
            venue_ids.add(str(marker.get("id", "")))
    if not venue_ids:
        if room.get("scenario") == "family":
            venue_ids.update(
                [
                    "venue_family_science",
                    "venue_family_play",
                    "venue_family_light_dinner",
                    "venue_picture_book",
                    "venue_family_indoor",
                ]
            )
        else:
            venue_ids.update(
                [
                    "venue_art",
                    "venue_hotpot",
                    "venue_light_dinner",
                    "venue_coffee",
                    "venue_boardgame",
                    "venue_mall_dinner",
                ]
            )
    return sorted(item for item in venue_ids if item)


_SCHEMA_SUMMARY = {
    "next_phase_hint": "continue_chat|ready_to_plan|voting|consensus|final_ready|revise_plan",
    "reasoning": (
        "你做出这一步决定的真实推理：先看每个人的硬约束，再找冲突，再决定取舍。"
        "简体中文，分 2-4 个短句或要点，80-200 字，像在心里推演，不是说给用户听的话。"
    ),
    "messages": [
        {
            "speaker_id": "agent|red|green|blue|pink|wife",
            "message_type": "chat|agent_summary|compact_plan_notice",
            "text": "1-180 chars",
        }
    ],
    "memory_delta": {
        "constraints": ["short strings"],
        "preferences": ["short strings"],
        "conflicts": ["short strings"],
        "decisions": ["short strings"],
    },
    "plan_copy_updates": {
        "plan_a": {
            "title": "short title",
            "positioning": "short positioning",
            "fit_for": ["short strings"],
            "risks": ["short strings"],
            "reason": "short reason",
        }
    },
    "venue_signals": [
        {
            "participant_id": "red|green|blue|pink|wife|agent",
            "venue_id": "trusted venue id only",
            "reaction_type": "like|neutral|veto|too_far|too_noisy|too_expensive|food_exclusion",
            "reason": "short reason",
        }
    ],
    "consensus": {
        "proposed_active_plan_id": "plan_a|plan_b|plan_c|null",
        "consensus_summary": "short explanation",
        "minority_concerns": ["short strings"],
    },
    "final_copy": {
        "final_summary": "short final summary",
        "share_text": "share message",
        "execution_notes": ["short strings"],
    },
}

_SYSTEM_PROMPT = """你是美团多人周末规划房间里的协作 Agent。

你只能输出严格 JSON，符合给定 RoomPatch schema。
你不能接管系统状态，不能生成 RoomState，不能生成 PlanCanvasState。
你不能编造地点、坐标、确认码、真实支付、真实下单或真实订座。
你只能基于提供的成员、plan_id、venue_id、当前阶段和现有对话，生成下一批可见消息、偏好增量、方案文案、共识解释或分享文案。
语气要像真实 AI 助手和真实成员聊天，不要像后台日志。

reasoning 字段：写出你这一步真实的思考过程（先看每个人的硬约束 → 找出冲突 → 决定取舍 → 得到结论），\
简体中文，2-4 个短句或要点，像在心里推演，不是说给用户听的话。\
messages 仍然是给用户看的对话，不要把推理塞进 messages。
"""

_REPAIR_PROMPT = """你正在修复一个 RoomPatch JSON 输出。
只输出严格 JSON，不要解释。
不要新增 schema 之外的字段。
如果缺信息，用空数组、空对象或 null。
"""

_STREAM_SYSTEM_PROMPT = (
    _SYSTEM_PROMPT
    + """
【输出格式 - 必须严格遵守，分三部分】
1) 先输出你这一步真实的思考过程：纯中文文本，2-4 个短句，\
顺序是「先看每个人的硬约束 → 找出冲突 → 决定取舍 → 得到结论」，\
像在心里推演，不是说给用户听的话。
2) 然后单独一行输出分隔符：===PATCH===
3) 然后输出严格 JSON 的 RoomPatch（messages 才是给用户看的对话）。JSON 里不需要再写 reasoning 字段。
"""
)
