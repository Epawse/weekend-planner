"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ParticipantAvatar } from "./ParticipantAvatar";
import type { CanvasTimelineItem, ParticipantId, Reaction, RoomReactionType } from "@/lib/types";

interface VenueReactionBarProps {
  timeline: CanvasTimelineItem[];
  reactions: Reaction[];
  onReact: (venueId: string, reactionType: RoomReactionType, reason: string) => void;
}

export function VenueReactionBar({ timeline, reactions, onReact }: VenueReactionBarProps) {
  if (timeline.length === 0) return null;

  return (
    <section className="rounded-lg border border-zinc-100 bg-white p-4 shadow-sm shadow-zinc-100">
      <div className="mb-3 text-sm font-semibold text-zinc-900">地点反应</div>
      <div className="space-y-2">
        {timeline.map((item) => {
          const venueId = venueIdFromTimeline(item);
          const venueReactions = reactions.filter((reaction) => reaction.target_id === venueId);
          return (
            <div key={item.id} className="rounded-lg bg-zinc-50 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-zinc-900">{item.display_name}</div>
                  <div className="mt-0.5 text-xs text-zinc-500">{item.category_label}</div>
                </div>
                <div className="flex gap-1">
                  {venueReactions.map((reaction) => (
                    <ParticipantAvatar
                      key={`${reaction.participant_id}_${reaction.reaction_type}`}
                      participantId={reaction.participant_id as ParticipantId}
                      size="sm"
                    />
                  ))}
                </div>
              </div>
              {venueReactions.length > 0 && (
                <div className="mt-2 space-y-1 text-xs text-zinc-600">
                  {venueReactions.map((reaction) => (
                    <div key={`${reaction.participant_id}_${reaction.reason}`}>
                      {reaction.label} · {reaction.reason}
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => onReact(venueId, "like", "想去")}>
                  <ThumbsUp className="mr-1 h-3.5 w-3.5" />
                  想去
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => onReact(venueId, "food_exclusion", "不吃这个")}
                >
                  <ThumbsDown className="mr-1 h-3.5 w-3.5" />
                  不吃这个
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => onReact(venueId, "too_far", "太远")}>
                  太远
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function venueIdFromTimeline(item: CanvasTimelineItem) {
  if (item.display_name.includes("绘本")) return "venue_picture_book";
  if (item.display_name.includes("低脂") || item.display_name.includes("家庭餐厅")) return "venue_family_light_dinner";
  if (item.display_name.includes("亲子") || item.display_name.includes("科学馆") || item.display_name.includes("乐园")) {
    return "venue_family_play";
  }
  if (item.display_name.includes("火锅")) return "venue_hotpot";
  if (item.display_name.includes("咖啡")) return "venue_coffee";
  if (item.display_name.includes("桌游")) return "venue_boardgame";
  if (item.display_name.includes("餐厅")) return "venue_light_dinner";
  return "venue_art";
}
