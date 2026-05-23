import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatTime(time: string): string {
  return time;
}

export function formatDuration(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}分钟`;
  }
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  if (remaining === 0) {
    return `${hours}小时`;
  }
  return `${hours}小时${remaining}分钟`;
}

export function getActivityTypeLabel(type: "play" | "eat" | "extra"): string {
  const labels: Record<string, string> = {
    play: "游玩",
    eat: "用餐",
    extra: "其他",
  };
  return labels[type] ?? type;
}

export function getActivityTypeColor(type: "play" | "eat" | "extra"): string {
  const colors: Record<string, string> = {
    play: "bg-green-100 text-green-800 border-green-200",
    eat: "bg-orange-100 text-orange-800 border-orange-200",
    extra: "bg-purple-100 text-purple-800 border-purple-200",
  };
  return colors[type] ?? "bg-gray-100 text-gray-800 border-gray-200";
}
