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
  switchRoomScenario,
} from "@/lib/api";
import type { ParticipantId, RoomReactionType, RoomState, Scenario } from "@/lib/types";

interface UseRoomReturn {
  room: RoomState | null;
  isLoading: boolean;
  isPlayingDemo: boolean;
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
      await updateRoom(() => sendRoomMessage(roomId, { actor_id: currentActorId, content: trimmed }));
    },
    [currentActorId, roomId, updateRoom]
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
        const nextRoom = await advanceRoom(roomId, latest?.active_user_id ?? currentActorId);
        setRoom(nextRoom);
        latest = nextRoom;
        await sleep(nextRoom.typing_participants.length > 0 ? 900 : 650);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "演示播放失败");
    } finally {
      setIsPlayingDemo(false);
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

function sleep(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
