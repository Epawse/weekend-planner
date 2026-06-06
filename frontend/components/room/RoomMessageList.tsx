"use client";

import { ParticipantAvatar } from "./ParticipantAvatar";
import type { Participant, SharedMessage } from "@/lib/types";

interface RoomMessageListProps {
  messages: SharedMessage[];
  participants: Participant[];
}

export function RoomMessageList({ messages, participants }: RoomMessageListProps) {
  return (
    <section className="rounded-lg border border-zinc-100 bg-white p-4 shadow-sm shadow-zinc-100">
      <div className="mb-3 text-sm font-semibold text-zinc-900">多人对话</div>
      <div className="space-y-3">
        {messages.map((message) => {
          const participant = participants.find((item) => item.id === message.actor_id);
          const isAgent = message.actor_id === "agent";
          return (
            <div key={message.id} className="flex gap-3">
              <ParticipantAvatar participant={participant} participantId={message.actor_id} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-zinc-900">{message.actor_name}</span>
                  <span className="text-xs text-zinc-400">{formatTime(message.created_at)}</span>
                </div>
                <div
                  className={
                    isAgent
                      ? "mt-1 rounded-lg bg-orange-50 px-3 py-2 text-sm leading-6 text-orange-950"
                      : "mt-1 text-sm leading-6 text-zinc-700"
                  }
                >
                  {message.content}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}
