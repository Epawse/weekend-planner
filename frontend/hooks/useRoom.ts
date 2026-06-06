"use client";

import { useCallback, useEffect, useState } from "react";
import {
  advanceRoom,
  executeRoom,
  fetchRoom,
  resetRoom,
  sendRoomMessage,
  sendRoomReaction,
  sendRoomVote,
  simulateRoom,
  streamAdvanceRoom,
  streamRoomMessage,
  switchRoomScenario,
} from "@/lib/api";
import type { ParticipantId, RoomReactionType, RoomState, Scenario, SharedMessage } from "@/lib/types";

interface UseRoomReturn {
  room: RoomState | null;
  isLoading: boolean;
  isPlayingDemo: boolean;
  isAgentThinking: boolean;
  isPreparingTurn: boolean;
  liveReasoning: string;
  error: string | null;
  reloadRoom: () => Promise<void>;
  resetDemo: (scenario?: Scenario) => Promise<void>;
  switchScenario: (scenario: Scenario) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  voteForPlan: (planId: string, reason?: string) => Promise<void>;
  reactToVenue: (venueId: string, reactionType: RoomReactionType, reason?: string) => Promise<void>;
  advanceDemo: () => Promise<void>;
  playDemo: () => Promise<void>;
  simulateDemo: () => Promise<void>;
  executeActivePlan: () => Promise<void>;
}

export function useRoom(roomId: string, userId: ParticipantId): UseRoomReturn {
  const [room, setRoom] = useState<RoomState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPlayingDemo, setIsPlayingDemo] = useState(false);
  const [isAgentThinking, setIsAgentThinking] = useState(false);
  const [isPreparingTurn, setIsPreparingTurn] = useState(false);
  const [liveReasoning, setLiveReasoning] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setRoom(await fetchRoom(roomId, userId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "房间加载失败");
    } finally {
      setIsLoading(false);
    }
  }, [roomId, userId]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialRoom() {
      try {
        const nextRoom = await fetchRoom(roomId, userId);
        if (cancelled) return;
        setRoom(nextRoom);
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "房间加载失败");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadInitialRoom();

    return () => {
      cancelled = true;
    };
  }, [roomId, userId]);

  const updateRoom = useCallback(
    async (operation: () => Promise<RoomState>) => {
      setError(null);
      try {
        setRoom(await operation());
      } catch (err) {
        setError(err instanceof Error ? err.message : "房间更新失败");
      }
    },
    []
  );

  const currentActorId = room?.active_user_id ?? userId;

  const resetDemo = useCallback(
    async (scenario?: Scenario) => {
      await updateRoom(() => resetRoom(roomId, currentActorId, scenario));
    },
    [currentActorId, roomId, updateRoom]
  );

  const switchScenario = useCallback(
    async (scenario: Scenario) => {
      await updateRoom(() => switchRoomScenario(roomId, { scenario, actor_id: currentActorId }));
    },
    [currentActorId, roomId, updateRoom]
  );

  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) return;
      const actor = currentActorId;
      // Show the member's own message first, then "thinking" — the message is
      // what triggers the agent, so it must precede the thinking indicator.
      setRoom((prev) => (prev ? appendOptimisticMessage(prev, actor, trimmed) : prev));
      setIsAgentThinking(true);
      setLiveReasoning("");
      setError(null);
      try {
        let nextRoom: RoomState | null = null;
        try {
          // Stream the agent's visible reasoning token-by-token while it thinks;
          // the final event carries the canonical room (with the reply + reasoning).
          for await (const event of streamRoomMessage(roomId, actor, trimmed)) {
            if (event.type === "reasoning") {
              setLiveReasoning((prev) => prev + event.delta);
            } else if (event.type === "done") {
              nextRoom = event.room;
            }
          }
        } catch {
          // Streaming unavailable — fall back to the non-streaming send so the
          // turn never stalls (no live reasoning in this path). If the stream
          // dropped *after* the server already committed the user message, this
          // re-appends it server-side; accepted for the in-memory demo scope
          // (no persistence / multiplayer), and `setRoom` below reconciles to
          // whatever the server returns.
          nextRoom = await sendRoomMessage(roomId, { actor_id: actor, content: trimmed });
        }
        if (nextRoom) setRoom(nextRoom);
      } catch (err) {
        setError(err instanceof Error ? err.message : "房间更新失败");
      } finally {
        setIsAgentThinking(false);
        setLiveReasoning("");
      }
    },
    [currentActorId, roomId]
  );

  const voteForPlan = useCallback(
    async (planId: string, reason = "") => {
      await updateRoom(() => sendRoomVote(roomId, { participant_id: currentActorId, plan_id: planId, reason }));
    },
    [currentActorId, roomId, updateRoom]
  );

  const reactToVenue = useCallback(
    async (venueId: string, reactionType: RoomReactionType, reason = "") => {
      await updateRoom(() =>
        sendRoomReaction(roomId, {
          participant_id: currentActorId,
          venue_id: venueId,
          reaction_type: reactionType,
          reason,
        })
      );
    },
    [currentActorId, roomId, updateRoom]
  );

  const advanceDemo = useCallback(async () => {
    await updateRoom(() => advanceRoom(roomId, currentActorId));
  }, [currentActorId, roomId, updateRoom]);

  const playDemo = useCallback(async () => {
    if (isPlayingDemo) return;
    setIsPlayingDemo(true);
    setError(null);
    try {
      let latest = room;
      for (let index = 0; index < 12; index += 1) {
        if (latest?.stage === "final_plan_ready" || latest?.stage === "done") break;
        const actor = latest?.active_user_id ?? currentActorId;
        const prevRoom = latest;
        // One demo turn is a single LLM call that emits reasoning first, then the
        // member + agent messages together at `done`. The member speech does not
        // exist yet, so show a neutral "generating" indicator and silently buffer
        // the reasoning — the agent "thinking" must not precede the members.
        setIsPreparingTurn(true);
        setIsAgentThinking(false);
        setLiveReasoning("");
        let reasoningBuf = "";
        let nextRoom: RoomState | null = null;
        try {
          // Real Gemini drives the demo (mode=auto); buffer its visible reasoning
          // to replay after the members speak. The final event carries the room.
          for await (const event of streamAdvanceRoom(roomId, actor, "auto")) {
            if (event.type === "reasoning") {
              reasoningBuf += event.delta;
            } else if (event.type === "done") {
              nextRoom = event.room;
            }
          }
        } catch {
          // Streaming unavailable — fall back to the non-streaming advance so the
          // demo never stalls (no buffered reasoning in this path).
          nextRoom = await advanceRoom(roomId, actor, "auto");
        }
        if (!nextRoom) {
          setIsPreparingTurn(false);
          setIsAgentThinking(false);
          setLiveReasoning("");
          break;
        }
        setIsPreparingTurn(false);
        // Reveal new member lines first: commit the room without the trailing
        // agent reply so the members type out before the "thinking" bubble.
        const heldBack = roomWithoutTrailingAgent(prevRoom, nextRoom);
        if (heldBack) {
          setRoom(heldBack.room);
          await sleep(memberRevealMs(heldBack.newMemberCount));
        }
        // Now the members have spoken: show the agent "thinking" and replay the
        // buffered reasoning so it streams in visibly after the member lines.
        setIsAgentThinking(true);
        if (reasoningBuf) {
          await replayReasoning(reasoningBuf, setLiveReasoning);
        } else {
          await sleep(500);
        }
        // Then drop "thinking" and reveal the agent reply (its reasoning stays
        // visible in the message's own panel).
        setIsAgentThinking(false);
        setLiveReasoning("");
        setRoom(nextRoom);
        latest = nextRoom;
        await sleep(demoDelayMs(nextRoom));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "演示播放失败");
    } finally {
      setIsPlayingDemo(false);
      setIsPreparingTurn(false);
      setIsAgentThinking(false);
      setLiveReasoning("");
    }
  }, [currentActorId, isPlayingDemo, room, roomId]);

  const simulateDemo = useCallback(async () => {
    await updateRoom(() => simulateRoom(roomId, currentActorId, room?.scenario));
  }, [currentActorId, room?.scenario, roomId, updateRoom]);

  const executeActivePlan = useCallback(async () => {
    await updateRoom(() => executeRoom(roomId, { actor_id: currentActorId }));
  }, [currentActorId, roomId, updateRoom]);

  return {
    room,
    isLoading,
    isPlayingDemo,
    isAgentThinking,
    isPreparingTurn,
    liveReasoning,
    error,
    reloadRoom: reload,
    resetDemo,
    switchScenario,
    sendMessage,
    voteForPlan,
    reactToVenue,
    advanceDemo,
    playDemo,
    simulateDemo,
    executeActivePlan,
  };
}

