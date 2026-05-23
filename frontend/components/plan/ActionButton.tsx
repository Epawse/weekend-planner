"use client";

import { Button } from "@/components/ui/button";
import { Check, RotateCcw } from "lucide-react";

interface ActionButtonProps {
  onApprove: () => void;
  onReject: () => void;
  disabled?: boolean;
}

export function ActionButton({ onApprove, onReject, disabled = false }: ActionButtonProps) {
  return (
    <div className="flex gap-3">
      <Button
        onClick={onApprove}
        disabled={disabled}
        size="lg"
        className="flex-1 bg-green-600 hover:bg-green-700"
        aria-label="确认方案"
      >
        <Check className="mr-2 h-4 w-4" />
        确认方案
      </Button>
      <Button
        onClick={onReject}
        disabled={disabled}
        variant="outline"
        size="lg"
        className="flex-1"
        aria-label="重新规划"
      >
        <RotateCcw className="mr-2 h-4 w-4" />
        重新规划
      </Button>
    </div>
  );
}
