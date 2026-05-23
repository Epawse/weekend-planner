"use client";

import { cn } from "@/lib/utils";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

export function ChatMessage({ role, content, timestamp }: ChatMessageProps) {
  return (
    <div
      className={cn(
        "flex w-full",
        role === "user" ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          role === "user"
            ? "bg-zinc-900 text-white"
            : "bg-zinc-100 text-zinc-800"
        )}
      >
        <p className="whitespace-pre-wrap">{content}</p>
        {timestamp && (
          <time
            className={cn(
              "mt-1 block text-[10px]",
              role === "user" ? "text-zinc-400" : "text-zinc-400"
            )}
            dateTime={timestamp}
          >
            {new Date(timestamp).toLocaleTimeString("zh-CN", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </time>
        )}
      </div>
    </div>
  );
}
