"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { ParticipantAvatar } from "./ParticipantAvatar";
import type { TypewriterFrame } from "@/hooks/useTypewriter";
import type { Participant, ParticipantId, SharedMessage } from "@/lib/types";

interface RoomMessageListProps {
  messages: SharedMessage[];
  participants: Participant[];
  typingParticipants: ParticipantId[];
  /** Per-message streaming frames from useTypewriter (sparse: only the live one). */
  streaming?: Map<string, TypewriterFrame>;
  /** Ids not yet revealed by the sequential typewriter — skip rendering them. */
  hiddenIds?: Set<string>;
  /** Show an agent "thinking" indicator while a turn is being generated. */
  agentThinking?: boolean;
  /** The agent's reasoning streaming in live during the current turn. */
  liveReasoning?: string;
  /** Neutral "generating" indicator shown during the demo's LLM wait. */
  preparing?: boolean;
}

function TypingDots() {
  return (
    <span className="inline-flex gap-1">
      <span className="animate-typing-dot h-1.5 w-1.5 rounded-full bg-zinc-400" />
      <span className="animate-typing-dot h-1.5 w-1.5 rounded-full bg-zinc-400 [animation-delay:0.18s]" />
      <span className="animate-typing-dot h-1.5 w-1.5 rounded-full bg-zinc-400 [animation-delay:0.36s]" />
    </span>
  );
}

/**
 * The in-progress agent turn rendered as ONE persistent bubble that morphs in
 * place: "正在思考" while the real LLM reasons (~7-9s), then the streaming reply —
 * both inside the SAME orange box element. Rendered under a stable key so React
 * reuses the DOM node across the thinking→streaming transition, avoiding an abrupt
 * remount/swap when the reply arrives. The reasoning panel opens by default so the
 * reasoning the user just watched stream does not appear to vanish.
 */
function AgentTurnBubble({
  agent,
  thinking,
  reasoning,
  text,
  streaming,
  timeLabel,
}: {
  agent?: Participant;
  thinking: boolean;
  reasoning?: string;
  text?: string;
  streaming?: boolean;
  timeLabel?: string;
}) {
  return (
    <div className="animate-message-in flex gap-3">
      <ParticipantAvatar participant={agent} participantId="agent" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-zinc-900">{agent?.name ?? "规划助手"}</span>
          {!thinking && timeLabel ? <span className="text-xs text-zinc-400">{timeLabel}</span> : null}
        </div>
        <div className="mt-1 rounded-lg bg-orange-50 px-3 py-2 text-sm leading-6">
          {thinking ? (
            <span className="inline-flex items-center gap-1.5 text-orange-700">
              <span>正在思考</span>
              <TypingDots />
            </span>
          ) : (
            <span className="text-orange-950">
              <span className="whitespace-pre-wrap">{text}</span>
              {streaming ? (
                <span
                  aria-hidden
                  className="animate-caret-blink ml-0.5 inline-block h-3.5 w-[2px] translate-y-[2px] rounded-full bg-current align-baseline"
                />
              ) : null}
            </span>
          )}
        </div>
        {reasoning ? <ReasoningPanel reasoning={reasoning} defaultOpen /> : null}
      </div>
    </div>
  );
}

/**
 * Neutral "a turn is being generated" indicator shown during the demo's LLM wait,
 * before any member speech exists. Deliberately carries no agent identity or
 * reasoning — it must not read as the agent "thinking" ahead of the members it
 * will reveal. Mutually exclusive in time with the agent "thinking" bubble.
 */
function GeneratingIndicator() {
  return (
    <div className="animate-message-in flex items-center gap-1.5 px-1 text-sm text-zinc-400">
      <span>正在生成对话…</span>
      <TypingDots />
    </div>
  );
}

/**
 * Collapsible panel showing the agent's genuine step reasoning. Opens by default
 * for the latest agent message so the reasoning the user just watched stream does
 * not vanish; older messages stay collapsed. Stays user-toggleable.
 */
function ReasoningPanel({ reasoning, defaultOpen = false }: { reasoning: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      className="group mt-1.5"
    >
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1 text-xs text-zinc-400 transition-colors hover:text-zinc-600 [&::-webkit-details-marker]:hidden">
        <ChevronRight className="h-3 w-3 transition-transform duration-200 group-open:rotate-90" />
        思考过程
      </summary>
      <div className="mt-1.5 whitespace-pre-wrap rounded-md border border-zinc-100 bg-zinc-50 px-2.5 py-2 text-xs leading-5 text-zinc-500">
        {reasoning}
      </div>
    </details>
  );
}

