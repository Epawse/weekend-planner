"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";
import type { ParticipantId, SharedMessage } from "@/lib/types";

export interface TypewriterFrame {
  /** The slice of `content` that should currently be visible. */
  text: string;
  /** Whether the caret should be shown (message still typing). */
  streaming: boolean;
}

interface TypewriterOptions {
  /** The viewer. Their own messages appear instantly (they already typed them). */
  selfId: ParticipantId;
  /** Disable streaming entirely (renders everything in full). */
  enabled?: boolean;
}

interface TypewriterResult {
  /** Sparse map: only the message currently typing has an entry. */
  frames: Map<string, TypewriterFrame>;
  /** Ids that have not been revealed yet — the consumer should not render them. */
  hiddenIds: Set<string>;
  /** Grows as messages reveal/type — use as an auto-scroll dependency. */
  tick: number;
}

interface ViewState {
  activeId: string | null;
  text: string;
  streaming: boolean;
  hidden: string[];
  seq: number;
}

const TICK_MS = 22;
const MAX_DURATION_MS = 1100;
const GAP_TICKS = Math.round(220 / TICK_MS);

const useIsomorphicLayoutEffect =
  typeof document !== "undefined" ? useLayoutEffect : useEffect;

const IDLE_VIEW: ViewState = { activeId: null, text: "", streaming: false, hidden: [], seq: 0 };

function isEligible(message: SharedMessage, selfId: ParticipantId): boolean {
  if (message.type === "system_message") return false;
  // The viewer's own outgoing messages should not be re-typed back at them.
  if (message.actor_id === selfId) return false;
  return true;
}

/**
 * Client-side streaming/typewriter effect for the collaborative room.
 *
 * The backend returns whole messages — and with the real LLM, a single turn
 * appends a *batch* of them at once (agent + several members). This hook reveals
 * a batch **one message at a time, in order**, typing each out, so members never
 * pop in fully-formed. History present at mount renders instantly; the viewer's
 * own messages reveal instantly; everything not yet reached stays hidden.
 *
 * The visible slice + hidden set live in React state (read during render); the
 * mutable animation cursor and bookkeeping live in refs (touched only in effects).
 */
export function useTypewriter(
  messages: SharedMessage[],
  { selfId, enabled = true }: TypewriterOptions
): TypewriterResult {
  const reduced = usePrefersReducedMotion();
  const active = enabled && !reduced;

  const completedRef = useRef<Set<string>>(new Set());
  const seededRef = useRef(false);
  const cursorRef = useRef<{ id: string; full: string; len: number } | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const gapRef = useRef(0);
  const seqRef = useRef(0);
  const messagesRef = useRef(messages);
  const selfIdRef = useRef(selfId);
  const [view, setView] = useState<ViewState>(IDLE_VIEW);

  useIsomorphicLayoutEffect(() => {
    messagesRef.current = messages;
    selfIdRef.current = selfId;
    const completed = completedRef.current;

    const stopTimer = () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };

    const publish = () => {
      const msgs = messagesRef.current;
      const cursor = cursorRef.current;
      const hidden: string[] = [];
      for (const message of msgs) {
        if (completed.has(message.id)) continue;
        if (cursor && message.id === cursor.id) continue;
        hidden.push(message.id); // uncompleted and not the active one → not revealed yet
      }
      setView({
        activeId: cursor?.id ?? null,
        text: cursor ? cursor.full.slice(0, cursor.len) : "",
        streaming: cursor ? cursor.len < cursor.full.length : false,
        hidden,
        seq: (seqRef.current += 1),
      });
    };

    // Walk to the next message that should type out, revealing/snapping anything
    // ahead of it that does not animate (the viewer's own / system messages).
    const pump = () => {
      const msgs = messagesRef.current;
      const self = selfIdRef.current;
      let index = 0;
      while (index < msgs.length && completed.has(msgs[index].id)) index += 1;
      while (
        index < msgs.length &&
        !completed.has(msgs[index].id) &&
        !isEligible(msgs[index], self)
      ) {
        completed.add(msgs[index].id); // reveal instantly, in order
        index += 1;
      }
      if (index >= msgs.length) {
        cursorRef.current = null;
        stopTimer();
        publish();
        return;
      }
      const target = msgs[index];
      if (cursorRef.current?.id !== target.id) {
        cursorRef.current = { id: target.id, full: target.content, len: 0 };
      }
      if (!timerRef.current) {
        timerRef.current = setInterval(() => {
          if (gapRef.current > 0) {
            gapRef.current -= 1;
            return;
          }
          const cursor = cursorRef.current;
          if (!cursor) {
            pump();
            return;
          }
          const step = Math.max(1, Math.ceil(cursor.full.length / (MAX_DURATION_MS / TICK_MS)));
          cursor.len = Math.min(cursor.full.length, cursor.len + step);
          if (cursor.len >= cursor.full.length) {
            completedRef.current.add(cursor.id);
            cursorRef.current = null;
            gapRef.current = GAP_TICKS;
            publish();
          } else {
            publish();
          }
        }, TICK_MS);
      }
      publish();
    };

    // Seed once: history already on screen at mount is shown in full.
    if (!seededRef.current) {
      seededRef.current = true;
      for (const message of messages) completed.add(message.id);
      return;
    }

    if (!active) {
      // Motion disabled — snap everything to its final, fully-revealed state.
      stopTimer();
      cursorRef.current = null;
      for (const message of messages) completed.add(message.id);
      publish();
      return;
    }

    pump();
  }, [messages, active, selfId]);

  // Clear the timer when the consumer unmounts.
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  const frames = new Map<string, TypewriterFrame>();
  if (view.activeId) {
    frames.set(view.activeId, { text: view.text, streaming: view.streaming });
  }
  return { frames, hiddenIds: new Set(view.hidden), tick: view.seq };
}
