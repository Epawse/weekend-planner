"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface AutoScrollResult {
  /** True while the viewport is parked near the bottom (follows new content). */
  pinned: boolean;
  /** Smoothly jump to the bottom and re-pin. */
  scrollToBottom: () => void;
  /** Callback ref to attach to the scroll container. */
  setScrollNode: (node: HTMLElement | null) => void;
}

const PIN_THRESHOLD_PX = 96;

/**
 * Keeps a scroll container glued to the bottom as content grows — but only
 * while the user hasn't deliberately scrolled up to read earlier messages.
 *
 * Uses a callback ref (not a RefObject) so the scroll listener attaches exactly
 * when the container mounts. This matters because the consumer renders a
 * different layout before any messages exist (e.g. an idle hero), so the
 * scrollable element only appears on a later render.
 *
 * @param signal a value that changes whenever content grows (message count,
 *               typing state, typewriter tick). When it changes and the view is
 *               pinned, the container snaps to the bottom.
 */
export function useAutoScroll(signal: unknown): AutoScrollResult {
  const [pinned, setPinned] = useState(true);
  const pinnedRef = useRef(true);
  const nodeRef = useRef<HTMLElement | null>(null);

  const handleScroll = useCallback(() => {
    const element = nodeRef.current;
    if (!element) return;
    const distanceFromBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight;
    const nextPinned = distanceFromBottom <= PIN_THRESHOLD_PX;
    pinnedRef.current = nextPinned;
    setPinned(nextPinned);
  }, []);

  const setScrollNode = useCallback(
    (node: HTMLElement | null) => {
      if (nodeRef.current) {
        nodeRef.current.removeEventListener("scroll", handleScroll);
      }
      nodeRef.current = node;
      if (node) {
        node.addEventListener("scroll", handleScroll, { passive: true });
      }
    },
    [handleScroll]
  );

  // Follow new content while pinned. Uses instant scrolling because `signal`
  // fires on every typewriter tick — smooth scrolling would stutter.
  useEffect(() => {
    const element = nodeRef.current;
    if (!element || !pinnedRef.current) return;
    element.scrollTop = element.scrollHeight;
  }, [signal]);

  const scrollToBottom = useCallback(() => {
    const element = nodeRef.current;
    if (!element) return;
    element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
    pinnedRef.current = true;
    setPinned(true);
  }, []);

  return { pinned, scrollToBottom, setScrollNode };
}
