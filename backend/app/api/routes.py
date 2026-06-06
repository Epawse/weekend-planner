"""FastAPI API endpoints with SSE streaming."""

import json
import uuid
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from app.agents.orchestrator import planning_graph
from app.config import settings
from app.models.schemas import (
    HealthResponse,
    PlanApproveRequest,
    PlanCreateRequest,
    PlanFeedbackRequest,
    RoomExecuteRequest,
    RoomMessageRequest,
    RoomReactionRequest,
    RoomScenarioRequest,
    RoomVoteRequest,
)
from app.services.feedback import apply_feedback_to_state
from app.services.room import (
    add_reaction,
    add_room_message,
    add_room_message_stream,
    add_vote,
    advance_room_agentic,
    advance_room_agentic_stream,
    execute_room,
    get_room,
    reset_room,
    set_room_scenario,
    simulate_room,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint showing provider availability."""
    providers = {
        "qwen": bool(settings.dashscope_api_key),
        "deepseek": bool(settings.deepseek_api_key),
        "gemini": bool(settings.gemini_api_key),
        "openai": bool(settings.openai_api_key),
    }
    return HealthResponse(status="ok", providers=providers)


@router.post("/plan/create")
async def create_plan(request: PlanCreateRequest):
    """Start the planning graph and stream progress events via SSE.

    Creates a new session, invokes the LangGraph planning graph,
    and streams all progress/tool/plan events to the client.
    """
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    initial_state = {
        "user_input": request.message,
        "scenario": request.scenario,
        "home_location": list(request.home_location),
        "scenario_description": request.scenario_description,
        "family_profile": None,
        "family_strategy": None,
        "isochrone": None,
        "candidate_venues": [],
        "weather": None,
        "optimized_route": None,
        "candidate_plans": [],
        "family_checks": [],
        "fatigue_score": None,
        "evidence": [],
        "alternatives": [],
        "rejected_options": [],
        "messages": [],
        "plan": None,
        "plan_status": "idle",
        "current_step": 0,
        "execution_results": [],
        "feedback_history": [],
        "feedback_constraints": {},
        "feedback_change_summary": None,
        "error": None,
        "retry_count": 0,
        "fallback_venues": [],
        "plan_canvas": None,
    }

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Stream LangGraph execution events as SSE."""
        # Send session_id first so client can use it for approve/modify
        yield {
            "event": "session",
            "data": json.dumps({"session_id": session_id}),
        }

        try:
            async for chunk in planning_graph.astream(
                initial_state,
                config=config,
                stream_mode=["updates", "custom"],
                version="v2",
            ):
                chunk_type = chunk.get("type") if isinstance(chunk, dict) else None
                if chunk_type == "custom":
                    payload = chunk.get("data", {})
                    yield {
                        "event": payload.get("type", "progress") if isinstance(payload, dict) else "progress",
                        "data": json.dumps(payload, ensure_ascii=False, default=str),
                    }
                elif chunk_type == "updates":
                    payload = chunk.get("data", {})
                    if isinstance(payload, dict):
                        for node_name, state_update in payload.items():
                            plan_status = state_update.get("plan_status") if isinstance(state_update, dict) else None
                            yield {
                                "event": "node_complete",
                                "data": json.dumps(
                                    {"node": node_name, "plan_status": plan_status},
                                    ensure_ascii=False,
                                ),
                            }

            # Check if graph is interrupted (waiting for approval)
            try:
                snapshot = await planning_graph.aget_state(config)
                if snapshot.next:
                    yield {
                        "event": "interrupted",
                        "data": json.dumps({"session_id": session_id, "awaiting": "approval"}),
                    }
                else:
                    yield {
                        "event": "done",
                        "data": json.dumps({"message": "Planning complete"}),
                    }
            except Exception as e:
                logger.warning("snapshot_check_failed", error=str(e))
                yield {
                    "event": "interrupted",
                    "data": json.dumps({"session_id": session_id, "awaiting": "approval"}),
                }

        except Exception as e:
            logger.error("plan_stream_error", error=str(e))
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e), "recoverable": False}, ensure_ascii=False),
            }

    return EventSourceResponse(
        event_generator(),
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache, no-transform",
        },
    )


