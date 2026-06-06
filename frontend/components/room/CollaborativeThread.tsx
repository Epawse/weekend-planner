"use client";

import { useState } from "react";
import { Play, Send } from "lucide-react";
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
  selectedPlanId: string | null;
  selectedTimelineId: string | null;
  isPlayingDemo: boolean;
  onSelectTimeline: (timelineId: string, markerId: string) => void;
  onSelectPlan: (planId: string) => void;
  onVote: (planId: string) => void;
  onReact: (venueId: string, reactionType: RoomReactionType, reason: string) => void;
  onSendMessage: (content: string) => void;
  onPlayDemo: () => void;
  onExecute: () => void;
}

export function CollaborativeThread({
  room,
  activeUserId,
  selectedPlanId,
  selectedTimelineId,
  isPlayingDemo,
  onSelectTimeline,
  onSelectPlan,
  onVote,
  onReact,
  onSendMessage,
  onPlayDemo,
  onExecute,
}: CollaborativeThreadProps) {
  const [draft, setDraft] = useState("");
  const activeOption =
    room.plan_options.find((item) => item.option_id === selectedPlanId) ??
    room.plan_options.find((item) => item.option_id === room.active_plan_id) ??
    room.plan_options[0] ??
    null;
  const activeCanvas = activeOption?.plan_canvas ?? null;
  const planStatus: PlanStatus = room.execution_state.status === "completed" ? "done" : "plan_ready";
  const isHost = activeUserId === room.host_user_id;
  const viewingConsensusPlan = Boolean(activeOption && activeOption.option_id === room.active_plan_id);
  const showMemory = room.group_memory.confirmed_constraints.length > 0 || room.group_memory.soft_preferences.length > 0;
  const showReactions = Boolean(activeCanvas && ["voting", "consensus_ready", "final_plan_ready", "done"].includes(room.stage));
  const showFinalCanvas = Boolean(activeCanvas && ["final_plan_ready", "done", "executing"].includes(room.stage));

  return (
    <main className="flex h-full min-h-0 flex-col bg-zinc-50/80">
      <header className="border-b border-zinc-200 bg-white px-4 py-3 xl:px-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-base font-semibold text-zinc-900">{room.stage_title}</div>
            <p className="mt-0.5 text-sm text-zinc-500">{room.stage_description}</p>
          </div>
          <div className="shrink-0 rounded-md bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-600">
            {stageLabel(room.stage)}
          </div>
        </div>
      </header>

      <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4 xl:p-6">
          {room.stage === "idle" ? (
            <EmptyRoomState scenario={room.scenario} isPlayingDemo={isPlayingDemo} onPlayDemo={onPlayDemo} />
          ) : (
            <RoomMessageList
              messages={room.messages}
              participants={room.participants}
              typingParticipants={room.typing_participants}
            />
          )}

          {room.plan_options.length > 0 && (
            <>
              <StageDivider
                eyebrow="第 1 步"
                title={room.scenario === "family" ? "先给家庭 3 个方向" : "先给大家 3 个方向"}
                detail="点击方案会切换右侧地图和来源；投票头像会进入左侧概览。"
              />
              <PlanOptionCards
                options={room.plan_options}
                activePlanId={activeOption?.option_id ?? null}
                activeUserId={activeUserId}
                onSelectPlan={onSelectPlan}
                onVote={onVote}
              />
            </>
          )}

          {showMemory && (
            <>
              <StageDivider
                eyebrow={room.stage === "options_ready" ? "第 2 步" : "共识状态"}
                title={room.stage === "options_ready" ? "等待投票和地点反应" : consensusTitle(room)}
                detail={room.consensus.summary}
              />
              <GroupMemoryPanel memory={room.group_memory} />
            </>
          )}

          {showReactions && activeCanvas && (
            <VenueReactionBar timeline={activeCanvas.timeline} reactions={room.reactions} onReact={onReact} />
          )}

          {room.stage === "consensus_ready" && (
            <StageDivider
              eyebrow="第 3 步"
              title={room.scenario === "family" ? "家庭共识已形成" : "Agent 已生成折中结论"}
              detail={
                room.scenario === "family"
                  ? "B 方案同时满足清淡少油、儿童椅、少走路和早点回家。"
                  : "最终将采用 B 折中推荐：避开火锅，保留室内、拍照和可选咖啡。"
              }
            />
          )}

          {showFinalCanvas && activeCanvas && (
            <>
              <StageDivider
                eyebrow={room.execution_state.status === "completed" ? "第 4 步" : "最终方案"}
                title={room.execution_state.status === "completed" ? "执行结果已完成" : finalPlanTitle(room)}
                detail={finalPlanDetail(room)}
              />
              <PlanCanvas
                canvas={activeCanvas}
                status={planStatus}
                selectedTimelineId={selectedTimelineId}
                onSelectTimeline={onSelectTimeline}
                onFeedback={(message) => onSendMessage(message)}
                onApprove={onExecute}
                onReject={() => onSelectPlan("plan_c")}
                approvalEnabled={isHost && viewingConsensusPlan && room.stage === "final_plan_ready"}
                approveLabel={isHost ? "确认并执行" : `等待${room.scenario === "family" ? "小明" : "小红"}确认`}
                approvalHint={approvalHint(isHost, viewingConsensusPlan, room.consensus.summary, room.scenario)}
                embedded
              />
            </>
          )}
        </div>
      </div>

      <form
        className="border-t border-zinc-200 bg-white p-3 xl:px-6"
        onSubmit={(event) => {
          event.preventDefault();
          onSendMessage(draft);
          setDraft("");
        }}
      >
        <div className="mx-auto flex max-w-6xl gap-2">
          <input
            value={draft}
            disabled={isPlayingDemo}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={composerPlaceholder(room.scenario)}
            className="min-w-0 flex-1 rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-orange-400 disabled:bg-zinc-50"
          />
          <Button type="submit" disabled={isPlayingDemo}>
            <Send className="mr-1.5 h-4 w-4" />
            发送
          </Button>
        </div>
      </form>
    </main>
  );
}