export function RoomMessageList({
  messages,
  participants,
  typingParticipants,
  streaming,
  hiddenIds,
  agentThinking,
  liveReasoning,
  preparing,
}: RoomMessageListProps) {
  const visibleMessages = hiddenIds
    ? messages.filter((message) => !hiddenIds.has(message.id))
    : messages;
  // The latest agent message's reasoning opens by default (continuity with the
  // live "thinking" stream the user just watched); older ones stay collapsed.
  const lastAgentMessageId = lastAgentId(visibleMessages);
  // The in-progress agent reply: the last message, when it is the agent's and is
  // still typing. It is rendered ONLY by the unified turn bubble (skipped in the
  // map below) so the "thinking" indicator can morph into it in place.
  const lastMessage = visibleMessages[visibleMessages.length - 1];
  const lastFrame = lastMessage ? streaming?.get(lastMessage.id) : undefined;
  const activeAgentMessage =
    lastMessage && lastMessage.actor_id === "agent" && lastFrame?.streaming ? lastMessage : null;
  // One persistent bubble spans the whole turn: "正在思考" first, then the
  // streaming reply. The agent's turn coexists with members' "typing" — they
  // describe different actors, so neither should suppress the other.
  const showActiveAgentTurn = Boolean(agentThinking) || Boolean(activeAgentMessage);
  // The neutral "generating" indicator only shows before the agent turn starts;
  // the two never appear together.
  const showPreparing = Boolean(preparing) && !showActiveAgentTurn;
  const agent = participants.find((item) => item.id === "agent");

  if (
    visibleMessages.length === 0 &&
    typingParticipants.length === 0 &&
    !showActiveAgentTurn &&
    !showPreparing
  ) {
    return null;
  }

  return (
    <section className="rounded-lg border border-zinc-100 bg-white p-4 shadow-sm shadow-zinc-100">
      <div className="mb-3 text-sm font-semibold text-zinc-900">多人对话</div>
      <div className="space-y-3">
        {visibleMessages
          .filter((message) => message.id !== activeAgentMessage?.id)
          .map((message) => {
          const participant = participants.find((item) => item.id === message.actor_id);
          const isAgent = message.actor_id === "agent";
          const frame = streaming?.get(message.id);
          const text = frame ? frame.text : message.content;
          const isStreaming = frame?.streaming ?? false;
          return (
            <div key={message.id} className="animate-message-in flex gap-3">
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
                  <span className="whitespace-pre-wrap">{text}</span>
                  {isStreaming && (
                    <span
                      aria-hidden
                      className="animate-caret-blink ml-0.5 inline-block h-3.5 w-[2px] translate-y-[2px] rounded-full bg-current align-baseline"
                    />
                  )}
                </div>
                {isAgent && message.reasoning && !isStreaming && (
                  // Re-key on latest/older so a panel re-collapses once it is no
                  // longer the most recent agent message: `defaultOpen` is read
                  // only on mount, so a superseded still-open panel needs a fresh
                  // instance to fall back to collapsed.
                  <ReasoningPanel
                    key={message.id === lastAgentMessageId ? "reasoning-latest" : "reasoning-older"}
                    reasoning={message.reasoning}
                    defaultOpen={message.id === lastAgentMessageId}
                  />
                )}
              </div>
            </div>
          );
        })}
        {typingParticipants.map((participantId) => {
          const participant = participants.find((item) => item.id === participantId);
          if (!participant) return null;
          return (
            <div key={`typing_${participantId}`} className="animate-message-in flex gap-3">
              <ParticipantAvatar participant={participant} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-zinc-900">{participant.name}</div>
                <div className="mt-1 inline-flex items-center gap-1.5 rounded-lg bg-zinc-100 px-3 py-2 text-sm text-zinc-500">
                  <span>{participant.name}正在输入</span>
                  <TypingDots />
                </div>
              </div>
            </div>
          );
        })}
        {showActiveAgentTurn && (
          <AgentTurnBubble
            key="active-agent-turn"
            agent={agent}
            thinking={Boolean(agentThinking)}
            reasoning={agentThinking ? liveReasoning : activeAgentMessage?.reasoning}
            text={
              activeAgentMessage
                ? streaming?.get(activeAgentMessage.id)?.text ?? activeAgentMessage.content
                : undefined
            }
            streaming={Boolean(activeAgentMessage && streaming?.get(activeAgentMessage.id)?.streaming)}
            timeLabel={activeAgentMessage ? formatTime(activeAgentMessage.created_at) : undefined}
          />
        )}
        {showPreparing && <GeneratingIndicator />}
      </div>
    </section>
  );
}

function lastAgentId(messages: SharedMessage[]): string | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].actor_id === "agent") return messages[index].id;
  }
  return null;
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}
