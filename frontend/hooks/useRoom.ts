"use client";

import { useCallback, useEffect, useState } from "react";
import {
  executeRoom,
  fetchRoom,
  resetRoom,
  sendRoomMessage,
  sendRoomReaction,
  sendRoomVote,
  simulateRoom,
} from "@/lib/api";
import type { ParticipantId, RoomReactionType, RoomState } from "@/lib/types";

interface UseRoomReturn {
  room: RoomState | null;
  isLoading: boolean;
  error: string | null;
  reloadRoom: () => Promise<void>;
  resetDemo: () => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  voteForPlan: (planId: string, reason?: string) => Promise<void>;
  reactToVenue: (venueId: string, reactionType: RoomReactionType, reason?: string) => Promise<void>;
  simulateDemo: () => Promise<void>;
  executeActivePlan: () => Promise<void>;
}

export function useRoom(roomId: string, userId: ParticipantId): UseRoomReturn {
  const [room, setRoom] = useState<RoomState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
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

  const resetDemo = useCallback(async () => {
    await updateRoom(() => resetRoom(roomId, userId));
  }, [roomId, updateRoom, userId]);

  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) return;
      await updateRoom(() => sendRoomMessage(roomId, { actor_id: userId, content: trimmed }));
    },
    [roomId, updateRoom, userId]
  );

  const voteForPlan = useCallback(
    async (planId: string, reason = "") => {
      await updateRoom(() => sendRoomVote(roomId, { participant_id: userId, plan_id: planId, reason }));
    },
    [roomId, updateRoom, userId]
  );

  const reactToVenue = useCallback(
    async (venueId: string, reactionType: RoomReactionType, reason = "") => {
      await updateRoom(() =>
        sendRoomReaction(roomId, {
          participant_id: userId,
          venue_id: venueId,
          reaction_type: reactionType,
          reason,
        })
      );
    },
    [roomId, updateRoom, userId]
  );

  const simulateDemo = useCallback(async () => {
    await updateRoom(() => simulateRoom(roomId, userId));
  }, [roomId, updateRoom, userId]);

  const executeActivePlan = useCallback(async () => {
    await updateRoom(() => executeRoom(roomId, { actor_id: userId }));
  }, [roomId, updateRoom, userId]);

  return {
    room,
    isLoading,
    error,
    reloadRoom: reload,
    resetDemo,
    sendMessage,
    voteForPlan,
    reactToVenue,
    simulateDemo,
    executeActivePlan,
  };
}
