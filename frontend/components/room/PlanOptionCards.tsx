"use client";

import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ParticipantAvatar } from "./ParticipantAvatar";
import type { PlanOption, ParticipantId } from "@/lib/types";

interface PlanOptionCardsProps {
  options: PlanOption[];
  activePlanId: string | null;
  activeUserId: ParticipantId;
  onSelectPlan: (planId: string) => void;
  onVote: (planId: string) => void;
}

export function PlanOptionCards({
  options,
  activePlanId,
  activeUserId,
  onSelectPlan,
  onVote,
}: PlanOptionCardsProps) {
  if (options.length === 0) return null;

  return (
    <section className="grid gap-3 xl:grid-cols-3">
      {options.map((option) => {
        const active = option.option_id === activePlanId;
        const hasVoted = option.vote_summary.supporters.includes(activeUserId);
        return (
          <article
            key={option.option_id}
            className={cn(
              "rounded-lg border bg-white p-4 shadow-sm shadow-zinc-100",
              active ? "border-orange-300" : "border-zinc-100"
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-zinc-900">{option.label}</div>
                <p className="mt-1 text-xs leading-5 text-zinc-500">{option.positioning}</p>
              </div>
              {active && <CheckCircle2 className="h-4 w-4 text-green-600" />}
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <Score label="共识" value={option.score.consensus} />
              <Score label="距离" value={option.score.distance} />
              <Score label="室内" value={option.score.indoor} />
              <Score label="拍照" value={option.score.photo} />
            </div>

            <div className="mt-3 flex items-center justify-between">
              <div className="flex gap-1">
                {option.vote_summary.supporters.map((id) => (
                  <ParticipantAvatar key={id} participantId={id} size="sm" />
                ))}
              </div>
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => onSelectPlan(option.option_id)}>
                  查看
                </Button>
                <Button type="button" size="sm" disabled={hasVoted} onClick={() => onVote(option.option_id)}>
                  {hasVoted ? "已投" : "投票"}
                </Button>
              </div>
            </div>

            {option.vote_summary.concerns.length > 0 && (
              <div className="mt-3 text-xs leading-5 text-amber-700">
                {option.vote_summary.concerns.join(" / ")}
              </div>
            )}
          </article>
        );
      })}
    </section>
  );
}

function Score({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex items-center justify-between text-zinc-500">
        <span>{label}</span>
        <span>{value}</span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-zinc-100">
        <div className={cn("h-1.5 rounded-full bg-orange-500", scoreWidthClass(value))} />
      </div>
    </div>
  );
}

function scoreWidthClass(value: number) {
  if (value >= 92) return "w-11/12";
  if (value >= 84) return "w-10/12";
  if (value >= 76) return "w-9/12";
  if (value >= 68) return "w-8/12";
  return "w-7/12";
}
