"use client";

import { ArrowRight, CheckCircle2, RotateCcw } from "lucide-react";
import type { FeedbackChangeSummary } from "@/lib/types";

interface FeedbackChangeCardProps {
  summary: FeedbackChangeSummary | null;
}

export function FeedbackChangeCard({ summary }: FeedbackChangeCardProps) {
  if (!summary) return null;

  return (
    <section className="rounded-lg border border-orange-100 bg-orange-50/70 p-4">
      <div className="flex items-start gap-2">
        <RotateCcw className="mt-0.5 h-4 w-4 text-orange-600" />
        <div className="min-w-0">
          <div className="text-sm font-semibold text-orange-950">{summary.title}</div>
          <p className="mt-1 text-sm leading-5 text-orange-900">{summary.result}</p>
        </div>
      </div>

      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-[1fr_auto_1fr]">
        <div className="rounded-md bg-white/70 px-3 py-2 text-zinc-600">
          <div className="mb-1 font-medium text-zinc-900">修改前</div>
          {summary.before}
        </div>
        <div className="hidden items-center justify-center text-orange-500 sm:flex">
          <ArrowRight className="h-4 w-4" />
        </div>
        <div className="rounded-md bg-white px-3 py-2 text-zinc-700">
          <div className="mb-1 font-medium text-zinc-900">修改后</div>
          {summary.after}
        </div>
      </div>

      {(summary.preserved.length > 0 || summary.changed.length > 0) && (
        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
          {summary.preserved.length > 0 && (
            <div className="rounded-md bg-white/70 px-3 py-2">
              <div className="mb-1 font-medium text-zinc-900">保留</div>
              <div className="flex flex-wrap gap-1.5">
                {summary.preserved.map((item) => (
                  <span key={item} className="rounded bg-zinc-100 px-2 py-0.5 text-zinc-600">
                    {item}
                  </span>
                ))}
              </div>
            </div>
          )}
          {summary.changed.length > 0 && (
            <div className="rounded-md bg-white px-3 py-2">
              <div className="mb-1 flex items-center gap-1 font-medium text-zinc-900">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
                调整
              </div>
              <div className="space-y-1 text-zinc-600">
                {summary.changed.map((item) => (
                  <div key={item}>{item}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {summary.note && <div className="mt-3 text-xs leading-5 text-orange-800">{summary.note}</div>}
    </section>
  );
}
