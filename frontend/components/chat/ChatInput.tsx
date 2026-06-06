"use client";

import { useState, useCallback, type FormEvent, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScenarioSelector } from "./ScenarioSelector";
import { Send } from "lucide-react";
import type { Scenario } from "@/lib/types";

interface ChatInputProps {
  onSubmit: (message: string, scenario: Scenario, homeLocation: [number, number]) => void;
  disabled?: boolean;
  compactScenarioSelector?: boolean;
}

const DEFAULT_HOME_LOCATION: [number, number] = [116.481, 39.998];

const SUGGESTIONS = [
  "今天下午想带老婆孩子出去玩，别离家太远",
  "周末想和朋友聚一聚，吃点好的再找个地方玩",
  "下午有空，想带家人去个亲子乐园，顺便吃顿饭",
];

export function ChatInput({ onSubmit, disabled = false, compactScenarioSelector = false }: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [scenario, setScenario] = useState<Scenario>("family");

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const trimmed = message.trim();
      if (!trimmed || disabled) return;
      onSubmit(trimmed, scenario, DEFAULT_HOME_LOCATION);
      setMessage("");
    },
    [message, scenario, disabled, onSubmit]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const trimmed = message.trim();
        if (!trimmed || disabled) return;
        onSubmit(trimmed, scenario, DEFAULT_HOME_LOCATION);
        setMessage("");
      }
    },
    [message, scenario, disabled, onSubmit]
  );

  const handleSuggestionClick = useCallback(
    (suggestion: string) => {
      if (disabled) return;
      onSubmit(suggestion, scenario, DEFAULT_HOME_LOCATION);
    },
    [scenario, disabled, onSubmit]
  );

  return (
    <div className="space-y-4">
      <ScenarioSelector
        selected={scenario}
        onSelect={setScenario}
        disabled={disabled}
        compact={compactScenarioSelector}
      />

      {!disabled && !compactScenarioSelector && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => handleSuggestionClick(suggestion)}
              className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs text-zinc-600 transition-colors hover:border-zinc-300 hover:bg-zinc-100"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="告诉我你想怎么安排..."
          disabled={disabled}
          aria-label="输入活动需求"
        />
        <Button
          type="submit"
          disabled={disabled || !message.trim()}
          aria-label="发送消息"
        >
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
