"use client";

import { VenueCard } from "./VenueCard";
import type { Activity } from "@/lib/types";

interface TimelineViewProps {
  activities: Activity[];
}

export function TimelineView({ activities }: TimelineViewProps) {
  if (activities.length === 0) return null;

  const sorted = [...activities].sort((a, b) => a.order - b.order);

  return (
    <div className="space-y-0">
      {sorted.map((activity, index) => (
        <VenueCard
          key={`${activity.venue_name}-${activity.order}`}
          activity={activity}
          isLast={index === sorted.length - 1}
        />
      ))}
    </div>
  );
}
