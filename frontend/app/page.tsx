"use client";

import { useCallback, useMemo, useState } from "react";
import { CollaborativeThread } from "@/components/room/CollaborativeThread";
import { RoomSidebar } from "@/components/room/RoomSidebar";
import { EvidencePanel } from "@/components/evidence/EvidencePanel";
import { MapView } from "@/components/map/MapView";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { Button } from "@/components/ui/button";
import { useRoom } from "@/hooks/useRoom";
import { cn } from "@/lib/utils";
import { AlertTriangle, FileText, Map, RefreshCw } from "lucide-react";
import type { ParticipantId, RoomActiveView, RoomReactionType, Scenario } from "@/lib/types";

type RightTab = "map" | "sources";

export default function HomePage() {
  const [{ roomId, userId }] = useState(initialRouteState);
  const {
    room,
    isLoading,
    isPlayingDemo,
    error,
    reloadRoom,
    resetDemo,
    switchScenario,
    sendMessage,
    voteForPlan,
    reactToVenue,
    playDemo,
    executeActivePlan,
  } = useRoom(roomId, userId);

  const [rightTab, setRightTab] = useState<RightTab>("map");
  const [activeView, setActiveView] = useState<RoomActiveView>("chat");
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [selectedTimelineId, setSelectedTimelineId] = useState<string | null>(null);
  const [selectedMarkerId, setSelectedMarkerId] = useState<string | null>(null);

  const selectedOption = useMemo(() => {
    if (!room) return null;
    if (room.plan_options.length === 0) return null;
    const displayPlanId = room.plan_options.some((option) => option.option_id === selectedPlanId)
      ? selectedPlanId
      : room.active_plan_id;
    return (
      room.plan_options.find((option) => option.option_id === displayPlanId) ??
      room.plan_options.find((option) => option.option_id === room.active_plan_id) ??
      room.plan_options[0]
    );
  }, [room, selectedPlanId]);

  const activeCanvas = selectedOption?.plan_canvas ?? null;
  const showRightPanel = Boolean(activeCanvas && activeView !== "chat");
  const effectiveTimelineId = selectedTimelineId ?? activeCanvas?.timeline[0]?.id ?? null;
  const effectiveMarkerId = selectedMarkerId ?? activeCanvas?.timeline[0]?.map_marker_id ?? null;

  const handleSelectPlan = useCallback((planId: string) => {
    setSelectedPlanId(planId);
    setSelectedTimelineId(null);
    setSelectedMarkerId(null);
    setRightTab("map");
  }, []);

  const handleVote = useCallback(
    async (planId: string) => {
      setSelectedPlanId(planId);
      await voteForPlan(planId);
    },
    [voteForPlan]
  );

  const handleReact = useCallback(
    async (venueId: string, reactionType: RoomReactionType, reason: string) => {
      await reactToVenue(venueId, reactionType, reason);
      setRightTab("sources");
    },
    [reactToVenue]
  );

  const handleSelectTimeline = useCallback((timelineId: string, markerId: string) => {
    setSelectedTimelineId(timelineId);
    setSelectedMarkerId(markerId);
    setRightTab("map");
  }, []);

  const handleSelectMarker = useCallback(
    (markerId: string) => {
      setSelectedMarkerId(markerId);
      const marker = activeCanvas?.map.markers.find((item) => item.id === markerId);
      if (marker) {
        setSelectedTimelineId(marker.timeline_item_id);
      }
    },
    [activeCanvas?.map.markers]
  );

  const handleSelectEvidence = useCallback((timelineId: string | null, markerId: string | null) => {
    if (timelineId) setSelectedTimelineId(timelineId);
    if (markerId) {
      setSelectedMarkerId(markerId);
      setRightTab("map");
    }
  }, []);

  if (isLoading && !room) {
    return (
      <div className="flex h-full items-center justify-center bg-zinc-50">
        <div className="flex items-center gap-2 text-sm text-zinc-500">
          <LoadingSpinner size="sm" />
          正在加载协作房间...
        </div>
      </div>
    );
  }

  if (!room) {
    return (
      <div className="flex h-full items-center justify-center bg-zinc-50 p-8 text-center">
        <div>
          <AlertTriangle className="mx-auto h-8 w-8 text-amber-500" />
          <h1 className="mt-3 text-lg font-semibold text-zinc-900">协作房间加载失败</h1>
          <p className="mt-2 text-sm text-zinc-500">{error ?? "没有可用房间状态。"}</p>
          <Button type="button" className="mt-4" onClick={reloadRoom}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            重试
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "grid h-full min-h-0 grid-cols-1 bg-zinc-100",
        showRightPanel
          ? "lg:grid-cols-[320px_minmax(0,1fr)_420px] xl:grid-cols-[340px_minmax(0,1fr)_460px]"
          : "lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[340px_minmax(0,1fr)]"
      )}
    >
      <RoomSidebar
        room={room}
        activeUserId={room.active_user_id}
        isPlayingDemo={isPlayingDemo}
        onPlayDemo={() => {
          setActiveView("chat");
          void playDemo();
        }}
        onReset={(scenario) => {
          setActiveView("chat");
          setSelectedPlanId(null);
          setSelectedTimelineId(null);
          setSelectedMarkerId(null);
          void resetDemo(scenario);
        }}
        onScenarioChange={(scenario) => {
          setActiveView("chat");
          setSelectedPlanId(null);
          setSelectedTimelineId(null);
          setSelectedMarkerId(null);
          void switchScenario(scenario);
        }}
      />

      <CollaborativeThread
        room={room}
        activeUserId={room.active_user_id}
        activeView={activeView}
        selectedPlanId={selectedOption?.option_id ?? null}
        selectedTimelineId={effectiveTimelineId}
        isPlayingDemo={isPlayingDemo}
        onViewChange={setActiveView}
        onSelectTimeline={handleSelectTimeline}
        onSelectPlan={handleSelectPlan}
        onVote={handleVote}
        onReact={handleReact}
        onSendMessage={sendMessage}
        onPlayDemo={() => {
          setActiveView("chat");
          void playDemo();
        }}
        onExecute={executeActivePlan}
      />

      {showRightPanel && activeCanvas && (
        <aside className="hidden min-h-0 border-l border-zinc-200 bg-white lg:flex lg:flex-col">
          <div className="flex border-b border-zinc-200 p-2">
            {[
              { id: "map" as const, label: "地图", icon: Map },
              { id: "sources" as const, label: "依据", icon: FileText },
            ].map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setRightTab(tab.id)}
                  className={cn(
                    "flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium",
                    rightTab === tab.id ? "bg-orange-50 text-orange-700" : "text-zinc-600 hover:bg-zinc-100"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          <div className="border-b border-zinc-200 px-4 py-2 text-xs text-zinc-500">
            当前显示：
            <span className="font-medium text-zinc-800">
              {room.stage === "final_plan_ready" || room.stage === "done"
                ? selectedOption?.option_id === room.active_plan_id
                  ? "最终方案"
                  : selectedOption?.label
                : selectedOption?.label}
            </span>
          </div>

          <div className="min-h-0 flex-1">
            {rightTab === "map" ? (
              <div className="h-full p-3">
                <MapView
                  mapData={null}
                  planCanvas={activeCanvas}
                  selectedMarkerId={effectiveMarkerId}
                  onSelectMarker={handleSelectMarker}
                  className="h-full w-full"
                />
              </div>
            ) : (
              <EvidencePanel
                evidence={activeCanvas.evidence_cards}
                rejectedOptions={activeCanvas.rejected_options}
                selectedTimelineId={effectiveTimelineId}
                onSelectEvidence={handleSelectEvidence}
              />
            )}
          </div>
        </aside>
      )}
    </div>
  );
}

function normalizeUser(value: string | null): ParticipantId {
  if (value === "green" || value === "blue" || value === "pink" || value === "wife" || value === "red") {
    return value;
  }
  return "red";
}

function normalizeScenario(value: string | null): Scenario {
  return value === "family" ? "family" : "friends";
}

function initialRouteState(): { roomId: string; userId: ParticipantId } {
  if (typeof window === "undefined") {
    return { roomId: "demo_friends_room", userId: "red" };
  }
  const params = new URLSearchParams(window.location.search);
  const scenario = normalizeScenario(params.get("scenario"));
  return {
    roomId: params.get("room") || (scenario === "family" ? "demo_family_room" : "demo_friends_room"),
    userId: normalizeUser(params.get("user")),
  };
}
