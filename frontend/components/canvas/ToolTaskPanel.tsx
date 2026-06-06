"use client";

import { CheckCircle2, Loader2, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ToolTask } from "@/lib/types";

interface ToolTaskPanelProps {
  tasks: ToolTask[];
  compact?: boolean;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

export function ToolTaskPanel({
  tasks,
  compact = false,
  collapsible = false,
  defaultOpen = true,
}: ToolTaskPanelProps) {
  if (tasks.length === 0) return null;
  const doneCount = tasks.filter((task) => task.status === "done").length;
  const warnCount = tasks.filter((task) => task.status === "warn" || task.status === "failed").length;
  const runningCount = tasks.filter((task) => task.status === "running").length;
  const summary = runningCount
    ? `${runningCount} 项进行中，${doneCount} 项完成`
    : `${doneCount} 项通过，${warnCount} 项提醒`;

  const body = (
    <div className="space-y-2">
      {tasks.map((task) => {
        const warn = task.status === "warn" || task.status === "failed";
        const running = task.status === "running";
        return (
          <div key={task.id} className="flex items-start gap-2 text-sm">
            {running ? (
              <Loader2 className="mt-0.5 h-4 w-4 animate-spin text-blue-600" />
            ) : warn ? (
              <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600" />
            ) : (
              <CheckCircle2 className="mt-0.5 h-4 w-4 text-green-600" />
            )}
            <div>
              <div className="font-medium text-zinc-800">{task.label}</div>
              <div className="text-xs text-zinc-500">{task.detail}</div>
            </div>
          </div>
        );
      })}
    </div>
  );

  if (collapsible) {
    return (
      <details
        className={cn("rounded-lg border border-zinc-100 bg-white", compact ? "p-3" : "p-4")}
        open={defaultOpen}
      >
        <summary className="cursor-pointer list-none text-sm font-semibold text-zinc-900">
          本地生活任务：{summary}
        </summary>
        <div className="mt-3">{body}</div>
      </details>
    );
  }

  return (
    <section className={cn("rounded-lg border border-zinc-200 bg-white", compact ? "p-3" : "p-4")}>
      <div className="mb-3 text-sm font-semibold text-zinc-900">本地生活任务：{summary}</div>
      {body}
    </section>
  );
}