function EmptyRoomState({
  scenario,
  isPlayingDemo,
  onPlayDemo,
}: {
  scenario: RoomState["scenario"];
  isPlayingDemo: boolean;
  onPlayDemo: () => void;
}) {
  return (
    <section className="rounded-lg border border-zinc-100 bg-white p-6 shadow-sm shadow-zinc-100">
      <div className="max-w-2xl">
        <div className="text-xl font-semibold text-zinc-950">一起把周末安排好</div>
        <p className="mt-2 text-sm leading-6 text-zinc-600">
          先输入你的想法，AI 会收集成员偏好、生成多个方案、汇总投票，并在确认后完成预约、订座、备注和分享。
        </p>
        <div className="mt-4 rounded-lg bg-zinc-50 p-3 text-sm leading-6 text-zinc-600">
          输入示例：
          <br />
          {scenario === "family"
            ? "今天下午想和老婆孩子去亲子乐园玩 4 到 6 个小时，孩子 5 岁，老婆最近减肥，别离家太远。"
            : "周末想和朋友聚一聚，吃点好的再找个地方玩，别太远。"}
        </div>
        <Button type="button" className="mt-4" onClick={onPlayDemo} disabled={isPlayingDemo}>
          <Play className="mr-1.5 h-4 w-4" />
          {isPlayingDemo ? "演示进行中" : "自动演示动作"}
        </Button>
      </div>
    </section>
  );
}

function StageDivider({ eyebrow, title, detail }: { eyebrow: string; title: string; detail: string }) {
  return (
    <section className="rounded-lg border border-zinc-100 bg-white px-4 py-3 shadow-sm shadow-zinc-100">
      <div className="text-xs font-medium text-orange-600">{eyebrow}</div>
      <div className="mt-1 text-sm font-semibold text-zinc-900">{title}</div>
      <p className="mt-1 text-xs leading-5 text-zinc-500">{detail}</p>
    </section>
  );
}

function stageLabel(stage: RoomState["stage"]) {
  return {
    idle: "未开始",
    host_prompted: "发起需求",
    agent_planning: "任务拆解",
    members_invited: "邀请成员",
    members_typing: "成员输入",
    opinions_collected: "意见收集",
    options_ready: "方案候选",
    voting: "投票中",
    consensus_ready: "共识",
    final_plan_ready: "最终方案",
    executing: "执行中",
    done: "已完成",
  }[stage];
}

function consensusTitle(room: RoomState) {
  if (room.stage === "voting") return "第 2 步：投票正在形成共识";
  if (room.stage === "consensus_ready") return "第 3 步：Agent 汇总共识";
  return "当前群体记忆";
}

function finalPlanTitle(room: RoomState) {
  if (room.scenario === "family") return "最终采用：B 早点回家优先";
  return "最终采用：B 折中推荐";
}

function finalPlanDetail(room: RoomState) {
  if (room.execution_state.status === "completed") return room.execution_state.summary;
  if (room.scenario === "family") {
    return "原因：2/2 已确认，保留亲子活动，晚餐清淡少油，儿童椅已备注，收尾可跳过。";
  }
  return "原因：3/4 支持，避开火锅，保留室内、拍照和可选咖啡。";
}

function composerPlaceholder(scenario: RoomState["scenario"]) {
  if (scenario === "family") return "说出家庭反馈，例如：别太油、早点回家、少排队";
  return "说出你的偏好，例如：不要火锅、想拍照、早点回家";
}

function approvalHint(isHost: boolean, viewingConsensusPlan: boolean, consensusSummary: string, scenario: RoomState["scenario"]) {
  if (!isHost) return `只有发起人${scenario === "family" ? "小明" : "小红"}可以确认执行。`;
  if (!viewingConsensusPlan) return "当前正在查看备选方案，请切回推荐方案后执行。";
  return consensusSummary;
}
