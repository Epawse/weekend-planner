"use client";

import { Check, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CanvasChecks } from "./CanvasChecks";
import { CanvasMetrics } from "./CanvasMetrics";
import { CanvasShareCard } from "./CanvasShareCard";
import { CanvasTimeline } from "./CanvasTimeline";
import { ExecutionActionCard } from "./ExecutionActionCard";
import { FeedbackChangeCard } from "./FeedbackChangeCard";
import { FeedbackBar } from "./FeedbackBar";
import { ToolTaskPanel } from "./ToolTaskPanel";
import type { PlanCanvasState, PlanStatus } from "@/lib/types";

interface PlanCanvasProps {
  canvas: PlanCanvasState;
  status: PlanStatus;
  selectedTimelineId: string | null;
  onSelectTimeline: (timelineId: string, markerId: string) => void;
  onFeedback: (message: string, quickAction?: string) => void;
  onApprove: () => void;
  onReject: () => void;
  approvalEnabled?: boolean;
  approveLabel?: string;
  approvalHint?: string;
  embedded?: boolean;
}

export function PlanCanvas({
  canvas,
  status,
  selectedTimelineId,
  onSelectTimeline,
  onFeedback,
  onApprove,
  onReject,
  approvalEnabled = true,
  approveLabel = "确认并执行",
  approvalHint,
  embedded = false,
}: PlanCanvasProps) {
  const canApprove = status === "plan_ready";
  const isBusy = status === "planning" || status === "executing";
  const executionTitle = canvas.execution_results.length > 0 ? "执行结果" : "待执行";

  const Shell = embedded ? "section" : "main";
  const shellClass = embedded ? "bg-transparent" : "custom-scrollbar h-full overflow-y-auto bg-zinc-50/80";
  const containerClass = embedded ? "flex flex-col gap-4" : "mx-auto flex max-w-5xl flex-col gap-4 p-4 xl:p-6";

  return (
    <Shell className={shellClass}>
      <div className={containerClass}>
        <section className="rounded-lg border border-zinc-100 bg-white p-5 shadow-sm shadow-zinc-100">
          <div className="flex flex-col gap-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xs font-medium text-orange-600">
                  {canvas.scenario === "friends" ? "Friends AI Mode" : "Family AI Mode"}
                </div>
                <h2 className="mt-1 text-2xl font-semibold tracking-normal text-zinc-950">{canvas.title}</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">{canvas.summary}</p>
              </div>
              <div className="rounded-md border border-orange-100 bg-orange-50 px-2.5 py-1 text-xs font-medium text-orange-700">
                {canvas.metrics.route_label}
              </div>
            </div>

            <CanvasMetrics metrics={canvas.metrics} />
          </div>
        </section>

        <FeedbackChangeCard summary={canvas.feedback.change_summary} />

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
          <div className="space-y-4">
            <div className="rounded-lg border border-zinc-100 bg-white p-4 shadow-sm shadow-zinc-100">
              <CanvasTimeline
                items={canvas.timeline}
                selectedTimelineId={selectedTimelineId}
                onSelectTimeline={onSelectTimeline}
              />
            </div>

            <CanvasChecks checks={canvas.checks} scenario={canvas.scenario} />

            <ToolTaskPanel tasks={canvas.tool_tasks} collapsible defaultOpen={false} />
          </div>

          <div className="space-y-4">
            <FeedbackBar feedback={canvas.feedback} disabled={isBusy} onFeedback={onFeedback} />
            <ExecutionActionCard
              title={executionTitle}
              actions={canvas.execution_results.length > 0 ? canvas.execution_results : canvas.pending_actions}
            />
            <CanvasShareCard shareText={canvas.share_text} />
          </div>
        </section>

        {canApprove && (
          <div className="sticky bottom-4 z-10 flex items-center justify-between gap-3 rounded-lg border border-zinc-100 bg-white/95 p-3 shadow-lg shadow-zinc-200/60 backdrop-blur">
            <div className="text-xs leading-5 text-zinc-500">{approvalHint}</div>
            <div className="flex shrink-0 gap-2">
              <Button type="button" variant="outline" onClick={onReject}>
                <RotateCcw className="mr-1.5 h-4 w-4" />
                重新规划
              </Button>
              <Button type="button" disabled={!approvalEnabled} onClick={onApprove}>
                <Check className="mr-1.5 h-4 w-4" />
                {approveLabel}
              </Button>
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}
