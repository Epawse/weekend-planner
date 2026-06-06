"use client";

import { CheckCircle2, Play, RotateCcw, Users, Vote } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ParticipantAvatar } from "./ParticipantAvatar";
import type { ParticipantId, RoomState, Scenario } from "@/lib/types";

interface RoomSidebarProps {
  room: RoomState;
  activeUserId: ParticipantId;
  isPlayingDemo: boolean;
  onPlayDemo: () => void;
  onReset: (scenario?: Scenario) => void;
  onScenarioChange: (scenario: Scenario) => void;
}

const SCENARIO_LABELS: Record<Scenario, string> = {
  friends: "朋友聚会",
  family: "家庭出游",
};

export function RoomSidebar({
  room,
  activeUserId,
  isPlayingDemo,
  onPlayDemo,
  onReset,
  onScenarioChange,
}: RoomSidebarProps) {
  const activeUser = room.participants.find((item) => item.id === activeUserId) ?? room.participants[0];
  const activeOption = room.plan_options.find((item) => item.option_id === room.active_plan_id);
  const hasVotes = room.plan_options.length > 0;
  const hasConsensus = room.consensus.current_votes >= room.consensus.required_votes && hasVotes;

  return (
    <aside className="flex min-h-0 flex-col border-r border-zinc-200 bg-white">
      <header className="border-b border-zinc-200 px-4 py-3">
        <div className="text-base font-semibold text-zinc-900">Weekend Planner</div>
        <div className="text-xs text-zinc-500">Collaborative AI Mode</div>
      </header>

      <div className="custom-scrollbar min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        <section>
          <div className="mb-2 text-xs font-medium text-zinc-500">当前场景</div>
          <div className="grid grid-cols-2 gap-2">
            {room.available_scenarios.map((scenario) => (
              <button
                key={scenario}
                type="button"
                onClick={() => onScenarioChange(scenario)}
                className={cn(
                  "rounded-lg border px-3 py-2 text-sm font-medium",
                  room.scenario === scenario
                    ? "border-orange-300 bg-orange-50 text-orange-800"
                    : "border-zinc-200 text-zinc-600 hover:bg-zinc-50"
                )}
              >
                {SCENARIO_LABELS[scenario]}
              </button>
            ))}
          </div>
        </section>

        <section>
          <div className="mb-2 text-xs font-medium text-zinc-500">当前账号</div>
          <div className="flex items-center gap-2 rounded-lg border border-orange-100 bg-orange-50 p-3">
            <ParticipantAvatar participant={activeUser} />
            <div>
              <div className="text-sm font-semibold text-zinc-900">{activeUser.name}</div>
              <div className="text-xs text-zinc-500">{roleLabel(activeUser.role)}</div>
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-zinc-100 bg-zinc-50 p-3">
          <div className="text-sm font-semibold text-zinc-900">{room.stage_title}</div>
          <p className="mt-1 text-xs leading-5 text-zinc-600">{room.stage_description}</p>
        </section>

        <section>
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-zinc-500">
            <Users className="h-3.5 w-3.5" />
            房间成员
          </div>
          <div className="space-y-2">
            {room.participants
              .filter((participant) => participant.role !== "agent")
              .map((participant) => (
                <div key={participant.id} className="flex items-center justify-between rounded-lg bg-zinc-50 px-3 py-2">
                  <div className="flex items-center gap-2">
                    <ParticipantAvatar participant={participant} size="sm" />
                    <div>
                      <div className="text-sm font-medium text-zinc-900">{participant.name}</div>
                      <div className="text-xs text-zinc-500">{participant.preference_profile.likes.join("、")}</div>
                    </div>
                  </div>
                  <span className={cn("text-xs", participant.role === "profile" ? "text-amber-600" : "text-green-600")}>
                    {participant.role === "profile" ? "画像" : "在线"}
                  </span>
                </div>
              ))}
          </div>
        </section>

        <section>
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-zinc-500">
            <Vote className="h-3.5 w-3.5" />
            投票概览
          </div>
          {hasVotes ? (
            <div className="space-y-2">
              {room.plan_options.map((option) => (
                <div key={option.option_id} className="rounded-lg border border-zinc-100 bg-white p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-zinc-900">{option.label}</div>
                    {option.option_id === room.active_plan_id && <CheckCircle2 className="h-4 w-4 text-green-600" />}
                  </div>
                  <div className="mt-2 flex gap-1">
                    {option.vote_summary.supporters.length > 0 ? (
                      option.vote_summary.supporters.map((id) => (
                        <ParticipantAvatar key={id} participantId={id} size="sm" />
                      ))
                    ) : (
                      <span className="text-xs text-zinc-400">等待投票</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-zinc-200 p-3 text-xs leading-5 text-zinc-500">
              生成 A/B/C 方案后，成员头像会显示在这里。
            </div>
          )}
        </section>

        <section className={cn("rounded-lg border p-3", hasConsensus ? "border-green-100 bg-green-50" : "border-zinc-100 bg-white")}>
          <div className={cn("text-sm font-semibold", hasConsensus ? "text-green-900" : "text-zinc-900")}>
            当前共识
          </div>
          <p className={cn("mt-1 text-xs leading-5", hasConsensus ? "text-green-800" : "text-zinc-500")}>
            {room.consensus.summary}
          </p>
          {activeOption && <div className="mt-2 text-xs text-green-700">推荐：{activeOption.label}</div>}
        </section>

        {room.group_memory.confirmed_constraints.length > 0 && (
          <section>
            <div className="mb-2 text-xs font-medium text-zinc-500">已确认约束</div>
            <div className="flex flex-wrap gap-1.5">
              {room.group_memory.confirmed_constraints.map((item) => (
                <span key={item} className="rounded bg-zinc-100 px-2 py-1 text-xs text-zinc-700">
                  {item}
                </span>
              ))}
            </div>
          </section>
        )}
      </div>

      <div className="space-y-2 border-t border-zinc-200 p-4">
        <Button type="button" className="w-full" onClick={onPlayDemo} disabled={isPlayingDemo}>
          <Play className="mr-1.5 h-4 w-4" />
          {isPlayingDemo ? "演示进行中" : "自动演示动作"}
        </Button>
        <Button type="button" variant="outline" className="w-full" onClick={() => onReset(room.scenario)}>
          <RotateCcw className="mr-1.5 h-4 w-4" />
          重置当前场景
        </Button>
      </div>
    </aside>
  );
}

function roleLabel(role: string) {
  if (role === "host") return "发起人";
  if (role === "profile") return "画像约束";
  if (role === "agent") return "规划者";
  return "成员";
}
