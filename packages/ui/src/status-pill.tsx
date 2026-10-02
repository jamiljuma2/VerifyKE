import type { VerificationStatus } from "@verifyke/shared-types";

import { Badge, type BadgeTone } from "./badge";
import { cn } from "./cn";

/**
 * Presentation rules for each verification status.
 *
 * `label` is the exact wording shown to a human; `explanation` is the one-line
 * meaning used in tooltips and result summaries. Keeping them together stops the
 * same status from being described two different ways in two different screens.
 */
export const STATUS_PRESENTATION: Record<
  VerificationStatus,
  { label: string; tone: BadgeTone; explanation: string; icon: string }
> = {
  VERIFIED: {
    label: "Verified",
    tone: "verified",
    explanation: "Issuer record, signature and content checks all passed.",
    icon: "\u2713",
  },
  SUSPECT: {
    label: "Needs review",
    tone: "suspect",
    explanation: "One or more checks raised a concern; manual review is required.",
    icon: "!",
  },
  FAILED: {
    label: "Not genuine",
    tone: "failed",
    explanation: "A decisive check failed - the document does not match the issuer record.",
    icon: "\u00d7",
  },
  NOT_FOUND: {
    label: "Not found",
    tone: "neutral",
    explanation: "No certificate matches this identifier or document.",
    icon: "?",
  },
  REVOKED: {
    label: "Revoked",
    tone: "failed",
    explanation: "The issuer withdrew this certificate; it is no longer valid.",
    icon: "\u2298",
  },
  EXPIRED: {
    label: "Expired",
    tone: "suspect",
    explanation: "The certificate passed its validity date.",
    icon: "\u23f3",
  },
  PENDING: {
    label: "Processing",
    tone: "info",
    explanation: "Verification is still running; check again shortly.",
    icon: "\u22ef",
  },
};

export function StatusPill({
  status,
  className,
}: {
  status: VerificationStatus;
  className?: string;
}) {
  const presentation = STATUS_PRESENTATION[status];
  return (
    <Badge tone={presentation.tone} className={cn("text-sm", className)}>
      <span aria-hidden="true" className="font-mono">
        {presentation.icon}
      </span>
      {presentation.label}
    </Badge>
  );
}
