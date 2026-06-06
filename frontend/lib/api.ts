import type {
  PlanApproveRequest,
  PlanCreateRequest,
  PlanEvent,
  PlanEventType,
  PlanFeedbackRequest,
  PlanFeedbackResponse,
  RoomExecuteRequest,
  RoomMessageRequest,
  RoomReactionRequest,
  RoomScenarioRequest,
  RoomState,
  RoomVoteRequest,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function* parseSSEStream(
  response: Response
): AsyncGenerator<PlanEvent> {
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  if (!response.body) {
    throw new Error("No response body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split(/\r\n\r\n|\n\n|\r\r/);
      buffer = parts.pop() || "";

      for (const part of parts) {
        const lines = part.split(/\r\n|\n|\r/);
        let eventType = "";
        let eventData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7);
          } else if (line.startsWith("data: ")) {
            eventData += line.slice(6);
          }
        }

        if (eventData) {
          try {
            const parsed = JSON.parse(eventData) as Record<string, unknown>;
            const event: PlanEvent = {
              type: ((parsed.type as string) || eventType || "unknown") as PlanEventType,
              data: (parsed.data as Record<string, unknown>) || parsed,
              timestamp: new Date().toISOString(),
            };
            yield event;
          } catch {
            // Skip malformed events
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function* streamPlanCreation(
  request: PlanCreateRequest
): AsyncGenerator<PlanEvent> {
  const response = await fetch(`${API_BASE}/api/plan/create`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
  });

  yield* parseSSEStream(response);
}

export async function* streamPlanApproval(
  request: PlanApproveRequest
): AsyncGenerator<PlanEvent> {
  const response = await fetch(`${API_BASE}/api/plan/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
  });

  yield* parseSSEStream(response);
}

export async function sendPlanFeedback(
  request: PlanFeedbackRequest
): Promise<PlanFeedbackResponse> {
  const response = await fetch(`${API_BASE}/api/plan/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Feedback failed: HTTP ${response.status}`);
  }

  return response.json() as Promise<PlanFeedbackResponse>;
}

export async function checkHealth(): Promise<{
  status: string;
  providers: Record<string, boolean>;
}> {
  const response = await fetch(`${API_BASE}/api/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}

async function parseRoomResponse(response: Response): Promise<RoomState> {
  if (!response.ok) {
    throw new Error(`Room request failed: HTTP ${response.status}`);
  }
  return response.json() as Promise<RoomState>;
}

export async function fetchRoom(roomId: string, userId: string): Promise<RoomState> {
  const response = await fetch(`${API_BASE}/api/room/${roomId}?user=${encodeURIComponent(userId)}`);
  return parseRoomResponse(response);
}

export async function resetRoom(roomId: string, userId: string, scenario?: string): Promise<RoomState> {
  const params = new URLSearchParams({ user: userId });
  if (scenario) params.set("scenario", scenario);
  const response = await fetch(`${API_BASE}/api/room/${roomId}/reset?${params.toString()}`, { method: "POST" });
  return parseRoomResponse(response);
}

export async function switchRoomScenario(roomId: string, request: RoomScenarioRequest): Promise<RoomState> {
  const response = await fetch(`${API_BASE}/api/room/${roomId}/scenario`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseRoomResponse(response);
}

export async function advanceRoom(
  roomId: string,
  userId: string,
  mode?: "auto" | "scripted" | "llm"
): Promise<RoomState> {
  const params = new URLSearchParams({ user: userId });
  if (mode) params.set("mode", mode);
  const response = await fetch(`${API_BASE}/api/room/${roomId}/advance?${params.toString()}`, {
    method: "POST",
  });
  return parseRoomResponse(response);
}

export type RoomStreamEvent =
  | { type: "reasoning"; delta: string }
  | { type: "done"; room: RoomState };

/**
 * Parse a room SSE stream into `reasoning` deltas followed by a final `done`
 * event carrying the full room. Throws on an `error` event so callers can fall
 * back to the non-streaming path.
 */
async function* parseRoomStream(response: Response): AsyncGenerator<RoomStreamEvent> {
  if (!response.ok || !response.body) {
    throw new Error(`Stream failed: HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split(/\r\n\r\n|\n\n|\r\r/);
      buffer = parts.pop() || "";

      for (const part of parts) {
        let eventType = "";
        let dataStr = "";
        for (const line of part.split(/\r\n|\n|\r/)) {
          if (line.startsWith("event: ")) eventType = line.slice(7);
          else if (line.startsWith("data: ")) dataStr += line.slice(6);
        }
        if (!dataStr) continue;

        let data: Record<string, unknown>;
        try {
          data = JSON.parse(dataStr) as Record<string, unknown>;
        } catch {
          continue;
        }
        if (eventType === "error") {
          throw new Error((data.message as string) || "room stream error");
        }
        if (eventType === "reasoning" && typeof data.delta === "string") {
          yield { type: "reasoning", delta: data.delta };
        } else if (eventType === "done" && data.room) {
          yield { type: "done", room: data.room as RoomState };
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Advance the room over SSE, streaming the agent's visible reasoning deltas and
 * finally the full updated room state. Throws on transport/HTTP errors so the
 * caller can fall back to the non-streaming advance.
 */
export async function* streamAdvanceRoom(
  roomId: string,
  userId: string,
  mode: "auto" | "scripted" | "llm" = "auto"
): AsyncGenerator<RoomStreamEvent> {
  const params = new URLSearchParams({ user: userId, mode });
  const response = await fetch(`${API_BASE}/api/room/${roomId}/advance/stream?${params.toString()}`, {
    method: "POST",
    headers: { Accept: "text/event-stream" },
  });
  yield* parseRoomStream(response);
}

/**
 * Send a participant message over SSE: the backend commits the message, streams
 * the agent's visible reasoning, then emits the full updated room. Throws on
 * transport/HTTP errors so the caller can fall back to the non-streaming send.
 */
export async function* streamRoomMessage(
  roomId: string,
  actorId: string,
  content: string
): AsyncGenerator<RoomStreamEvent> {
  const response = await fetch(`${API_BASE}/api/room/${roomId}/message/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ actor_id: actorId, content }),
  });
  yield* parseRoomStream(response);
}

export async function sendRoomMessage(roomId: string, request: RoomMessageRequest): Promise<RoomState> {
  const response = await fetch(`${API_BASE}/api/room/${roomId}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseRoomResponse(response);
}

export async function sendRoomVote(roomId: string, request: RoomVoteRequest): Promise<RoomState> {
  const response = await fetch(`${API_BASE}/api/room/${roomId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseRoomResponse(response);
}

export async function sendRoomReaction(roomId: string, request: RoomReactionRequest): Promise<RoomState> {
  const response = await fetch(`${API_BASE}/api/room/${roomId}/reaction`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseRoomResponse(response);
}

export async function simulateRoom(roomId: string, userId: string, scenario?: string): Promise<RoomState> {
  const params = new URLSearchParams({ user: userId });
  if (scenario) params.set("scenario", scenario);
  const response = await fetch(`${API_BASE}/api/room/${roomId}/simulate?${params.toString()}`, {
    method: "POST",
  });
  return parseRoomResponse(response);
}

export async function executeRoom(roomId: string, request: RoomExecuteRequest): Promise<RoomState> {
  const response = await fetch(`${API_BASE}/api/room/${roomId}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseRoomResponse(response);
}
