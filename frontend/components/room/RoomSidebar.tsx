"use client";

import { CheckCircle2, Users, Vote } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ParticipantAvatar } from "./ParticipantAvatar";
import type { ParticipantId, RoomState } from "@/lib/types";

interface RoomSidebarProps {
  room: RoomState;
  activeUserId: ParticipantId;
  onSimulate: () => void;
  onReset: () => void;
}

export function RoomSidebar({ room, activeUserId, onSimulate, onReset }: RoomSidebarProps) {
  const activeUser = room.participants.find((item) => item.id === activeUserId) ?? room.participants[0];
  const activeOption = room.plan_options.find((item) => item.option_id === room.active_plan_id);

  return (
    <aside className="flex min-h-0 flex-col border-r border-zinc-200 bg-white">
      <header className="border-b border-zinc-200 px-4 py-3">
        <div className="text-base font-semibold text-zinc-900">Weekend Planner</div>
        <div className="text-xs text-zinc-500">Collaborative AI Mode</div>
      </header>

      <div className="custom-scrollbar min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
        <section>
          <div className="mb-2 text-xs font-medium text-zinc-500">当前账号</div>
          <div className="flex items-center gap-2 rounded-lg border border-orange-100 bg-orange-50 p-3">
            <ParticipantAvatar participant={activeUser} />
            <div>
              <div className="text-sm font-semibold text-zinc-900">{activeUser.name}</div>
              <div className="text-xs text-zinc-500">{activeUser.role === "host" ? "发起人" : "成员"}</div>
            </div>
          </div>
        </section>

        <section>
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-zinc-500">
            <Users className="h-3.5 w-3.5" />
            房间成员
          </div>
          <div className="space-y-2">
            {room.participants.map((participant) => (
              <div key={participant.id} className="flex items-center justify-between rounded-lg bg-zinc-50 px-3 py-2">
                <div className="flex items-center gap-2">
                  <ParticipantAvatar participant={participant} size="sm" />
                  <div>
                    <div className="text-sm font-medium text-zinc-900">{participant.name}</div>
                    <div className="text-xs text-zinc-500">{participant.preference_profile.likes.join("、")}</div>
                  </div>
                </div>
                <span className="text-xs text-green-600">在线</span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-zinc-500">
            <Vote className="h-3.5 w-3.5" />
            投票概览
          </div>
          <div className="space-y-2">
            {room.plan_options.map((option) => (
              <div key={option.option_id} className="rounded-lg border border-zinc-100 bg-white p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium text-zinc-900">{option.label}</div>
                  {option.option_id === room.active_plan_id && (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  )}
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
        </section>

        <section className="rounded-lg border border-green-100 bg-green-50 p-3">
          <div className="text-sm font-semibold text-green-900">当前共识</div>
          <p className="mt-1 text-xs leading-5 text-green-800">{room.consensus.summary}</p>
          {activeOption && <div className="mt-2 text-xs text-green-700">推荐：{activeOption.label}</div>}
        </section>

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
      </div>

      <div className="space-y-2 border-t border-zinc-200 p-4">
        <Button type="button" className="w-full" onClick={onSimulate}>
          自动演示协作
        </Button>
        <Button type="button" variant="outline" className="w-full" onClick={onReset}>
          重置房间
        </Button>
      </div>
    </aside>
  );
}
