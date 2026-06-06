"use client";

import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CanvasCheck, CanvasChecks as CanvasChecksType } from "@/lib/types";

interface CanvasChecksProps {
  checks: CanvasChecksType;
  scenario: "family" | "friends";
}

function CheckList({ title, checks, tone }: { title: string; checks: CanvasCheck[]; tone: "green" | "amber" | "red" }) {
  if (checks.length === 0) return null;
  const Icon = tone === "green" ? CheckCircle2 : tone === "amber" ? Info : AlertTriangle;

  return (
    <div>
      <div className="mb-2 text-xs font-medium text-zinc-600">{title}</div>
      <div className="grid gap-2 sm:grid-cols-2">
        {checks.map((check) => (
          <div
            key={check.id}
            className={cn(
              "rounded-lg border px-3 py-2 text-sm",
              tone === "green" && "border-green-200 bg-green-50 text-green-800",
              tone === "amber" && "border-amber-200 bg-amber-50 text-amber-800",
              tone === "red" && "border-red-200 bg-red-50 text-red-800"
            )}
          >
            <div className="flex items-center gap-1.5 font-medium">
              <Icon className="h-4 w-4" />
              {check.label}
            </div>
            <div className="mt-1 text-xs opacity-80">{check.detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function CanvasChecks({ checks, scenario }: CanvasChecksProps) {
  const title = scenario === "friends" ? "朋友局适配检查" : "家庭安心检查";

  return (
    <section className="space-y-3 rounded-lg border border-zinc-100 bg-white p-4 shadow-sm shadow-zinc-100">
      <div className="text-sm font-semibold text-zinc-900">{title}</div>
      <CheckList title="已满足" checks={checks.passed} tone="green" />
      <CheckList title="轻微降级 / 风险提醒" checks={checks.warnings} tone="amber" />
      <CheckList title="需处理" checks={checks.failed} tone="red" />
    </section>
  );
}
