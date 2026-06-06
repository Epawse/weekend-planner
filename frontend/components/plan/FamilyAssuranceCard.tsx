"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { AlertTriangle, CheckCircle2, Info, ShieldCheck, Sparkles } from "lucide-react";
import type { EvidenceItem, FamilyCheck, Plan } from "@/lib/types";

interface FamilyAssuranceCardProps {
  plan: Plan;
}

function getCheckIcon(status: FamilyCheck["status"]) {
  if (status === "pass") {
    return <CheckCircle2 className="h-4 w-4 text-green-600" />;
  }
  if (status === "fail") {
    return <AlertTriangle className="h-4 w-4 text-red-600" />;
  }
  return <Info className="h-4 w-4 text-amber-600" />;
}

function getCheckClass(status: FamilyCheck["status"]): string {
  if (status === "pass") return "border-green-200 bg-green-50 text-green-800";
  if (status === "fail") return "border-red-200 bg-red-50 text-red-800";
  return "border-amber-200 bg-amber-50 text-amber-800";
}

function getFatigueLabel(score: number | null | undefined): string {
  if (score == null) return "未知";
  if (score <= 35) return "低";
  if (score <= 65) return "中";
  return "高";
}

function getEvidenceSourceLabel(item: EvidenceItem): string {
  if (item.source === "real_api") return "真实地图数据";
  if (item.source === "keyword_rule") return "规则推断";
  if (item.source === "category_rule") return "规则推断";
  if (item.source === "mock_api") return "演示业务接口";
  if (item.source === "mock_availability") return "演示业务接口";
  if (item.source === "mock_business_api") return "演示业务接口";
  if (item.source === "amap_real_poi") return "真实地图数据";
  if (item.source === "showcase_curated") return "精选演示数据";
  if (item.source === "fallback_generated") return "系统备选建议";
  if (item.source === "llm") return "规则推断";
  return item.source;
}

function getEvidenceClaim(item: EvidenceItem): string {
  if (item.claim.includes("POI来源")) return `${item.venue_name}地点信息已核验`;
  return item.claim;
}

function getEvidenceDescription(item: EvidenceItem): string {
  if (item.source === "showcase_curated") return "已验证适合当前场景。";
  if (item.source === "mock_business_api" || item.source === "mock_api" || item.source === "mock_availability") {
    return "已校验座位、等待时间和可用性。";
  }
  if (item.source === "amap_real_poi" || item.source === "real_api") return "来自地图数据与地点品类信息。";
  if (item.source === "fallback_generated") return "根据当前路线补充的可选备选。";
  if (item.evidence.includes("source=") || item.evidence.includes("typecode") || item.evidence.includes("tags=无")) {
    return "根据地点名称和品类推断。";
  }
  return item.evidence;
}

