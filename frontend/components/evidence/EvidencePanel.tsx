"use client";

import { AlertTriangle, ChevronDown, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import type { EvidenceCardItem, RejectedCanvasOption } from "@/lib/types";

interface EvidencePanelProps {
  evidence: EvidenceCardItem[];
  rejectedOptions: RejectedCanvasOption[];
  selectedTimelineId: string | null;
  onSelectEvidence: (timelineId: string | null, markerId: string | null) => void;
}

export function EvidencePanel({
  evidence,
  rejectedOptions,
  selectedTimelineId,
  onSelectEvidence,
}: EvidencePanelProps) {
  const groups = evidence.reduce<Record<string, EvidenceCardItem[]>>((acc, item) => {
    acc[item.source_label] = [...(acc[item.source_label] ?? []), item];
    return acc;
  }, {});
  const sourceOrder = [
    "真实地图数据",
    "精选演示数据",
    "演示业务接口",
    "投票信号",
    "规则推断",
    "路线计算",
    "系统备选建议",
  ];
  const orderedGroups = Object.entries(groups).sort(
    ([a], [b]) => sourceRank(sourceOrder, a) - sourceRank(sourceOrder, b)
  );

  return (
    <div className="custom-scrollbar h-full overflow-y-auto p-4">
      <div className="mb-4">
        <div className="text-sm font-semibold text-zinc-900">来源与校验</div>
        <div className="text-xs text-zinc-500">
          {orderedGroups.length} 类来源，{evidence.length + rejectedOptions.length} 条证据
        </div>
      </div>

      <div className="space-y-4">
        {orderedGroups.map(([source, items]) => (
          <details key={source} className="group rounded-lg border border-zinc-100 bg-white p-3" open>
            <summary className="flex cursor-pointer list-none items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-zinc-900">{source}</div>
                <div className="mt-1 text-xs leading-5 text-zinc-500">
                  {sourceSummary(source, items)}
                </div>
              </div>
              <ChevronDown className="mt-0.5 h-4 w-4 text-zinc-400 transition-transform group-open:rotate-180" />
            </summary>

            <div className="mt-3 space-y-2">
              <div className="flex flex-wrap gap-1.5">
                {items.slice(0, 3).map((item) => (
                  <span key={item.id} className="rounded bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">
                    {item.subject || item.title}
                  </span>
                ))}
              </div>

              {items.map((item) => {
                const timelineId = item.related_timeline_ids[0] ?? null;
                const markerId = item.related_marker_ids[0] ?? null;
                const active = timelineId != null && timelineId === selectedTimelineId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onSelectEvidence(timelineId, markerId)}
                    className={cn(
                      "w-full rounded-md border p-3 text-left text-sm transition-colors",
                      active ? "border-orange-300 bg-orange-50" : "border-zinc-100 bg-zinc-50 hover:border-zinc-200"
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <FileText className="mt-0.5 h-4 w-4 text-zinc-500" />
                      <div className="min-w-0">
                        <div className="font-medium text-zinc-900">{item.title}</div>
                        {item.subject && <div className="mt-0.5 text-xs text-zinc-500">{item.subject}</div>}
                        <div className="mt-1 text-xs leading-5 text-zinc-600">{item.detail}</div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </details>
        ))}

        {rejectedOptions.length > 0 && (
          <details className="group rounded-lg border border-amber-100 bg-amber-50 p-3" open>
            <summary className="flex cursor-pointer list-none items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-amber-950">被排除项</div>
                <div className="mt-1 text-xs leading-5 text-amber-800">
                  {rejectedOptions.length} 个候选未进入计划，原因会影响后续反馈重规划。
                </div>
              </div>
              <ChevronDown className="mt-0.5 h-4 w-4 text-amber-700 transition-transform group-open:rotate-180" />
            </summary>
            <div className="mt-3 space-y-2">
              {rejectedOptions.map((item) => (
                <div key={item.id} className="rounded-md border border-amber-100 bg-white/70 p-3 text-sm text-amber-950">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 h-4 w-4" />
                    <div>
                      <div className="font-medium">{item.name}</div>
                      <div className="mt-1 text-xs leading-5">{item.reason}</div>
                      <div className="mt-1 text-xs opacity-75">{item.source_label}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function sourceSummary(source: string, items: EvidenceCardItem[]) {
  const subjects = Array.from(new Set(items.map((item) => item.subject).filter(Boolean))).slice(0, 3);
  if (source === "真实地图数据") return `用于核验地点坐标、地址和路线可达性，共 ${items.length} 条。`;
  if (source === "精选演示数据") return `用于保证演示地点稳定可复现：${subjects.join("、") || `${items.length} 条地点`}`;
  if (source === "演示业务接口") return `用于核验排队、桌位、预约等执行条件，共 ${items.length} 条。`;
  if (source === "投票信号") return `来自成员投票和地点反应，用于解释群体偏好和折中原因。`;
  if (source === "规则推断") return `用于判断聊天、拍照、亲子、清淡餐和路线集中等场景适配。`;
  if (source === "路线计算") return `用于解释站点顺序和通勤时间。`;
  return `${items.length} 条可解释证据。`;
}

function sourceRank(sourceOrder: string[], source: string) {
  const index = sourceOrder.indexOf(source);
  return index >= 0 ? index : sourceOrder.length;
}
