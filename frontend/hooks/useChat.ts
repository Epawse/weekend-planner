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
  SpatialVenue,
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
  const homeLocationRef = useRef<[number, number]>([116.481, 39.998]);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (message: string, scenario: Scenario, homeLocation: [number, number]) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      homeLocationRef.current = homeLocation;

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
              const readyPlan = event.data.plan as Plan | undefined;
              if (readyPlan) {
                setPlan(readyPlan);
                setStatus("plan_ready");

                // Extract isochrone GeoJSON from event
                const isochrone = (event.data.isochrone as GeoJSONPolygon) || null;

                // Extract spatial venues from event
                const rawVenues = (event.data.venues as SpatialVenue[]) || [];

                // Build route from plan activities' venue_coords
                const routeCoords: number[][] = [homeLocation];
                for (const activity of readyPlan.activities) {
                  if (activity.venue_coords) {
                    routeCoords.push(activity.venue_coords);
                  }
                }

                const route = routeCoords.length > 1
                  ? {
                      type: "Feature" as const,
                      geometry: {
                        type: "LineString" as const,
                        coordinates: routeCoords,
                      },
                      properties: {
                        total_travel_minutes: readyPlan.total_travel_minutes,
                      },
                    }
                  : null;

                const newMapData: PlanMapData = {
                  isochrone,
                  route,
                  venues: readyPlan.activities,
                  spatialVenues: rawVenues,
                  home_location: homeLocation,
                };
                setMapData(newMapData);
              }

              // Capture session_id if present
              const sid = event.data.session_id as string;
              if (sid) {
                setSessionId(sid);
              }
              break;
            }
            case "interrupted": {
              // Graph is paused waiting for approval -- ensure status reflects this
              setStatus("plan_ready");
              const interruptSid = event.data.session_id as string;
              if (interruptSid) {
                setSessionId(interruptSid);
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
                content: `${(event.data.venue as string) || "步骤完成"}${event.data.confirmation ? ` (${event.data.confirmation})` : ""}`,
                timestamp: event.timestamp,
              };
              setMessages((prev) => [...prev, stepMsg]);
              break;
            }
            case "step_failed": {
              const failMsg: ChatMessage = {
                id: crypto.randomUUID(),
                role: "assistant",
                content: `${(event.data.error as string) || "步骤失败"}`,
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
