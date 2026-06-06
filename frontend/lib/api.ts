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

export async function resetRoom(roomId: string, userId: string): Promise<RoomState> {
  const response = await fetch(`${API_BASE}/api/room/${roomId}/reset?user=${encodeURIComponent(userId)}`, {
    method: "POST",
  });
  return parseRoomResponse(response);
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

export async function simulateRoom(roomId: string, userId: string): Promise<RoomState> {
  const response = await fetch(`${API_BASE}/api/room/${roomId}/simulate?user=${encodeURIComponent(userId)}`, {
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
