import type { PlanCreateRequest, PlanEvent, PlanApproveRequest, PlanEventType } from "./types";

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
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        const lines = part.split("\n");
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
