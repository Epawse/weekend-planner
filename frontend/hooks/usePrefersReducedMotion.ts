"use client";

import { useEffect, useState } from "react";

/**
 * Tracks the user's `prefers-reduced-motion` setting so animation-heavy UI
 * (typewriter streaming, caret blink, entrance transitions) can degrade to an
 * instant, motion-free experience.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return reduced;
}
