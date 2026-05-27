"use client";

import { useCallback, useRef, useEffect } from "react";
import { useChat } from "@/hooks/useChat";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatStream } from "@/components/chat/ChatStream";
import { PlanCard } from "@/components/plan/PlanCard";
import { MapView } from "@/components/map/MapView";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { Button } from "@/components/ui/button";
import { RotateCcw, MapPin } from "lucide-react";
import type { Scenario } from "@/lib/types";

export default function HomePage() {
  const {
    messages,
    events,
    plan,
    status,
    mapData,
    sendMessage,
    approvePlan,
    reset,
  } = useChat();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, events]);

  const handleSubmit = useCallback(
    (message: string, scenario: Scenario, homeLocation: [number, number]) => {
      sendMessage(message, scenario, homeLocation);
    },
    [sendMessage]
  );

  const handleApprove = useCallback(() => {
    approvePlan(true);
  }, [approvePlan]);

  const handleReject = useCallback(() => {
    reset();
  }, [reset]);

  const isStreaming = status === "planning" || status === "executing";

  return (
    <div className="flex h-full">
      {/* Left Panel: Chat + Plan */}
      <div className="flex w-full flex-col border-r border-zinc-200 lg:w-[480px] xl:w-[540px]">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
          <div className="flex items-center gap-2">
            <MapPin className="h-5 w-5 text-orange-500" />
            <h1 className="text-lg font-semibold text-zinc-900">
              Weekend Planner
            </h1>
          </div>
          {status !== "idle" && (
            <Button
              variant="ghost"
              size="sm"
              onClick={reset}
              aria-label="重新开始"
            >
              <RotateCcw className="mr-1.5 h-4 w-4" />
              重新开始
            </Button>
          )}
        </header>

        {/* Messages Area */}
        <div className="custom-scrollbar flex-1 overflow-y-auto px-5 py-4">
          {status === "idle" && messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="rounded-full bg-orange-100 p-4">
                <MapPin className="h-8 w-8 text-orange-500" />
              </div>
              <h2 className="mt-4 text-xl font-semibold text-zinc-900">
                周末去哪玩？
              </h2>
              <p className="mt-2 max-w-xs text-sm text-zinc-500">
                告诉我你的需求，AI 帮你规划完美的周末活动方案
              </p>
            </div>
          )}

          <div className="space-y-3">
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                timestamp={msg.timestamp}
              />
            ))}

            <ChatStream events={events} isStreaming={isStreaming} />

            {plan && (
              <div className="mt-4">
                <PlanCard
                  plan={plan}
                  status={status}
                  onApprove={handleApprove}
                  onReject={handleReject}
                />
              </div>
            )}

            {status === "executing" && (
              <div className="flex items-center justify-center gap-2 py-4">
                <LoadingSpinner size="sm" />
                <span className="text-sm text-zinc-500">正在执行预订...</span>
              </div>
            )}
          </div>

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t border-zinc-200 px-5 py-4">
          <ChatInput
            onSubmit={handleSubmit}
            disabled={status !== "idle" && status !== "done" && status !== "error"}
          />
        </div>
      </div>

      {/* Right Panel: Map */}
      <div className="hidden flex-1 flex-col bg-zinc-50 p-4 lg:flex">
        <div className="mb-3 flex items-center gap-2">
          <h2 className="text-sm font-medium text-zinc-700">活动地图</h2>
          {mapData && (
            <span className="text-xs text-zinc-400">
              {mapData.venues.length} 个活动地点
              {mapData.spatialVenues.length > 0 && ` / ${mapData.spatialVenues.length} 个周边场所`}
            </span>
          )}
        </div>
        <MapView mapData={mapData} className="h-full w-full flex-1" />
      </div>
    </div>
  );
}
