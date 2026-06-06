"""Pydantic request/response schemas for API endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class PlanCreateRequest(BaseModel):
    """Request body for POST /api/plan/create."""

    message: str = Field(..., description="User's natural language input")
    scenario: Literal["family", "friends"] = Field(default="family", description="family or friends")
    home_location: list[float] = Field(
        default=[116.481, 39.998],
        description="[lng, lat] in GCJ-02",
    )
    scenario_description: str = Field(
        default="",
        description="Additional context about the scenario",
    )


class PlanApproveRequest(BaseModel):
    """Request body for POST /api/plan/approve."""

    session_id: str = Field(..., description="Thread ID for graph resumption")
    approved: bool = Field(..., description="Whether user approves the plan")
    modifications: dict | None = Field(default=None, description="Optional modification hints")


class PlanFeedbackRequest(BaseModel):
    """Request body for POST /api/plan/feedback."""

    session_id: str = Field(..., description="Thread ID for current interrupted graph")
    message: str = Field(..., description="User feedback text")
    quick_action: str | None = Field(default=None, description="Optional quick action label")


class RoomMessageRequest(BaseModel):
    """Request body for POST /api/room/{room_id}/message."""

    actor_id: str = Field(default="red", description="Participant id")
    content: str = Field(..., description="Message content")


class RoomVoteRequest(BaseModel):
    """Request body for POST /api/room/{room_id}/vote."""

    participant_id: str = Field(default="red", description="Participant id")
    plan_id: str = Field(..., description="Target plan option id")
    reason: str = Field(default="", description="Optional vote reason")


class RoomReactionRequest(BaseModel):
    """Request body for POST /api/room/{room_id}/reaction."""

    participant_id: str = Field(default="red", description="Participant id")
    venue_id: str = Field(..., description="Target venue id")
    reaction_type: str = Field(default="like", description="Reaction type")
    reason: str = Field(default="", description="Optional reaction reason")


class RoomExecuteRequest(BaseModel):
    """Request body for POST /api/room/{room_id}/execute."""

    actor_id: str = Field(default="red", description="Participant id")


class RoomScenarioRequest(BaseModel):
    """Request body for switching a collaborative room scenario."""

    scenario: Literal["family", "friends"] = Field(default="friends", description="Target room scenario")
    actor_id: str = Field(default="red", description="Participant id")


class HealthResponse(BaseModel):
    """Response for GET /api/health."""

    status: str = "ok"
    providers: dict[str, bool] = Field(default_factory=dict)


class PlanEvent(BaseModel):
    """SSE event payload sent to frontend."""

    type: str  # thinking, tool_calling, tool_result, plan_generated, step_start, step_complete, error, done
    data: dict = Field(default_factory=dict)