@router.post("/plan/feedback")
async def feedback_plan(request: PlanFeedbackRequest):
    """Apply follow-up feedback to the current interrupted plan."""
    config = {"configurable": {"thread_id": request.session_id}}
    snapshot = await planning_graph.aget_state(config)
    state = dict(snapshot.values or {})

    if not state.get("plan"):
        raise HTTPException(status_code=400, detail="No current plan to modify for this session")

    try:
        update = apply_feedback_to_state(
            state,
            message=request.message,
            quick_action=request.quick_action,
            session_id=request.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await planning_graph.aupdate_state(config, update)

    return {
        "session_id": request.session_id,
        "message": update["feedback_message"],
        "plan": update["plan"],
        "plan_canvas": update["plan_canvas"],
    }


@router.post("/plan/approve")
async def approve_plan(request: PlanApproveRequest):
    """Resume the planning graph after user approval/rejection.

    Sends Command(resume=True/False) to the interrupted graph,
    then streams execution progress events.
    """
    config = {"configurable": {"thread_id": request.session_id}}

    # Verify the graph is actually paused
    snapshot = await planning_graph.aget_state(config)
    if not snapshot.next:
        raise HTTPException(status_code=400, detail="No pending plan to approve for this session")

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Stream execution events after approval."""
        try:
            async for chunk in planning_graph.astream(
                Command(resume=request.approved),
                config=config,
                stream_mode=["updates", "custom"],
                version="v2",
            ):
                chunk_type = chunk.get("type") if isinstance(chunk, dict) else None
                if chunk_type == "custom":
                    payload = chunk.get("data", {})
                    yield {
                        "event": payload.get("type", "progress") if isinstance(payload, dict) else "progress",
                        "data": json.dumps(payload, ensure_ascii=False, default=str),
                    }
                elif chunk_type == "updates":
                    payload = chunk.get("data", {})
                    if isinstance(payload, dict):
                        for node_name, state_update in payload.items():
                            plan_status = state_update.get("plan_status") if isinstance(state_update, dict) else None
                            yield {
                                "event": "node_complete",
                                "data": json.dumps(
                                    {"node": node_name, "plan_status": plan_status},
                                    ensure_ascii=False,
                                ),
                            }

            yield {
                "event": "done",
                "data": json.dumps({"message": "Execution complete"}),
            }

        except Exception as e:
            logger.error("approve_stream_error", error=str(e), session_id=request.session_id)
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e), "recoverable": False}, ensure_ascii=False),
            }

    return EventSourceResponse(
        event_generator(),
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache, no-transform",
        },
    )


@router.get("/room/{room_id}")
async def get_collaboration_room(room_id: str, user: str = "red"):
    """Return the deterministic collaborative demo room."""
    return get_room(room_id, active_user_id=user)


@router.post("/room/{room_id}/reset")
async def reset_collaboration_room(room_id: str, user: str = "red", scenario: str | None = None):
    """Reset the collaborative demo room to its baseline state."""
    return reset_room(room_id, active_user_id=user, scenario=scenario)


@router.post("/room/{room_id}/scenario")
async def switch_collaboration_room_scenario(room_id: str, request: RoomScenarioRequest):
    """Switch the collaborative room scenario and reset to idle."""
    return set_room_scenario(room_id, scenario=request.scenario, active_user_id=request.actor_id)


@router.post("/room/{room_id}/message")
async def post_room_message(room_id: str, request: RoomMessageRequest):
    """Add a participant message and update group memory."""
    return add_room_message(room_id, actor_id=request.actor_id, content=request.content)


@router.post("/room/{room_id}/message/stream")
async def post_room_message_stream(room_id: str, request: RoomMessageRequest):
    """Add a participant message while streaming the agent's reasoning via SSE.

    Commits the user message first, emits ``reasoning`` events (incremental
    rationale), then a single ``done`` event carrying the full updated room state.
    """

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            async for event in add_room_message_stream(room_id, actor_id=request.actor_id, content=request.content):
                if event["type"] == "reasoning":
                    yield {
                        "event": "reasoning",
                        "data": json.dumps({"delta": event["delta"]}, ensure_ascii=False),
                    }
                elif event["type"] == "done":
                    yield {
                        "event": "done",
                        "data": json.dumps({"room": event["room"]}, ensure_ascii=False, default=str),
                    }
        except Exception as e:  # noqa: BLE001 - surface as an SSE error event
            logger.error("room_message_stream_error", error=str(e), room_id=room_id)
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(
        event_generator(),
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache, no-transform"},
    )


@router.post("/room/{room_id}/vote")
async def post_room_vote(room_id: str, request: RoomVoteRequest):
    """Record a participant plan vote."""
    return add_vote(room_id, participant_id=request.participant_id, plan_id=request.plan_id, reason=request.reason)


@router.post("/room/{room_id}/reaction")
async def post_room_reaction(room_id: str, request: RoomReactionRequest):
    """Record a venue-level reaction."""
    return add_reaction(
        room_id,
        participant_id=request.participant_id,
        venue_id=request.venue_id,
        reaction_type=request.reaction_type,
        reason=request.reason,
    )


@router.post("/room/{room_id}/advance")
async def post_room_advance(room_id: str, user: str = "red", mode: str = "auto"):
    """Advance the collaborative room by one visible event."""
    return await advance_room_agentic(room_id, active_user_id=user, agent_mode=mode)


@router.post("/room/{room_id}/advance/stream")
async def post_room_advance_stream(room_id: str, user: str = "red", mode: str = "auto"):
    """Advance the room while streaming the agent's visible reasoning via SSE.

    Emits ``reasoning`` events (incremental rationale) followed by a single
    ``done`` event carrying the full updated room state.
    """

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            async for event in advance_room_agentic_stream(room_id, active_user_id=user, agent_mode=mode):
                if event["type"] == "reasoning":
                    yield {
                        "event": "reasoning",
                        "data": json.dumps({"delta": event["delta"]}, ensure_ascii=False),
                    }
                elif event["type"] == "done":
                    yield {
                        "event": "done",
                        "data": json.dumps({"room": event["room"]}, ensure_ascii=False, default=str),
                    }
        except Exception as e:  # noqa: BLE001 - surface as an SSE error event
            logger.error("room_advance_stream_error", error=str(e), room_id=room_id)
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(
        event_generator(),
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache, no-transform"},
    )


@router.post("/room/{room_id}/simulate")
async def post_room_simulation(room_id: str, user: str = "red", scenario: str | None = None):
    """Apply the stable collaborative demo script."""
    return simulate_room(room_id, active_user_id=user, scenario=scenario)


@router.post("/room/{room_id}/execute")
async def post_room_execute(room_id: str, request: RoomExecuteRequest):
    """Execute the active collaborative plan if the host confirms."""
    return execute_room(room_id, actor_id=request.actor_id)
