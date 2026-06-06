"use client";

import { AlertTriangle, CalendarClock, CheckCircle2, Circle, Loader2, Ticket, Users } from "lucide-react";
import type { ExecutionAction } from "@/lib/types";

interface ExecutionActionCardProps {
  title: string;
  actions: ExecutionAction[];
}

function ActionIcon({ status }: { status: ExecutionAction["status"] }) {
  if (status === "done") return <CheckCircle2 className="h-4 w-4 text-green-600" />;
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-blue-600" />;
  if (status === "failed") return <AlertTriangle className="h-4 w-4 text-red-600" />;
  return <Circle className="h-4 w-4 text-zinc-400" />;
}

export function ExecutionActionCard({ title, actions }: ExecutionActionCardProps) {
  if (actions.length === 0) return null;

  return (
    <section className="rounded-lg border border-zinc-100 bg-white p-4 shadow-sm shadow-zinc-100">
      <div className="mb-3 text-sm font-semibold text-zinc-900">{title}</div>
      <div className="space-y-3">
        {actions.map((action) => (
          <div key={action.id} className="rounded-lg border border-zinc-100 bg-zinc-50/70 p-3 text-sm">
            <div className="flex items-start gap-2">
              <ActionIcon status={action.status} />
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-zinc-900">{action.label}</div>
                <div className="mt-0.5 text-zinc-700">{action.target}</div>
              </div>
            </div>

            <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-600">
              {action.scheduled_time && (
                <span className="inline-flex items-center gap-1 rounded bg-white px-2 py-1">
                  <CalendarClock className="h-3.5 w-3.5" />
                  {action.scheduled_time}
                </span>
              )}
              {action.party_size && (
                <span className="inline-flex items-center gap-1 rounded bg-white px-2 py-1">
                  <Users className="h-3.5 w-3.5" />
                  {action.party_size}人
                </span>
              )}
              {action.confirmation && (
                <span className="inline-flex items-center gap-1 rounded bg-green-50 px-2 py-1 text-green-700">
                  <Ticket className="h-3.5 w-3.5" />
                  {action.confirmation}
                </span>
              )}
            </div>

            {action.note && <div className="mt-2 text-xs leading-5 text-zinc-600">{action.note}</div>}
            {action.detail && <div className="mt-1 text-xs leading-5 text-zinc-500">{action.detail}</div>}
            {action.next_step && (
              <div className="mt-2 text-xs font-medium text-orange-700">{action.next_step}</div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
