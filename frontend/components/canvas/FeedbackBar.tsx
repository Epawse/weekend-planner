"use client";

import { Button } from "@/components/ui/button";
import type { CanvasFeedback } from "@/lib/types";

interface FeedbackBarProps {
  feedback: CanvasFeedback;
  disabled?: boolean;
  onFeedback: (message: string, quickAction?: string) => void;
}

export function FeedbackBar({ feedback, disabled = false, onFeedback }: FeedbackBarProps) {
  if (feedback.quick_actions.length === 0) return null;
  const latest = feedback.history[feedback.history.length - 1];

  return (
    <section className="space-y-2">
      <div className="text-xs font-medium text-zinc-500">快捷修改</div>
      <div className="flex flex-wrap gap-2">
        {feedback.quick_actions.map((action) => (
          <Button
            key={action}
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => onFeedback(action, action)}
          >
            {action}
          </Button>
        ))}
      </div>
      {latest && (
        <div className="space-y-1 rounded-lg bg-zinc-50 p-2">
          <div className="text-xs leading-5 text-zinc-600">
            <span className="font-medium text-zinc-800">{latest.label}</span> · {latest.result_message}
          </div>
        </div>
      )}
    </section>
  );
}
