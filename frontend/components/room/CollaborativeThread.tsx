"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PlanCanvas } from "@/components/canvas/PlanCanvas";
import { GroupMemoryPanel } from "./GroupMemoryPanel";
import { PlanOptionCards } from "./PlanOptionCards";
import { RoomMessageList } from "./RoomMessageList";
import { VenueReactionBar } from "./VenueReactionBar";
import type { ParticipantId, PlanStatus, RoomReactionType, RoomState } from "@/lib/types";

interface CollaborativeThreadProps {
  room: RoomState;
  activeUserId: ParticipantId;
  selectedPlanId: string;
  selectedTimelineId: string | null;
  onSelectTimeline: (timelineId: string, markerId: string) => void;
  onSelectPlan: (planId: string) => void;
  onVote: (planId: string) => void;
  onReact: (venueId: string, reactionType: RoomReactionType, reason: string) => void;
  onSendMessage: (content: string) => void;
  onExecute: () => void;
}

export function CollaborativeThread({
  room,
  activeUserId,
  selectedPlanId,
  selectedTimelineId,
  onSelectTimeline,
  onSelectPlan,
  onVote,
  onReact,
  onSendMessage,
  onExecute,
}: CollaborativeThreadProps) {
  const [draft, setDraft] = useState("");
  const activeOption = room.plan_options.find((item) => item.option_id === selectedPlanId) ?? room.plan_options[0];
  const activeCanvas = activeOption.plan_canvas;
  const planStatus: PlanStatus = room.execution_state.status === "completed" ? "done" : "plan_ready";
  const isHost = activeUserId === room.host_user_id;
  const viewingConsensusPlan = activeOption.option_id === room.active_plan_id;

  return (
    <main className="custom-scrollbar h-full overflow-y-auto bg-zinc-50/80">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4 xl:p-6">
        <RoomMessageList messages={room.messages} participants={room.participants} />

        <form
          className="flex gap-2 rounded-lg border border-zinc-100 bg-white p-3 shadow-sm shadow-zinc-100"
          onSubmit={(event) => {
            event.preventDefault();
            onSendMessage(draft);
            setDraft("");
          }}
        >
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="说出你的偏好，例如：不要火锅、想拍照、早点回家"
            className="min-w-0 flex-1 rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-orange-400"
          />
          <Button type="submit">
            <Send className="mr-1.5 h-4 w-4" />
            发送
          </Button>
        </form>

        <PlanOptionCards
          options={room.plan_options}
          activePlanId={selectedPlanId}
          activeUserId={activeUserId}
          onSelectPlan={onSelectPlan}
          onVote={onVote}
        />

        <GroupMemoryPanel memory={room.group_memory} />

        <VenueReactionBar timeline={activeCanvas.timeline} reactions={room.reactions} onReact={onReact} />

        <PlanCanvas
          canvas={activeCanvas}
          status={planStatus}
          selectedTimelineId={selectedTimelineId}
          onSelectTimeline={onSelectTimeline}
          onFeedback={(message) => onSendMessage(message)}
          onApprove={onExecute}
          onReject={() => onSelectPlan("plan_c")}
          approvalEnabled={isHost && viewingConsensusPlan}
          approveLabel={isHost ? "确认并执行" : "等待小红确认"}
          approvalHint={approvalHint(isHost, viewingConsensusPlan, room.consensus.summary)}
          embedded
        />
      </div>
    </main>
  );
}

function approvalHint(isHost: boolean, viewingConsensusPlan: boolean, consensusSummary: string) {
  if (!isHost) return "只有发起人小红可以确认执行。";
  if (!viewingConsensusPlan) return "当前正在查看备选方案，请切回推荐折中方案后执行。";
  return consensusSummary;
}
