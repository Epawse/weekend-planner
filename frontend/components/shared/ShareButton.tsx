"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Share2, Check } from "lucide-react";

interface ShareButtonProps {
  text: string;
  className?: string;
}

export function ShareButton({ text, className }: ShareButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [text]);

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={handleCopy}
      className={className}
      aria-label={copied ? "已复制" : "分享方案"}
    >
      {copied ? (
        <>
          <Check className="mr-1.5 h-4 w-4" />
          已复制
        </>
      ) : (
        <>
          <Share2 className="mr-1.5 h-4 w-4" />
          分享
        </>
      )}
    </Button>
  );
}
