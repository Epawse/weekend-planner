"use client";

import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { TimelineView } from "./TimelineView";
import { ActionButton } from "./ActionButton";
import { ShareButton } from "@/components/shared/ShareButton";
import { formatDuration } from "@/lib/utils";
import { Clock, Route } from "lucide-react";
import type { Plan, PlanStatus } from "@/lib/types";

interface PlanCardProps {
  plan: Plan;
  status: PlanStatus;
  onApprove: () => void;
  onReject: () => void;
}

export function PlanCard({ plan, status, onApprove, onReject }: PlanCardProps) {
  const showActions = status === "plan_ready";
  const isExecuting = status === "executing";
  const isDone = status === "done";

  return (
    <Card className="overflow-hidden">
      <CardHeader className="bg-gradient-to-r from-orange-50 to-amber-50">
        <CardTitle className="flex items-center justify-between">
          <span>{plan.title}</span>
          {isDone && <ShareButton text={plan.share_text} />}
        </CardTitle>
        <div className="flex items-center gap-4 text-sm text-zinc-500">
          <span className="flex items-center gap-1">
            <Clock className="h-4 w-4" />
            总时长 {formatDuration(plan.duration_hours * 60)}
          </span>
          <span className="flex items-center gap-1">
            <Route className="h-4 w-4" />
            通勤 {plan.total_travel_minutes} 分钟
          </span>
        </div>
      </CardHeader>

      <CardContent className="pt-5">
        <TimelineView activities={plan.activities} />
      </CardContent>

      {showActions && (
        <CardFooter>
          <div className="w-full">
            <ActionButton
              onApprove={onApprove}
              onReject={onReject}
              disabled={isExecuting}
            />
          </div>
        </CardFooter>
      )}

      {isDone && (
        <CardFooter>
          <div className="w-full rounded-lg bg-green-50 p-3 text-center text-sm text-green-700">
            {plan.share_text}
          </div>
        </CardFooter>
      )}
    </Card>
  );
}
