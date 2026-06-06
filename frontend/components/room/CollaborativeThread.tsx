"use client";

import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CalendarCheck,
  ChevronDown,
  Play,
  Send,
  Sparkles,
  Ticket,
  Utensils,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { PlanCanvas } from "@/components/canvas/PlanCanvas";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { useTypewriter } from "@/hooks/useTypewriter";
import { cn } from "@/lib/utils";
import { GroupMemoryPanel } from "./GroupMemoryPanel";
import { PlanOptionCards } from "./PlanOptionCards";
import { RoomMessageList } from "./RoomMessageList";
import { VenueReactionBar } from "./VenueReactionBar";
import type {
  ParticipantId,
  PlanStatus,
  RoomActiveView,
  RoomReactionType,
  RoomState,
  Scenario,
} from "@/lib/types";

interface CollaborativeThreadProps {
  room: RoomState;
  activeUserId: ParticipantId;
  activeView: RoomActiveView;
  selectedPlanId: string | null;
  selectedTimelineId: string | null;
  isPlayingDemo: boolean;
  isAgentThinking: boolean;
  liveReasoning: string;
  onViewChange: (view: RoomActiveView) => void;
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
  activeView,
  selectedPlanId,
  selectedTimelineId,
  isPlayingDemo,
  isAgentThinking,
  liveReasoning,
  onViewChange,
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
  const hasOptions = room.plan_options.length > 0;
  const canOpenFinal = Boolean(
    activeCanvas && ["consensus_ready", "final_plan_ready", "done", "executing"].includes(room.stage)
  );

  return (
    <main className="flex h-full min-h-0 flex-col bg-[#f7f7f5]">
      <MainHeader
        room={room}
        activeView={activeView}
        hasOptions={hasOptions}
        canOpenFinal={canOpenFinal}
        onViewChange={onViewChange}
      />

      {activeView === "chat" ? (
        <ChatView
          room={room}
          activeUserId={activeUserId}
          draft={draft}
          isPlayingDemo={isPlayingDemo}
          isAgentThinking={isAgentThinking}
          liveReasoning={liveReasoning}
          hasOptions={hasOptions}
          canOpenFinal={canOpenFinal}
          onDraftChange={setDraft}
          onSendMessage={onSendMessage}
          onPlayDemo={onPlayDemo}
          onViewChange={onViewChange}
        />
      ) : activeView === "plans" ? (
        <PlansView
          room={room}
          activeUserId={activeUserId}
          activeOptionId={activeOption?.option_id ?? null}
          activeCanvas={activeCanvas}
          onSelectPlan={onSelectPlan}
          onVote={onVote}
          onReact={onReact}
          onViewChange={onViewChange}
        />
      ) : (
        <FinalView
          room={room}
          activeCanvas={activeCanvas}
          planStatus={planStatus}
          selectedTimelineId={selectedTimelineId}
          isHost={isHost}
          viewingConsensusPlan={viewingConsensusPlan}
          onSelectTimeline={onSelectTimeline}
          onSelectPlan={onSelectPlan}
          onSendMessage={onSendMessage}
          onExecute={onExecute}
          onViewChange={onViewChange}
        />
      )}
    </main>
  );
}

function MainHeader({
  room,
  activeView,
  hasOptions,
  canOpenFinal,
  onViewChange,
}: {
  room: RoomState;
  activeView: RoomActiveView;
  hasOptions: boolean;
  canOpenFinal: boolean;
  onViewChange: (view: RoomActiveView) => void;
}) {
  const tabs: Array<{ id: RoomActiveView; label: string; disabled?: boolean }> = [
    { id: "chat", label: "对话" },
    { id: "plans", label: "方案", disabled: !hasOptions },
    { id: "final", label: "最终安排", disabled: !canOpenFinal },
  ];
  return (
    <header className="border-b border-zinc-200/80 bg-white/90 px-4 py-3 xl:px-6">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-zinc-950">{headerTitle(room, activeView)}</div>
          <p className="mt-0.5 truncate text-xs text-zinc-500">{headerSubtitle(room, activeView)}</p>
        </div>
        <nav className="flex shrink-0 rounded-lg bg-zinc-100 p-1" aria-label="工作区视图">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              disabled={tab.disabled}
              onClick={() => onViewChange(tab.id)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition",
                activeView === tab.id ? "bg-white text-zinc-950 shadow-sm" : "text-zinc-500 hover:text-zinc-900",
                tab.disabled && "cursor-not-allowed opacity-40 hover:text-zinc-500"
              )}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  );
}

