"""Domain entities for activity planning."""

from typing import Literal

from pydantic import BaseModel, Field


class Venue(BaseModel):
    """A point of interest (restaurant, attraction, activity)."""

    id: str
    name: str
    address: str
    coords: tuple[float, float]  # (lng, lat) GCJ-02
    category: str
    rating: float | None = None
    distance_meters: int | None = None
    tel: str | None = None
    business_area: str | None = None


class Activity(BaseModel):
    """A single activity in the plan."""

    order: int
    type: Literal["play", "eat", "extra"]
    venue_name: str
    venue_address: str
    venue_coords: tuple[float, float]
    start_time: str  # "14:00"
    duration_minutes: int
    travel_to_next_minutes: int | None = None
    action: Literal["book", "reserve", "order_delivery", "no_action"]
    action_details: dict = Field(default_factory=dict)
    reason: str  # Why this venue fits the constraints


class Plan(BaseModel):
    """A complete activity plan."""

    title: str  # "周六下午亲子时光"
    duration_hours: float
    activities: list[Activity]
    total_travel_minutes: int
    share_text: str  # "搞定了，下午2点出发，先去……"