export function FamilyAssuranceCard({ plan }: FamilyAssuranceCardProps) {
  const checks = plan.family_checks ?? [];
  const evidence = plan.evidence ?? [];
  const degradations = (plan.degradations ?? []).filter((item) => item.trim().length > 0);
  const alternatives = plan.alternatives ?? [];
  const rejected = plan.rejected_options ?? [];
  const profile = plan.family_profile;

  if (!profile && checks.length === 0) return null;

  const highlightedEvidence = evidence.slice(0, 5);
  const passedChecks = checks.filter((check) => check.status === "pass");
  const degradedChecks = checks.filter((check) => check.status === "warn");
  const riskChecks = checks.filter((check) => check.status === "fail");

  return (
    <section className="space-y-4 rounded-lg border border-orange-200 bg-orange-50/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-orange-600" />
            <h3 className="text-sm font-semibold text-zinc-900">家庭安心检查</h3>
          </div>
          {profile && (
            <p className="mt-1 text-xs text-zinc-600">
              {profile.party_size}人出行 · 孩子{profile.child_age}岁 · {profile.diet_goal}
            </p>
          )}
        </div>
        <Badge className="border-orange-200 bg-white text-orange-700" variant="outline">
          疲劳度 {getFatigueLabel(plan.fatigue_score)}
          {plan.fatigue_score != null && ` · ${plan.fatigue_score}`}
        </Badge>
      </div>

      {plan.family_summary && (
        <p className="rounded-md bg-white px-3 py-2 text-xs text-zinc-700">
          {plan.family_summary}
        </p>
      )}

      {checks.length > 0 && (
        <div className="space-y-3">
          {passedChecks.length > 0 && (
            <div>
              <div className="mb-2 text-xs font-medium text-green-700">已满足</div>
              <div className="grid gap-2 sm:grid-cols-2">
                {passedChecks.slice(0, 6).map((check) => (
                  <div
                    key={check.id}
                    className={cn(
                      "flex items-start gap-2 rounded-md border px-3 py-2 text-xs",
                      getCheckClass(check.status)
                    )}
                  >
                    {getCheckIcon(check.status)}
                    <div>
                      <div className="font-medium">{check.label}</div>
                      <div className="mt-0.5 opacity-80">{check.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(degradedChecks.length > 0 || riskChecks.length > 0) && (
            <div>
              <div className="mb-2 text-xs font-medium text-amber-700">轻微降级 / 风险提醒</div>
              <div className="grid gap-2">
                {[...degradedChecks, ...riskChecks].map((check) => (
                  <div
                    key={check.id}
                    className={cn(
                      "flex items-start gap-2 rounded-md border px-3 py-2 text-xs",
                      getCheckClass(check.status)
                    )}
                  >
                    {getCheckIcon(check.status)}
                    <div>
                      <div className="font-medium">{check.label}</div>
                      <div className="mt-0.5 opacity-80">{check.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {degradations.length > 0 && (
        <details className="rounded-md border border-amber-200 bg-white p-3">
          <summary className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-amber-700">
            <AlertTriangle className="h-4 w-4" />
            已做降级处理
          </summary>
          <ul className="mt-2 space-y-1 text-xs text-zinc-600">
            {degradations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </details>
      )}

      {highlightedEvidence.length > 0 && (
        <details className="rounded-md bg-white p-3">
          <summary className="flex cursor-pointer items-center gap-1.5 text-xs font-medium text-zinc-700">
            <Sparkles className="h-4 w-4 text-orange-500" />
            关键证据
          </summary>
          <div className="mt-2 space-y-2">
            {highlightedEvidence.map((item) => (
              <div key={item.id} className="text-xs text-zinc-600">
                <span className="font-medium text-zinc-800">{getEvidenceClaim(item)}</span>
                <span className="mx-1 text-zinc-300">·</span>
                <span>{getEvidenceSourceLabel(item)}</span>
                <div className="mt-0.5 text-zinc-500">{getEvidenceDescription(item)}</div>
              </div>
            ))}
          </div>
        </details>
      )}

      {(alternatives.length > 0 || rejected.length > 0) && (
        <div className="grid gap-3 sm:grid-cols-2">
          {alternatives.length > 0 && (
            <details className="rounded-md bg-white p-3">
              <summary className="cursor-pointer text-xs font-medium text-zinc-700">备选方案</summary>
              {alternatives.slice(0, 2).map((item) => (
                <div key={item.id} className="mt-2 text-xs text-zinc-600">
                  <div className="font-medium text-zinc-800">{item.title}</div>
                  <div>{item.reason}</div>
                </div>
              ))}
            </details>
          )}

          {rejected.length > 0 && (
            <details className="rounded-md bg-white p-3">
              <summary className="cursor-pointer text-xs font-medium text-zinc-700">为什么不选</summary>
              {rejected.slice(0, 2).map((item) => (
                <div key={item.label} className="mt-2 text-xs text-zinc-600">
                  <div className="font-medium text-zinc-800">{item.label}</div>
                  <div>{item.reasons.join("；")}</div>
                </div>
              ))}
            </details>
          )}
        </div>
      )}
    </section>
  );
}
