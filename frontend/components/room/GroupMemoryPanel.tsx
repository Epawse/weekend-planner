"use client";

import { Brain, GitBranch } from "lucide-react";
import { ParticipantAvatar } from "./ParticipantAvatar";
import type { GroupMemory } from "@/lib/types";

interface GroupMemoryPanelProps {
  memory: GroupMemory;
}

export function GroupMemoryPanel({ memory }: GroupMemoryPanelProps) {
  return (
    <section className="rounded-lg border border-zinc-100 bg-white p-4 shadow-sm shadow-zinc-100">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-900">
        <Brain className="h-4 w-4 text-orange-600" />
        群体记忆
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <div>
          <div className="mb-1 text-xs font-medium text-zinc-500">已确认</div>
          <div className="flex flex-wrap gap-1.5">
            {memory.confirmed_constraints.map((item) => (
              <span key={item} className="rounded bg-green-50 px-2 py-1 text-xs text-green-700">
                {item}
              </span>
            ))}
          </div>
        </div>
        <div>
          <div className="mb-1 text-xs font-medium text-zinc-500">软偏好</div>
          <div className="flex flex-wrap gap-1.5">
            {memory.soft_preferences.map((item) => (
              <span key={item} className="rounded bg-orange-50 px-2 py-1 text-xs text-orange-700">
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>

      {memory.conflicts.length > 0 && (
        <div className="mt-3 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-500">
            <GitBranch className="h-3.5 w-3.5" />
            当前分歧
          </div>
          {memory.conflicts.map((conflict) => (
            <div key={conflict.topic} className="rounded-lg bg-zinc-50 p-3">
              <div className="text-sm font-medium text-zinc-900">{conflict.topic}</div>
              <div className="mt-2 flex items-center gap-3 text-xs text-zinc-500">
                <div className="flex items-center gap-1">
                  支持
                  {conflict.supporters.map((id) => (
                    <ParticipantAvatar key={id} participantId={id} size="sm" />
                  ))}
                </div>
                <div className="flex items-center gap-1">
                  顾虑
                  {conflict.opponents.map((id) => (
                    <ParticipantAvatar key={id} participantId={id} size="sm" />
                  ))}
                </div>
              </div>
              <div className="mt-2 text-xs leading-5 text-zinc-600">{conflict.resolution}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
