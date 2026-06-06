"""LangGraph state definitions using TypedDict."""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class PlannerState(TypedDict):
    """Main state schema for the activity planning graph."""

    # Input
    user_input: str
    scenario: Literal["family", "friends"]
    home_location: list[float]  # GCJ-02 [lng, lat]
    scenario_description: str  # e.g. "孩子5岁，老婆最近在减肥"
    family_profile: dict | None
    family_strategy: dict | None
    friend_profile: dict | None
    friend_strategy: dict | None

    # GIS Analysis
    isochrone: dict | None  # GeoJSON Polygon from OpenRouteService
    candidate_venues: list[dict]  # POI results filtered by isochrone
    weather: dict | None  # Real-time weather data
    optimized_route: dict | None  # Route GeoJSON
    candidate_plans: list[dict]  # Spatially-validated candidate plans from SpatialAnalysisEngine
    family_checks: list[dict]
    friend_checks: list[dict]
    fatigue_score: int | None
    social_score: int | None
    evidence: list[dict]
    alternatives: list[dict]
    rejected_options: list[dict]

    # Planning
    messages: Annotated[list[BaseMessage], add_messages]
    plan: dict | None  # Structured plan output
    plan_canvas: dict | None  # User-facing Plan Canvas contract
    plan_status: Literal[
        "idle",
        "generating",
        "presented",
        "approved",
        "rejected",
        "executing",
        "completed",
        "failed",
    ]

    # Execution
    current_step: int
    execution_results: list[dict]  # Each step's booking/order result
    feedback_history: list[dict]
    feedback_constraints: dict
    feedback_change_summary: dict | None

    # Error handling
    error: str | None
    retry_count: int
    fallback_venues: list[dict]
