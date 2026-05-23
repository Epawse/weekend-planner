import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "secondary" | "outline";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
        {
          "bg-zinc-900 text-white": variant === "default",
          "bg-zinc-100 text-zinc-900": variant === "secondary",
          "border border-zinc-200 text-zinc-700": variant === "outline",
        },
        className
      )}
      {...props}
    />
  );
}
