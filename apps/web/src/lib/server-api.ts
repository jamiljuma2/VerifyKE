import { cookies } from "next/headers";

import { isApiErrorEnvelope, type ApiErrorCode } from "@verifyke/shared-types";

/**
 * Server-side API access for React Server Components.
 *
 * Two differences from the browser client matter here:
 *
 * 1. The internal Docker hostname is used (`API_INTERNAL_URL`) so requests stay
 *    on the private network instead of going out through the public ingress.
 * 2. The incoming cookie header is forwarded explicitly, because a server
 *    component's `fetch` does not inherit the browser's cookies. Nothing else is
 *    forwarded - no user agent, no client IP, no arbitrary headers.
 *
 * Note that forwarded responses are never cached: verification results contain
 * personal data and depend on the caller's authorisation.
 */
const INTERNAL_API_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export interface ServerApiResult<T> {
  ok: boolean;
  status: number;
  data?: T;
  error?: { code: ApiErrorCode | string; message: string; requestId?: string };
}

export async function serverApiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<ServerApiResult<T>> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((cookie) => `${cookie.name}=${cookie.value}`)
    .join("; ");

  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (cookieHeader) {
    headers.set("Cookie", cookieHeader);
  }

  let response: Response;
  try {
    response = await fetch(`${INTERNAL_API_URL}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch {
    return {
      ok: false,
      status: 503,
      error: {
        code: "SERVICE_UNAVAILABLE",
        message: "The verification service is unreachable right now. Please try again shortly.",
      },
    };
  }

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    if (isApiErrorEnvelope(payload)) {
      return {
        ok: false,
        status: response.status,
        error: {
          code: payload.error.code,
          message: payload.error.message,
          requestId: payload.error.request_id,
        },
      };
    }
    return {
      ok: false,
      status: response.status,
      error: { code: "HTTP_ERROR", message: "The request could not be completed." },
    };
  }

  return { ok: true, status: response.status, data: payload as T };
}