function appendOptimisticMessage(room: RoomState, actorId: ParticipantId, content: string): RoomState {
  const actor = room.participants.find((item) => item.id === actorId);
  const message: SharedMessage = {
    id: `optimistic_${room.messages.length + 1}_${Date.now()}`,
    actor_id: actorId,
    actor_name: actor?.name ?? "我",
    actor_avatar: actor?.avatar ?? "",
    type: "user_message",
    content,
    created_at: new Date().toISOString(),
    related_plan_id: null,
  };
  return { ...room, messages: [...room.messages, message] };
}

/**
 * Split a freshly advanced room so member lines reveal before the agent reply:
 * returns the room with the trailing agent message(s) removed, plus how many new
 * member lines that exposes. Returns null when there is nothing to hold back
 * (agent-only turn, or no new member lines vs the previous room).
 */
function roomWithoutTrailingAgent(
  prev: RoomState | null,
  next: RoomState
): { room: RoomState; newMemberCount: number } | null {
  const messages = next.messages;
  let cut = messages.length;
  while (cut > 0 && messages[cut - 1].actor_id === "agent") cut -= 1;
  if (cut === messages.length) return null;
  const prevCount = prev?.messages.length ?? 0;
  if (cut <= prevCount) return null;
  return { room: { ...next, messages: messages.slice(0, cut) }, newMemberCount: cut - prevCount };
}

function memberRevealMs(count: number): number {
  return Math.min(count, 3) * 1100 + 500;
}

function sleep(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function demoDelayMs(room: RoomState) {
  if (room.typing_participants.length > 0) {
    return 1800 + Math.floor(Math.random() * 1700);
  }
  if (room.stage === "agent_planning" || room.stage === "opinions_collected") {
    return 1400 + Math.floor(Math.random() * 900);
  }
  return 1200 + Math.floor(Math.random() * 700);
}

/**
 * Replay buffered reasoning into `liveReasoning` so it appears to stream in after
 * the member lines. The demo delivers reasoning + messages together at the
 * stream's end, so this live reveal is reconstructed client-side. Reveals in ~8
 * steps ~120ms apart (well under ~1300ms total); reuses `sleep` so no timers leak.
 */
async function replayReasoning(reasoning: string, setLiveReasoning: (value: string) => void) {
  const chunk = Math.ceil(reasoning.length / 8);
  for (let cut = chunk; cut < reasoning.length; cut += chunk) {
    setLiveReasoning(reasoning.slice(0, cut));
    await sleep(120);
  }
  setLiveReasoning(reasoning);
}
