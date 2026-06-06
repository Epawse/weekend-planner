"""User-facing Plan Canvas contract models."""

from typing import Literal

from pydantic import BaseModel, Field

CanvasScenario = Literal["family", "friends"]
CanvasStatus = Literal["plan_ready", "feedback_applied", "executing", "done"]
CanvasCheckStatus = Literal["pass", "warn", "fail"]
CanvasActionStatus = Literal["pending", "running", "done", "failed", "skipped"]


class CanvasMetrics(BaseModel):
    """Top-line metrics displayed in the Plan Canvas."""

    total_duration_text: str
    travel_time_text: str
    end_time_text: str
    fit_label: str
    route_label: str


class CanvasTimelineItem(BaseModel):
    """A single user-visible timeline step."""

    id: str
    step: int
    time: str
    end_time: str
    duration_text: str
    display_name: str
    category_label: str
    user_description: str
    address: str
    map_marker_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class CanvasCheck(BaseModel):
    """Scenario quality check shown to the user."""

    id: str
    label: str
    detail: str
    status: CanvasCheckStatus


class CanvasChecks(BaseModel):
    """Checks grouped by visible status."""

    passed: list[CanvasCheck] = Field(default_factory=list)
    warnings: list[CanvasCheck] = Field(default_factory=list)
    failed: list[CanvasCheck] = Field(default_factory=list)


class EvidenceCard(BaseModel):
    """User-facing evidence card with scrubbed source labels."""

    id: str
    title: str
    source_label: str
    subject: str
    detail: str
    related_timeline_ids: list[str] = Field(default_factory=list)
    related_marker_ids: list[str] = Field(default_factory=list)


class RejectedCanvasOption(BaseModel):
    """A user-facing rejected option."""

    id: str
    name: str
    reason: str
    source_label: str


class CanvasMapMarker(BaseModel):
    """A selected plan marker used by the interactive map."""

    id: str
    timeline_item_id: str
    step: int
    type: Literal["home", "play", "eat", "extra"]
    coordinates: tuple[float, float]
    display_name: str
    category_label: str
    user_description: str
    address: str
    source_label: str
    schedule_text: str
    next_leg_text: str | None = None
    business_status: str | None = None
    actions: list[str] = Field(default_factory=list)


class CanvasMap(BaseModel):
    """Map data for selected plan display."""

    home_marker_id: str = "home"
    home_location: tuple[float, float]
    markers: list[CanvasMapMarker] = Field(default_factory=list)
    route_geojson: dict[str, object] | None = None
    route_notice: str


class FeedbackHistoryItem(BaseModel):
    """A feedback item applied to the current canvas."""

    id: str
    label: str
    user_text: str
    result_message: str


class FeedbackChangeSummary(BaseModel):
    """User-visible before/after explanation for the latest follow-up."""

    title: str
    result: str
    before: str
    after: str
    preserved: list[str] = Field(default_factory=list)
    changed: list[str] = Field(default_factory=list)
    note: str | None = None


class CanvasFeedback(BaseModel):
    """Quick feedback controls and applied history."""

    quick_actions: list[str]
    history: list[FeedbackHistoryItem] = Field(default_factory=list)
    change_summary: FeedbackChangeSummary | None = None


class ToolTask(BaseModel):
    """Local-life fan-out task status."""

    id: str
    label: str
    status: Literal["pending", "running", "done", "warn", "failed"]
    detail: str


class ExecutionAction(BaseModel):
    """Execution action before or after confirmation."""

    id: str
    label: str
    status: CanvasActionStatus
    target: str
    detail: str | None = None
    confirmation: str | None = None
    scheduled_time: str | None = None
    party_size: int | None = None
    note: str | None = None
    next_step: str | None = None


class PlanCanvasState(BaseModel):
    """Single user-facing plan state consumed by the frontend workbench."""

    canvas_id: str
    scenario: CanvasScenario
    status: CanvasStatus
    title: str
    summary: str
    metrics: CanvasMetrics
    timeline: list[CanvasTimelineItem]
    checks: CanvasChecks
    evidence_cards: list[EvidenceCard] = Field(default_factory=list)
    rejected_options: list[RejectedCanvasOption] = Field(default_factory=list)
    map: CanvasMap
    feedback: CanvasFeedback
    tool_tasks: list[ToolTask] = Field(default_factory=list)
    pending_actions: list[ExecutionAction] = Field(default_factory=list)
    execution_results: list[ExecutionAction] = Field(default_factory=list)
    share_text: str
    modification_notice: str | None = None
