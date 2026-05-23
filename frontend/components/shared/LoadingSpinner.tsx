import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

export function LoadingSpinner({ className, size = "md" }: LoadingSpinnerProps) {
  return (
    <div
      role="status"
      aria-label="加载中"
      className={cn(
        "inline-block animate-spin rounded-full border-2 border-current border-t-transparent text-zinc-600",
        {
          "h-4 w-4": size === "sm",
          "h-6 w-6": size === "md",
          "h-8 w-8": size === "lg",
        },
        className
      )}
    >
      <span className="sr-only">加载中...</span>
    </div>
  );
}
