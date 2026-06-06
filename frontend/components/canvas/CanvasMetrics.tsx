"use client";

import { Clock, Route, ShieldCheck, Timer } from "lucide-react";
import type { CanvasMetrics as CanvasMetricsType } from "@/lib/types";

interface CanvasMetricsProps {
  metrics: CanvasMetricsType;
}

export function CanvasMetrics({ metrics }: CanvasMetricsProps) {
  const items = [
    { label: "总时长", value: metrics.total_duration_text, icon: Clock },
    { label: "通勤", value: metrics.travel_time_text, icon: Route },
    { label: "结束", value: metrics.end_time_text, icon: Timer },
    { label: "适配", value: metrics.fit_label, icon: ShieldCheck },
  ];

  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.label} className="rounded-lg border border-zinc-200 bg-white px-3 py-2">
            <div className="flex items-center gap-1.5 text-xs text-zinc-500">
              <Icon className="h-3.5 w-3.5" />
              {item.label}
            </div>
            <div className="mt-1 text-sm font-semibold text-zinc-900">{item.value}</div>
          </div>
        );
      })}
    </div>
  );
}