function ChatView({
  room,
  activeUserId,
  draft,
  isPlayingDemo,
  isAgentThinking,
  liveReasoning,
  hasOptions,
  canOpenFinal,
  onDraftChange,
  onSendMessage,
  onPlayDemo,
  onViewChange,
}: {
  room: RoomState;
  activeUserId: ParticipantId;
  draft: string;
  isPlayingDemo: boolean;
  isAgentThinking: boolean;
  liveReasoning: string;
  hasOptions: boolean;
  canOpenFinal: boolean;
  onDraftChange: (value: string) => void;
  onSendMessage: (content: string) => void;
  onPlayDemo: () => void;
  onViewChange: (view: RoomActiveView) => void;
}) {
  const { frames, hiddenIds, tick } = useTypewriter(room.messages, {
    selfId: activeUserId,
    enabled: room.stage !== "idle",
  });
  const scrollSignal = `${room.messages.length}:${room.typing_participants.length}:${tick}:${isAgentThinking ? 1 : 0}:${liveReasoning.length}`;
  const { pinned, scrollToBottom, setScrollNode } = useAutoScroll(scrollSignal);

  const submit = () => {
    onSendMessage(draft);
    onDraftChange("");
    scrollToBottom();
  };

  if (room.stage === "idle" && !isPlayingDemo) {
    return (
      <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full max-w-4xl flex-col justify-center px-4 py-8">
          <section className="text-center">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-orange-50 px-3 py-1 text-xs font-medium text-orange-700">
              <Sparkles className="h-3.5 w-3.5" />
              多人协作式 Weekend Planner
            </div>
            <h1 className="mt-5 text-3xl font-semibold tracking-normal text-zinc-950 md:text-4xl">
              周末想怎么安排？
            </h1>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-zinc-600">
              输入一个想法，AI 会收集成员偏好，生成方案，协助投票，并完成预约、订座和分享。
            </p>
          </section>

          <HeroComposer
            scenario={room.scenario}
            value={draft}
            isPlayingDemo={isPlayingDemo}
            onChange={onDraftChange}
            onSubmit={submit}
            onPlayDemo={onPlayDemo}
          />
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="relative min-h-0 flex-1">
        <div ref={setScrollNode} className="custom-scrollbar h-full overflow-y-auto">
          <div className="mx-auto flex max-w-4xl flex-col gap-4 px-4 py-5">
            <RoomMessageList
              messages={room.messages}
              participants={room.participants}
              typingParticipants={room.typing_participants}
              streaming={frames}
              hiddenIds={hiddenIds}
              agentThinking={isAgentThinking}
              liveReasoning={liveReasoning}
            />

            {hasOptions && (
              <CompactPlanReadyCard
                room={room}
                canOpenFinal={canOpenFinal}
                onViewChange={onViewChange}
              />
            )}
          </div>
        </div>

        {!pinned && (
          <button
            type="button"
            onClick={scrollToBottom}
            aria-label="回到最新消息"
            className="absolute bottom-4 left-1/2 inline-flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-zinc-200 bg-white/95 px-3 py-1.5 text-xs font-medium text-zinc-600 shadow-md shadow-zinc-300/40 backdrop-blur transition hover:text-zinc-900"
          >
            回到最新
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <ChatComposer
        scenario={room.scenario}
        value={draft}
        isPlayingDemo={isPlayingDemo}
        onChange={onDraftChange}
        onSubmit={submit}
        onQuickReply={(text) => {
          onDraftChange("");
          onSendMessage(text);
        }}
      />
    </>
  );
}

function PlansView({
  room,
  activeUserId,
  activeOptionId,
  activeCanvas,
  onSelectPlan,
  onVote,
  onReact,
  onViewChange,
}: {
  room: RoomState;
  activeUserId: ParticipantId;
  activeOptionId: string | null;
  activeCanvas: RoomState["plan_options"][number]["plan_canvas"] | null;
  onSelectPlan: (planId: string) => void;
  onVote: (planId: string) => void;
  onReact: (venueId: string, reactionType: RoomReactionType, reason: string) => void;
  onViewChange: (view: RoomActiveView) => void;
}) {
  return (
    <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4 xl:p-6">
        <section className="rounded-lg bg-white p-5 shadow-sm shadow-zinc-100">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs font-medium text-orange-600">Plan Mode</div>
              <h2 className="mt-1 text-xl font-semibold text-zinc-950">
                {room.scenario === "family" ? "给家庭 3 个可选方向" : "给大家 3 个可选方向"}
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-600">
                {room.scenario === "family"
                  ? "先比较亲子体验、早点回家和雨天备选，再选择最适合今天状态的一套。"
                  : "先比较体验优先、折中推荐和稳妥备选；投票后，AI 会把分歧转成最终安排。"}
              </p>
            </div>
            {["consensus_ready", "final_plan_ready", "done"].includes(room.stage) && (
              <Button type="button" onClick={() => onViewChange("final")}>
                查看最终安排
                <ArrowRight className="ml-1.5 h-4 w-4" />
              </Button>
            )}
          </div>
        </section>

        <PlanOptionCards
          options={room.plan_options}
          activePlanId={activeOptionId}
          activeUserId={activeUserId}
          onSelectPlan={onSelectPlan}
          onVote={onVote}
        />

        <section className="rounded-lg bg-white p-4 shadow-sm shadow-zinc-100">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-zinc-950">当前共识</div>
              <p className="mt-1 text-sm text-zinc-600">{room.consensus.summary}</p>
            </div>
            <div className="rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">
              {room.consensus.current_votes}/{room.scenario === "family" ? 2 : 4} 已支持
            </div>
          </div>
        </section>

        <details className="rounded-lg bg-white p-4 shadow-sm shadow-zinc-100" open>
          <summary className="cursor-pointer text-sm font-semibold text-zinc-950">为什么推荐这个方案</summary>
          <div className="mt-4">
            <GroupMemoryPanel memory={room.group_memory} />
          </div>
        </details>

        {activeCanvas && (
          <VenueReactionBar timeline={activeCanvas.timeline} reactions={room.reactions} onReact={onReact} />
        )}
      </div>
    </div>
  );
}

function FinalView({
  room,
  activeCanvas,
  planStatus,
  selectedTimelineId,
  isHost,
  viewingConsensusPlan,
  onSelectTimeline,
  onSelectPlan,
  onSendMessage,
  onExecute,
  onViewChange,
}: {
  room: RoomState;
  activeCanvas: RoomState["plan_options"][number]["plan_canvas"] | null;
  planStatus: PlanStatus;
  selectedTimelineId: string | null;
  isHost: boolean;
  viewingConsensusPlan: boolean;
  onSelectTimeline: (timelineId: string, markerId: string) => void;
  onSelectPlan: (planId: string) => void;
  onSendMessage: (content: string) => void;
  onExecute: () => void;
  onViewChange: (view: RoomActiveView) => void;
}) {
  if (!activeCanvas) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center p-8 text-center">
        <div>
          <div className="text-lg font-semibold text-zinc-950">还没有最终安排</div>
          <p className="mt-2 text-sm text-zinc-500">先在对话里收集偏好，或进入方案页查看候选。</p>
          <Button type="button" className="mt-4" onClick={() => onViewChange("chat")}>
            返回对话
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4 xl:p-6">
        <section className="rounded-lg bg-white p-5 shadow-sm shadow-zinc-100">
          <button
            type="button"
            className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-zinc-500 hover:text-zinc-900"
            onClick={() => onViewChange("plans")}
          >
            <ArrowLeft className="h-4 w-4" />
            返回方案
          </button>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs font-medium text-orange-600">Execution Mode</div>
              <h2 className="mt-1 text-2xl font-semibold text-zinc-950">{finalPlanTitle(room)}</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">{finalPlanDetail(room)}</p>
            </div>
            <div className="rounded-lg bg-orange-50 px-3 py-2 text-xs font-medium text-orange-800">
              {room.execution_state.status === "completed" ? "已执行" : "待确认执行"}
            </div>
          </div>
        </section>

        <ExecutionHighlights scenario={room.scenario} completed={room.execution_state.status === "completed"} />

        <PlanCanvas
          canvas={activeCanvas}
          status={planStatus}
          selectedTimelineId={selectedTimelineId}
          onSelectTimeline={onSelectTimeline}
          onFeedback={(message) => onSendMessage(message)}
          onApprove={onExecute}
          onReject={() => onSelectPlan("plan_c")}
          approvalEnabled={isHost && viewingConsensusPlan && ["consensus_ready", "final_plan_ready"].includes(room.stage)}
          approveLabel={isHost ? "确认并执行" : `等待${room.scenario === "family" ? "小明" : "小红"}确认`}
          approvalHint={approvalHint(isHost, viewingConsensusPlan, room.consensus.summary, room.scenario)}
          embedded
        />
      </div>
    </div>
  );
}

function HeroComposer({
  scenario,
  value,
  isPlayingDemo,
  onChange,
  onSubmit,
  onPlayDemo,
}: {
  scenario: Scenario;
  value: string;
  isPlayingDemo: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onPlayDemo: () => void;
}) {
  return (
    <form
      className="mx-auto mt-8 w-full max-w-3xl rounded-2xl bg-white p-3 shadow-lg shadow-zinc-200/70"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <textarea
        value={value}
        disabled={isPlayingDemo}
        onChange={(event) => onChange(event.target.value)}
        placeholder={heroPlaceholder(scenario)}
        rows={3}
        className="block max-h-40 min-h-24 w-full resize-none rounded-xl border-0 bg-zinc-50 px-4 py-3 text-sm leading-6 text-zinc-900 outline-none placeholder:text-zinc-400 focus:bg-white focus:ring-2 focus:ring-orange-200 disabled:bg-zinc-50"
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <PromptChips scenario={scenario} onPick={onChange} />
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={onPlayDemo} disabled={isPlayingDemo}>
            <Play className="mr-1.5 h-4 w-4" />
            {isPlayingDemo ? "演示中" : "自动演示"}
          </Button>
          <Button type="submit" disabled={isPlayingDemo}>
            <Send className="mr-1.5 h-4 w-4" />
            发送
          </Button>
        </div>
      </div>
    </form>
  );
}

function ChatComposer({
  scenario,
  value,
  isPlayingDemo,
  onChange,
  onSubmit,
  onQuickReply,
}: {
  scenario: Scenario;
  value: string;
  isPlayingDemo: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onQuickReply: (value: string) => void;
}) {
  return (
    <form
      className="border-t border-zinc-200/80 bg-white/90 p-3"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="mx-auto max-w-3xl">
        <QuickReplies scenario={scenario} onPick={onQuickReply} />
        <div className="mt-2 flex gap-2">
          <input
            value={value}
            disabled={isPlayingDemo}
            onChange={(event) => onChange(event.target.value)}
            placeholder={composerPlaceholder(scenario)}
            className="min-w-0 flex-1 rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm outline-none focus:border-orange-300 focus:bg-white disabled:bg-zinc-50"
          />
          <Button type="submit" disabled={isPlayingDemo}>
            <Send className="mr-1.5 h-4 w-4" />
            发送
          </Button>
        </div>
      </div>
    </form>
  );
}

function CompactPlanReadyCard({
  room,
  canOpenFinal,
  onViewChange,
}: {
  room: RoomState;
  canOpenFinal: boolean;
  onViewChange: (view: RoomActiveView) => void;
}) {
  return (
    <section className="rounded-2xl bg-white p-4 shadow-sm shadow-zinc-100">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-950">
            <Sparkles className="h-4 w-4 text-orange-600" />
            已生成 3 个候选方案
          </div>
          <p className="mt-1 text-sm leading-6 text-zinc-600">
            {room.scenario === "family"
              ? "A 亲子体验优先｜B 早点回家优先｜C 雨天室内备选"
              : "A 体验优先｜B 折中推荐｜C 稳妥备选"}
          </p>
          <p className="mt-1 text-xs text-zinc-500">{room.consensus.summary}</p>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={() => onViewChange("plans")}>
            查看方案
            <ArrowRight className="ml-1.5 h-4 w-4" />
          </Button>
          {canOpenFinal && (
            <Button type="button" onClick={() => onViewChange("final")}>
              最终安排
            </Button>
          )}
        </div>
      </div>
    </section>
  );
}

function ExecutionHighlights({ scenario, completed }: { scenario: Scenario; completed: boolean }) {
  const items =
    scenario === "family"
      ? [
          { icon: Ticket, title: completed ? "亲子活动已预约" : "亲子活动可预约", detail: "适合5岁孩子，排队可控" },
          { icon: Utensils, title: completed ? "家庭餐厅已预订" : "家庭餐厅可订", detail: "儿童椅、少油清淡已备注" },
          { icon: CalendarCheck, title: completed ? "家庭文案已生成" : "准备家庭提醒", detail: "孩子累了可直接回家" },
        ]
      : [
          { icon: Ticket, title: completed ? "活动已预约" : "活动可预约", detail: "拍照点保留，路线集中" },
          { icon: Utensils, title: completed ? "4人桌已预订" : "4人桌可订", detail: "避开火锅，排队约18分钟" },
          { icon: CalendarCheck, title: completed ? "群聊文案已生成" : "准备群聊分享", detail: "饭后咖啡设为可选" },
        ];
  return (
    <section className="grid gap-3 md:grid-cols-3">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.title} className="rounded-lg bg-white p-4 shadow-sm shadow-zinc-100">
            <Icon className="h-5 w-5 text-orange-600" />
            <div className="mt-3 text-sm font-semibold text-zinc-950">{item.title}</div>
            <p className="mt-1 text-xs leading-5 text-zinc-500">{item.detail}</p>
          </div>
        );
      })}
    </section>
  );
}

