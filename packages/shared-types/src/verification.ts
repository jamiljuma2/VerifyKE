/**
 * Verification domain contracts.
 *
 * A result is always evidence-based: it reports what each independent check
 * found. `VERIFIED` is never inferred from a QR code being present, nor from
 * OCR text alone.
 */

export const VERIFICATION_STATUSES = [
  "VERIFIED",
  "SUSPECT",
  "FAILED",
  "NOT_FOUND",
  "REVOKED",
  "EXPIRED",
  "PENDING",
] as const;

export type VerificationStatus = (typeof VERIFICATION_STATUSES)[number];

export const VERIFICATION_CHANNELS = [
  "QR",
  "MANUAL_ID",
  "UPLOAD_IMAGE",
  "UPLOAD_PDF",
  "EXTERNAL_API",
] as const;

export type VerificationChannel = (typeof VERIFICATION_CHANNELS)[number];

/** Outcome of a single independent check. `NOT_APPLICABLE` is honest: a check
 * that could not run must never be reported as passing. */
export const CHECK_OUTCOMES = ["PASS", "FAIL", "WARN", "NOT_APPLICABLE", "ERROR"] as const;
export type CheckOutcome = (typeof CHECK_OUTCOMES)[number];

/** A single independent check performed during verification. */
export interface VerificationCheck {
  /** Stable machine name, e.g. `issuer_record`, `pdf_signature`, `content_hash`. */
  code: string;
  /** Human-readable name shown in the results list. */
  label: string;
  outcome: CheckOutcome;
  /** One sentence explaining what was found - never a raw exception. */
  detail: string;
  /** Optional structured evidence (hash values, key version, page numbers). */
  evidence?: Record<string, string | number | boolean | null>;
}

/** How conclusive the overall result is. */
export const EVIDENCE_LEVELS = ["HIGH", "MEDIUM", "LOW"] as const;
export type EvidenceLevel = (typeof EVIDENCE_LEVELS)[number];

export interface VerificationSubject {
  certificate_id: string | null;
  holder_name: string | null;
  institution_name: string | null;
  qualification: string | null;
  issued_on: string | null;
  valid_until: string | null;
}

export interface VerificationResult {
  /** Identifier for this verification event, quoted in support requests. */
  verification_id: string;
  status: VerificationStatus;
  channel: VerificationChannel;
  evidence_level: EvidenceLevel;
  /** Plain-language summary of the outcome. */
  summary: string;
  /** The individual checks, in the order they were performed. */
  checks: VerificationCheck[];
  /** Certificate details, masked where the requester is not authorised. */
  subject: VerificationSubject | null;
  /** When the result was produced (ISO 8601, UTC). */
  verified_at: string;
}

/** True when the status is a definitive outcome rather than an in-progress one. */
export function isFinalStatus(status: VerificationStatus): boolean {
  return status !== "PENDING";
}

/** True when a human should look at the result before it is relied upon. */
export function needsHumanReview(status: VerificationStatus): boolean {
  return status === "SUSPECT" || status === "PENDING";
}
