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


class HealthResponse(BaseModel):
    """Response for GET /api/health."""

    status: str = "ok"
    providers: dict[str, bool] = Field(default_factory=dict)


class PlanEvent(BaseModel):
    """SSE event payload sent to frontend."""

    type: str  # thinking, tool_calling, tool_result, plan_generated, step_start, step_complete, error, done
    data: dict = Field(default_factory=dict)
