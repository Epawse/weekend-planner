"use client";

import { ShareButton } from "@/components/shared/ShareButton";

interface CanvasShareCardProps {
  shareText: string;
}

export function CanvasShareCard({ shareText }: CanvasShareCardProps) {
  if (!shareText) return null;

  return (
    <section className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-zinc-900">分享文案</div>
        <ShareButton text={shareText} />
      </div>
      <p className="text-sm leading-6 text-zinc-700">{shareText}</p>
    </section>
  );
}
