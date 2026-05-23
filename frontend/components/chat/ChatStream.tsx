"use client";

import { cn } from "@/lib/utils";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import type { PlanEvent } from "@/lib/types";
import { Search, Brain, Wrench } from "lucide-react";

interface ChatStreamProps {
  events: PlanEvent[];
  isStreaming: boolean;
}

function getEventIcon(type: string) {
  switch (type) {
    case "thinking":
      return <Brain className="h-4 w-4 text-purple-500" />;
    case "tool_calling":
      return <Search className="h-4 w-4 text-blue-500" />;
    case "tool_result":
      return <Wrench className="h-4 w-4 text-green-500" />;
    default:
      return null;
  }
}

function getEventLabel(event: PlanEvent): string {
  switch (event.type) {
    case "thinking":
      return (event.data.message as string) || "正在思考...";
    case "tool_calling":
      return (event.data.message as string) || `调用工具: ${(event.data.tool as string) || ""}`;
    case "tool_result":
      return (event.data.message as string) || "数据获取完成";
    case "step_start":
      return `执行: ${(event.data.venue as string) || (event.data.action as string) || ""}`;
    case "step_complete":
      return `完成: ${(event.data.venue as string) || (event.data.confirmation as string) || ""}`;
    default:
      return event.type;
  }
}

export function ChatStream({ events, isStreaming }: ChatStreamProps) {
  const streamEvents = events.filter(
    (e) => e.type === "thinking" || e.type === "tool_calling" || e.type === "tool_result"
  );

  if (streamEvents.length === 0 && !isStreaming) return null;

  return (
    <div className="space-y-2">
      {streamEvents.map((event, index) => (
        <div
          key={`${event.type}-${index}`}
          className={cn(
            "flex items-center gap-2 rounded-lg px-3 py-2 text-xs",
            "bg-zinc-50 text-zinc-600 animate-in fade-in slide-in-from-bottom-1"
          )}
        >
          {getEventIcon(event.type)}
          <span>{getEventLabel(event)}</span>
        </div>
      ))}
      {isStreaming && (
        <div className="flex items-center gap-2 px-3 py-2">
          <LoadingSpinner size="sm" />
          <span className="text-xs text-zinc-500">处理中...</span>
        </div>
      )}
    </div>
  );
}
