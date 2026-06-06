"use client";

import { cn } from "@/lib/utils";
import type { Participant, ParticipantId } from "@/lib/types";

interface ParticipantAvatarProps {
  participant?: Participant;
  participantId?: ParticipantId;
  size?: "sm" | "md";
}

const PARTICIPANT_LABELS: Record<ParticipantId, string> = {
  red: "红",
  green: "绿",
  blue: "蓝",
  pink: "粉",
  agent: "AI",
};

function avatarColor(id: ParticipantId | undefined) {
  switch (id) {
    case "red":
      return "bg-red-500 text-white";
    case "green":
      return "bg-green-500 text-white";
    case "blue":
      return "bg-blue-500 text-white";
    case "pink":
      return "bg-pink-500 text-white";
    case "agent":
      return "bg-zinc-900 text-white";
    default:
      return "bg-zinc-200 text-zinc-700";
  }
}

export function ParticipantAvatar({ participant, participantId, size = "md" }: ParticipantAvatarProps) {
  const id = participant?.id ?? participantId;
  const label = participant?.avatar ?? (id ? PARTICIPANT_LABELS[id] : "?");

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold",
        size === "sm" ? "h-6 w-6 text-[10px]" : "h-8 w-8 text-xs",
        avatarColor(id)
      )}
      title={participant?.name ?? id}
    >
      {label}
    </span>
  );
}
