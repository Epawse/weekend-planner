"use client";

import { cn, getActivityTypeLabel, getActivityTypeColor, formatDuration } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { MapPin, Clock, Car } from "lucide-react";
import type { Activity } from "@/lib/types";

interface VenueCardProps {
  activity: Activity;
  isLast?: boolean;
}

export function VenueCard({ activity, isLast = false }: VenueCardProps) {
  return (
    <div className="relative flex gap-3">
      {/* Timeline dot and line */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold",
            activity.type === "play" && "border-green-400 bg-green-50 text-green-700",
            activity.type === "eat" && "border-orange-400 bg-orange-50 text-orange-700",
            activity.type === "extra" && "border-purple-400 bg-purple-50 text-purple-700"
          )}
        >
          {activity.order}
        </div>
        {!isLast && (
          <div className="w-0.5 flex-1 bg-zinc-200" />
        )}
      </div>

      {/* Content */}
      <div className={cn("flex-1 pb-6", isLast && "pb-0")}>
        <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h4 className="font-semibold text-zinc-900">{activity.venue_name}</h4>
                <Badge className={getActivityTypeColor(activity.type)} variant="outline">
                  {getActivityTypeLabel(activity.type)}
                </Badge>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-zinc-500">
                <span className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  {activity.start_time} · {formatDuration(activity.duration_minutes)}
                </span>
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {activity.venue_address}
                </span>
              </div>

              <p className="mt-2 text-sm text-zinc-600">{activity.reason}</p>
            </div>
          </div>

          {/* Travel to next */}
          {activity.travel_to_next_minutes != null && !isLast && (
            <div className="mt-3 flex items-center gap-1.5 rounded-md bg-zinc-50 px-2.5 py-1.5 text-xs text-zinc-500">
              <Car className="h-3.5 w-3.5" />
              <span>到下一站约 {activity.travel_to_next_minutes} 分钟</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
