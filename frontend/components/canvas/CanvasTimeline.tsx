"use client";

import { MapPin } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CanvasTimelineItem } from "@/lib/types";

interface CanvasTimelineProps {
  items: CanvasTimelineItem[];
  selectedTimelineId: string | null;
  onSelectTimeline: (timelineId: string, markerId: string) => void;
}

export function CanvasTimeline({ items, selectedTimelineId, onSelectTimeline }: CanvasTimelineProps) {
  if (items.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="text-sm font-semibold text-zinc-900">计划时间线</div>
      <div className="space-y-2">
        {items.map((item) => {
          const selected = item.id === selectedTimelineId;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectTimeline(item.id, item.map_marker_id)}
              className={cn(
                "grid w-full grid-cols-[40px_1fr] gap-3 rounded-lg border bg-white p-3 text-left transition-colors",
                selected ? "border-orange-400 bg-orange-50" : "border-zinc-200 hover:border-zinc-300"
              )}
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 text-xs font-semibold text-white">
                {item.step}
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-zinc-900">{item.time}</span>
                  <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">
                    {item.category_label}
                  </span>
                  <span className="text-xs text-zinc-500">{item.duration_text}</span>
                </div>
                <div className="mt-1 text-base font-semibold text-zinc-950">{item.display_name}</div>
                <p className="mt-1 text-sm leading-5 text-zinc-600">{item.user_description}</p>
                {item.address && (
                  <div className="mt-2 flex items-center gap-1 text-xs text-zinc-500">
                    <MapPin className="h-3.5 w-3.5" />
                    <span className="truncate">{item.address}</span>
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
