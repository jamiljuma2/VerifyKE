import type { ReactNode } from "react";

import { cn } from "./cn";

export type BadgeTone = "neutral" | "verified" | "suspect" | "failed" | "info";

const TONES: Record<BadgeTone, string> = {
  neutral: "bg-muted-soft text-muted border-muted-border",
  verified: "bg-verified-soft text-verified border-verified-border",
  suspect: "bg-suspect-soft text-suspect border-suspect-border",
  failed: "bg-failed-soft text-failed border-failed-border",
  info: "bg-brand-50 text-brand-700 border-brand-200",
};

/** Small, non-interactive label. Always paired with text - never colour alone. */
export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