function PromptChips({ scenario, onPick }: { scenario: Scenario; onPick: (value: string) => void }) {
  const prompts =
    scenario === "family"
      ? [
          "下午带孩子去玩 4 小时，孩子 5 岁，老婆想少走路，晚餐清淡一点。",
          "下雨天想带娃去室内玩，少排队，早点回家。",
        ]
      : [
          "今天下午和朋友聚，不想太远，想吃饭聊天，最好有拍照点。",
          "4 个朋友有吃有玩，不吃火锅，饭后可以喝咖啡。",
        ];
  return (
    <div className="flex flex-wrap gap-2">
      {prompts.map((prompt) => (
        <button
          key={prompt}
          type="button"
          className="rounded-full bg-zinc-100 px-3 py-1.5 text-xs text-zinc-600 hover:bg-orange-50 hover:text-orange-700"
          onClick={() => onPick(prompt)}
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}

function QuickReplies({ scenario, onPick }: { scenario: Scenario; onPick: (value: string) => void }) {
  const replies =
    scenario === "family"
      ? ["少走路", "清淡少油", "适合5岁孩子", "室内优先", "早点回家", "避开排队"]
      : ["不要火锅", "近一点", "想拍照", "预算别太高", "早点回家", "重新规划"];
  return (
    <div className="flex flex-wrap gap-2">
      {replies.map((reply) => (
        <button
          key={reply}
          type="button"
          className="rounded-full bg-zinc-100 px-3 py-1.5 text-xs text-zinc-600 hover:bg-orange-50 hover:text-orange-700"
          onClick={() => onPick(reply)}
        >
          {reply}
        </button>
      ))}
    </div>
  );
}

function headerTitle(room: RoomState, activeView: RoomActiveView) {
  if (activeView === "plans") return "方案对比";
  if (activeView === "final") return "最终执行";
  if (room.stage === "idle") return "对话";
  return room.scenario === "family" ? "家庭协作对话" : "朋友协作对话";
}

function headerSubtitle(room: RoomState, activeView: RoomActiveView) {
  if (activeView === "plans") return "比较候选方案、投票和查看推荐依据。";
  if (activeView === "final") return "把达成共识的安排变成可执行行程单。";
  return room.stage_description || "先聊清楚偏好，再进入方案。";
}

function heroPlaceholder(scenario: Scenario) {
  if (scenario === "family") {
    return "比如：下午带孩子去玩 4 小时，孩子 5 岁，老婆想少走路，晚餐清淡一点";
  }
  return "比如：今天下午想和朋友聚一聚，不想太远，最好能拍照、吃饭、喝咖啡";
}

function composerPlaceholder(scenario: Scenario) {
  if (scenario === "family") return "继续补充：别太油、早点回家、少排队";
  return "继续补充：不要火锅、想拍照、预算别太高";
}

function finalPlanTitle(room: RoomState) {
  if (room.scenario === "family") return "家庭安心下午安排好了";
  return "朋友局安排好了";
}

function finalPlanDetail(room: RoomState) {
  if (room.execution_state.status === "completed") return room.execution_state.summary;
  if (room.scenario === "family") {
    return "B 早点回家优先：孩子有室内亲子活动，晚餐清淡少油，儿童椅已备注，绘本书店可跳过。";
  }
  return "B 折中推荐：路线集中，避开火锅，保留小粉想去的拍照点，小绿能接受室内安排，小蓝也可以早点回。";
}

function approvalHint(isHost: boolean, viewingConsensusPlan: boolean, consensusSummary: string, scenario: Scenario) {
  if (!isHost) return `只有发起人${scenario === "family" ? "小明" : "小红"}可以确认执行。`;
  if (!viewingConsensusPlan) return "当前正在查看备选方案，请切回推荐方案后执行。";
  return consensusSummary;
}
