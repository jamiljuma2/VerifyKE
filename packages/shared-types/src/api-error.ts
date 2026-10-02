/**
 * The single error envelope every API endpoint returns:
 *
 *   { "error": { "code": "NOT_FOUND", "message": "...", "details": ..., "request_id": "..." } }
 */

export const API_ERROR_CODES = [
  "VALIDATION_ERROR",
  "AUTHENTICATION_REQUIRED",
  "INVALID_CREDENTIALS",
  "ACCOUNT_LOCKED",
  "MFA_REQUIRED",
  "REAUTHENTICATION_REQUIRED",
  "PERMISSION_DENIED",
  "CSRF_VALIDATION_FAILED",
  "NOT_FOUND",
  "CONFLICT",
  "RESOURCE_GONE",
  "PAYLOAD_TOO_LARGE",
  "UNSUPPORTED_MEDIA_TYPE",
  "RATE_LIMITED",
  "SERVICE_UNAVAILABLE",
  "INTERNAL_ERROR",
  "HTTP_ERROR",
] as const;

export type ApiErrorCode = (typeof API_ERROR_CODES)[number];

export interface ApiErrorDetail {
  location?: string;
  message: string;
  type?: string;
}

export interface ApiErrorBody {
  code: ApiErrorCode | string;
  message: string;
  details?: ApiErrorDetail[] | Record<string, unknown>;
  request_id?: string;
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody;
}

export function isApiErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const error = (value as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}
