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
from app.models.schemas import HealthResponse, PlanApproveRequest, PlanCreateRequest

logger = structlog.get_logger()

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint showing provider availability."""
    providers = {
        "qwen": bool(settings.dashscope_api_key),
        "deepseek": bool(settings.deepseek_api_key),
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
        "isochrone": None,
        "candidate_venues": [],
        "weather": None,
        "optimized_route": None,
        "messages": [],
        "plan": None,
        "plan_status": "idle",
        "current_step": 0,
        "execution_results": [],
        "error": None,
        "retry_count": 0,
        "fallback_venues": [],
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
