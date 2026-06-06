"""Validated patch contract for the hybrid agentic collaborative room."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PatchSpeakerId = Literal["agent", "red", "green", "blue", "pink", "wife"]
PatchMessageKind = Literal["chat", "agent_summary", "compact_plan_notice"]
PatchPhaseHint = Literal["continue_chat", "ready_to_plan", "voting", "consensus", "final_ready", "revise_plan"]
PatchPlanId = Literal["plan_a", "plan_b", "plan_c"]
PatchReactionType = Literal["like", "neutral", "veto", "too_far", "too_noisy", "too_expensive", "food_exclusion"]


class StrictPatchModel(BaseModel):
    """Base model that rejects schema drift from LLM output."""

    model_config = ConfigDict(extra="forbid")


class MessageDraft(StrictPatchModel):
    """Short message suggested by the LLM for the next visible room event."""

    speaker_id: PatchSpeakerId
    message_type: PatchMessageKind = "chat"
    text: str = Field(min_length=1, max_length=180)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.strip().split())


class MemoryDelta(StrictPatchModel):
    """Small incremental update to group memory."""

    constraints: list[str] = Field(default_factory=list, max_length=6)
    preferences: list[str] = Field(default_factory=list, max_length=6)
    conflicts: list[str] = Field(default_factory=list, max_length=4)
    decisions: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("constraints", "preferences", "conflicts", "decisions")
    @classmethod
    def clean_items(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            text = " ".join(str(item).strip().split())
            if text:
                cleaned.append(text[:80])
        return cleaned


class PlanCopyUpdate(StrictPatchModel):
    """LLM-owned copy updates only; venue facts and canvas data remain backend-owned."""

    title: str = Field(default="", max_length=16)
    positioning: str = Field(default="", max_length=80)
    fit_for: list[str] = Field(default_factory=list, max_length=4)
    risks: list[str] = Field(default_factory=list, max_length=3)
    reason: str = Field(default="", max_length=140)

    @field_validator("title", "positioning", "reason")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("fit_for", "risks")
    @classmethod
    def clean_list(cls, value: list[str]) -> list[str]:
        return [" ".join(str(item).strip().split())[:60] for item in value if str(item).strip()]


class ConsensusPatch(StrictPatchModel):
    """LLM explanation for backend-computed or backend-validated consensus."""

    proposed_active_plan_id: PatchPlanId | None = None
    consensus_summary: str | None = Field(default=None, max_length=180)
    minority_concerns: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("consensus_summary")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split()) or None

    @field_validator("minority_concerns")
    @classmethod
    def clean_concerns(cls, value: list[str]) -> list[str]:
        return [" ".join(str(item).strip().split())[:80] for item in value if str(item).strip()]


class VenueSignalDraft(StrictPatchModel):
    """Optional venue-level signal suggested by the LLM using trusted venue ids."""

    participant_id: PatchSpeakerId
    venue_id: str = Field(min_length=1, max_length=64)
    reaction_type: PatchReactionType = "like"
    reason: str = Field(default="", max_length=80)

    @field_validator("venue_id", "reason")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.strip().split())


class FinalCopyPatch(StrictPatchModel):
    """Final arrangement copy only. Mock execution still belongs to backend rules."""

    final_summary: str | None = Field(default=None, max_length=220)
    share_text: str | None = Field(default=None, max_length=280)
    execution_notes: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("final_summary", "share_text")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split()) or None

    @field_validator("execution_notes")
    @classmethod
    def clean_notes(cls, value: list[str]) -> list[str]:
        return [" ".join(str(item).strip().split())[:80] for item in value if str(item).strip()]


class RoomPatch(StrictPatchModel):
    """The only LLM-owned output accepted by the collaborative room."""

    next_phase_hint: PatchPhaseHint = "continue_chat"
    reasoning: str = Field(default="")
    messages: list[MessageDraft] = Field(default_factory=list, max_length=3)
    memory_delta: MemoryDelta = Field(default_factory=MemoryDelta)
    plan_copy_updates: dict[PatchPlanId, PlanCopyUpdate] = Field(default_factory=dict)
    venue_signals: list[VenueSignalDraft] = Field(default_factory=list, max_length=4)
    consensus: ConsensusPatch | None = None
    final_copy: FinalCopyPatch | None = None

    @field_validator("reasoning")
    @classmethod
    def clean_reasoning(cls, value: str) -> str:
        # The model's genuine step reasoning. Truncate (don't reject) so an
        # over-long thought never fails validation and forces a scripted fallback.
        return value.strip()[:600]
