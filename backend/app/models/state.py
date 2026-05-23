"""LangGraph state definitions using TypedDict."""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class PlannerState(TypedDict):
    """Main state schema for the activity planning graph."""

    # Input
    user_input: str
    scenario: Literal["family", "friends"]
    home_location: tuple[float, float]  # GCJ-02 (lng, lat)
    scenario_description: str  # e.g. "孩子5岁，老婆最近在减肥"

    # GIS Analysis
    isochrone: dict | None  # GeoJSON Polygon from OpenRouteService
    candidate_venues: list[dict]  # POI results filtered by isochrone
    weather: dict | None  # Real-time weather data
    optimized_route: dict | None  # Route GeoJSON

    # Planning
    messages: Annotated[list[BaseMessage], add_messages]
    plan: dict | None  # Structured plan output
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

    # Error handling
    error: str | None
    retry_count: int
    fallback_venues: list[dict]
