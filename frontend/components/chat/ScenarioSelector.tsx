"use client";

import { cn } from "@/lib/utils";
import type { Scenario } from "@/lib/types";
import { Users, Baby } from "lucide-react";

interface ScenarioSelectorProps {
  selected: Scenario;
  onSelect: (scenario: Scenario) => void;
  disabled?: boolean;
}

export function ScenarioSelector({ selected, onSelect, disabled = false }: ScenarioSelectorProps) {
  return (
    <div className="flex gap-3">
      <button
        type="button"
        onClick={() => onSelect("family")}
        disabled={disabled}
        aria-pressed={selected === "family"}
        className={cn(
          "flex flex-1 flex-col items-center gap-2 rounded-xl border-2 p-4 transition-all",
          selected === "family"
            ? "border-orange-400 bg-orange-50 shadow-sm"
            : "border-zinc-200 bg-white hover:border-zinc-300",
          disabled && "pointer-events-none opacity-50"
        )}
      >
        <Baby className="h-6 w-6 text-orange-500" />
        <span className="text-sm font-medium text-zinc-900">家庭出游</span>
        <span className="text-xs text-zinc-500">孩子5岁，老婆在减肥</span>
      </button>

      <button
        type="button"
        onClick={() => onSelect("friends")}
        disabled={disabled}
        aria-pressed={selected === "friends"}
        className={cn(
          "flex flex-1 flex-col items-center gap-2 rounded-xl border-2 p-4 transition-all",
          selected === "friends"
            ? "border-blue-400 bg-blue-50 shadow-sm"
            : "border-zinc-200 bg-white hover:border-zinc-300",
          disabled && "pointer-events-none opacity-50"
        )}
      >
        <Users className="h-6 w-6 text-blue-500" />
        <span className="text-sm font-medium text-zinc-900">朋友聚会</span>
        <span className="text-xs text-zinc-500">4个人，2男2女</span>
      </button>
    </div>
  );
}
