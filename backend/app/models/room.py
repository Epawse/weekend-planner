"""User-facing collaborative room contract models."""

from typing import Literal

from pydantic import BaseModel, Field

ParticipantId = Literal["red", "green", "blue", "pink", "wife", "child", "agent"]
RoomScenario = Literal["friends", "family"]
RoomStage = Literal[
    "idle",
    "host_prompted",
    "agent_planning",
    "members_invited",
    "members_typing",
    "opinions_collected",
    "options_ready",
    "voting",
    "consensus_ready",
    "final_plan_ready",
    "executing",
    "done",
]
MessageType = Literal["user_message", "agent_message", "system_message"]
VoteType = Literal["support", "oppose"]
ReactionType = Literal["like", "neutral", "veto", "too_far", "too_noisy", "too_expensive", "food_exclusion"]


class ParticipantProfile(BaseModel):
    """Mock participant preference profile."""

    distance: str
    budget: str
    vibe: str
    food_exclusions: list[str] = Field(default_factory=list)
    likes: list[str] = Field(default_factory=list)


class Participant(BaseModel):
    """Mock room participant."""

    id: ParticipantId
    name: str
    color: str
    avatar: str
    role: Literal["host", "member", "profile", "agent"]
    status: Literal["online", "invited", "profile", "agent"] = "online"
    preference_profile: ParticipantProfile


class SharedMessage(BaseModel):
    """Conversation message inside a collaborative room."""

    id: str
    actor_id: ParticipantId
    actor_name: str
    actor_avatar: str
    type: MessageType
    content: str
    created_at: str
    related_plan_id: str | None = None


class Vote(BaseModel):
    """Plan-level vote."""

    participant_id: ParticipantId
    target_type: Literal["plan"] = "plan"
    target_id: str
    vote_type: VoteType = "support"
    reason: str


class Reaction(BaseModel):
    """Venue-level reaction."""

    participant_id: ParticipantId
    target_type: Literal["venue"] = "venue"
    target_id: str
    reaction_type: ReactionType
    label: str
    reason: str


class GroupConflict(BaseModel):
    """A group preference conflict and its resolution."""

    topic: str
    supporters: list[ParticipantId] = Field(default_factory=list)
    opponents: list[ParticipantId] = Field(default_factory=list)
    resolution: str


class GroupMemoryItem(BaseModel):
    """Group memory history item."""

    round: int
    summary: str


class GroupMemory(BaseModel):
    """Agent-visible summary of group intent."""

    confirmed_constraints: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    conflicts: list[GroupConflict] = Field(default_factory=list)
    history: list[GroupMemoryItem] = Field(default_factory=list)


class PlanOptionScore(BaseModel):
    """User-facing plan option score dimensions."""

    distance: int
    budget: int
    photo: int
    indoor: int
    consensus: int


class PlanOptionVoteSummary(BaseModel):
    """Vote summary for a plan option."""

    supporters: list[ParticipantId] = Field(default_factory=list)
    opponents: list[ParticipantId] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class PlanOption(BaseModel):
    """A candidate plan option wrapping PlanCanvasState."""

    option_id: str
    label: str
    positioning: str
    plan_canvas: dict
    vote_summary: PlanOptionVoteSummary
    score: PlanOptionScore
    is_recommended: bool = False


class ConsensusState(BaseModel):
    """Current consensus status."""

    required_votes: int
    current_votes: int
    status: Literal["collecting", "split", "consensus_reached"]
    active_plan_id: str
    summary: str


class RoomExecutionState(BaseModel):
    """Collaborative room execution status."""

    status: Literal["not_started", "ready", "executing", "completed"] = "not_started"
    host_can_execute: bool = True
    summary: str = ""


class RoomState(BaseModel):
    """Collaborative room state consumed by the frontend workbench."""

    room_id: str
    scenario: RoomScenario
    available_scenarios: list[RoomScenario] = Field(default_factory=lambda: ["friends", "family"])
    stage: RoomStage = "idle"
    stage_title: str = "等待发起需求"
    stage_description: str = ""
    typing_participants: list[ParticipantId] = Field(default_factory=list)
    demo_step_index: int = 0
    host_user_id: ParticipantId
    active_user_id: ParticipantId
    participants: list[Participant]
    messages: list[SharedMessage]
    group_memory: GroupMemory
    plan_options: list[PlanOption]
    active_plan_id: str
    votes: list[Vote]
    reactions: list[Reaction]
    consensus: ConsensusState
    execution_state: RoomExecutionState
