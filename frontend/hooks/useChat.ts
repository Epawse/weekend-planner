"use client";

import { useState, useCallback, useRef } from "react";
import { streamPlanCreation, streamPlanApproval } from "@/lib/api";
import type {
  Plan,
  PlanEvent,
  PlanStatus,
  Scenario,
  PlanMapData,
  GeoJSONPolygon,
  RouteGeoJSON,
} from "@/lib/types";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

interface UseChatReturn {
  messages: ChatMessage[];
  events: PlanEvent[];
  plan: Plan | null;
  status: PlanStatus;
  mapData: PlanMapData | null;
  sessionId: string | null;
  sendMessage: (message: string, scenario: Scenario, homeLocation: [number, number]) => Promise<void>;
  approvePlan: (approved: boolean) => Promise<void>;
  reset: () => void;
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [events, setEvents] = useState<PlanEvent[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [status, setStatus] = useState<PlanStatus>("idle");
  const [mapData, setMapData] = useState<PlanMapData | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (message: string, scenario: Scenario, homeLocation: [number, number]) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: message,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setStatus("planning");
      setEvents([]);
      setPlan(null);
      setMapData(null);
      setSessionId(null);

      try {
        for await (const event of streamPlanCreation({
          message,
          scenario,
          home_location: homeLocation,
        })) {
          if (abortRef.current?.signal.aborted) break;

          setEvents((prev) => [...prev, event]);

          switch (event.type) {
            case "session": {
              // Capture backend-assigned session_id for later approve/modify calls
              const backendSessionId = event.data.session_id as string;
              if (backendSessionId) {
                setSessionId(backendSessionId);
              }
              break;
            }
            case "thinking": {
              const assistantMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "assistant",
                content: (event.data.message as string) || "正在思考...",
                timestamp: event.timestamp,
              };
              setMessages((prev) => [...prev, assistantMsg]);
              break;
            }
            case "plan_ready": {
              const readyPlan = event.data.plan as Plan;
              if (readyPlan) {
                setPlan(readyPlan);
                setStatus("plan_ready");

                const newMapData: PlanMapData = {
                  isochrone: (event.data.isochrone as GeoJSONPolygon) || null,
                  route: (event.data.route as RouteGeoJSON) || null,
                  venues: readyPlan.activities,
                  home_location: homeLocation,
                };
                setMapData(newMapData);
              }

              // Also capture session_id if present (sent after interrupt detection)
              const sid = event.data.session_id as string;
              if (sid) {
                setSessionId(sid);
              }
              break;
            }
            case "error": {
              setStatus("error");
              const errorMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "assistant",
                content: `出错了: ${(event.data.message as string) || "未知错误"}`,
                timestamp: event.timestamp,
              };
              setMessages((prev) => [...prev, errorMsg]);
              break;
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") {
          setStatus("error");
          const errorMsg: ChatMessage = {
            id: crypto.randomUUID(),
            role: "assistant",
            content: `连接失败: ${err.message}`,
            timestamp: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, errorMsg]);
        }
      }
    },
    []
  );

  const approvePlan = useCallback(
    async (approved: boolean) => {
      if (!sessionId) return;

      setStatus("executing");

      try {
        for await (const event of streamPlanApproval({
          session_id: sessionId,
          approved,
        })) {
          setEvents((prev) => [...prev, event]);

          switch (event.type) {
            case "step_complete": {
              const stepMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "assistant",
                content: `✓ ${(event.data.venue as string) || "步骤完成"}${event.data.confirmation ? ` (${event.data.confirmation})` : ""}`,
                timestamp: event.timestamp,
              };
              setMessages((prev) => [...prev, stepMsg]);
              break;
            }
            case "step_failed": {
              const failMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "assistant",
                content: `✗ ${(event.data.error as string) || "步骤失败"}`,
                timestamp: event.timestamp,
              };
              setMessages((prev) => [...prev, failMsg]);
              break;
            }
            case "all_complete": {
              setStatus("done");
              const doneMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "assistant",
                content: (event.data.summary as string) || "所有预订已完成！",
                timestamp: event.timestamp,
              };
              setMessages((prev) => [...prev, doneMsg]);
              break;
            }
            case "error": {
              setStatus("error");
              break;
            }
          }
        }
      } catch (err) {
        if (err instanceof Error) {
          setStatus("error");
        }
      }
    },
    [sessionId]
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setEvents([]);
    setPlan(null);
    setStatus("idle");
    setMapData(null);
    setSessionId(null);
  }, []);

  return {
    messages,
    events,
    plan,
    status,
    mapData,
    sessionId,
    sendMessage,
    approvePlan,
    reset,
  };
}
