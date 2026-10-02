import { isApiErrorEnvelope, type ApiErrorCode, type ApiErrorDetail } from "@verifyke/shared-types";

import { publicEnv } from "./env";

/**
 * Typed API client.
 *
 * The browser never talks to the API directly with a token: session cookies are
 * `HttpOnly` and same-site, so requests are sent with `credentials: "include"`
 * and the server decides whether the caller is authenticated. Mutating requests
 * must carry the CSRF token from the readable `vk_csrf` cookie.
 */
export class ApiError extends Error {
  readonly code: ApiErrorCode | string;
  readonly status: number;
  readonly details?: ApiErrorDetail[] | Record<string, unknown>;
  readonly requestId?: string;

  constructor(params: {
    code: ApiErrorCode | string;
    message: string;
    status: number;
    details?: ApiErrorDetail[] | Record<string, unknown>;
    requestId?: string;
  }) {
    super(params.message);
    this.name = "ApiError";
    this.code = params.code;
    this.status = params.status;
    this.details = params.details;
    this.requestId = params.requestId;
  }

  /** True when retrying the same request could plausibly succeed. */
  get isRetryable(): boolean {
    return this.status >= 500 || this.code === "RATE_LIMITED" || this.code === "SERVICE_UNAVAILABLE";
  }
}

const CSRF_COOKIE_NAME = "vk_csrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") {
    return undefined;
  }
  return document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(`${name}=`))
    ?.split("=")[1];
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Milliseconds before the request is aborted (default 30s). */
  timeoutMs?: number;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, timeoutMs = 30_000, headers, ...rest } = options;
  const method = (rest.method ?? "GET").toUpperCase();

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
  }
  if (MUTATING_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) {
      requestHeaders.set(CSRF_HEADER_NAME, csrfToken);
    }
  }

  try {
    const response = await fetch(`${publicEnv.NEXT_PUBLIC_API_BASE_URL}${path}`, {
      ...rest,
      method,
      headers: requestHeaders,
      credentials: "include",
      signal: controller.signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    return await readResponse<T>(response);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError({
        code: "SERVICE_UNAVAILABLE",
        message: "The request timed out. Check your connection and try again.",
        status: 408,
      });
    }
    throw new ApiError({
      code: "SERVICE_UNAVAILABLE",
      message: "The verification service is unreachable. Please try again shortly.",
      status: 503,
    });
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Decode a response, converting the API's error envelope into an `ApiError`.
 * Kept in one place so every entry point (JSON, upload, streaming) fails the
 * same way and a UI can rely on `error.code`.
 */
async function readResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    if (isApiErrorEnvelope(payload)) {
      throw new ApiError({
        code: payload.error.code,
        message: payload.error.message,
        details: payload.error.details,
        requestId: payload.error.request_id,
        status: response.status,
      });
    }
    throw new ApiError({
      code: "HTTP_ERROR",
      message: "The request could not be completed.",
      status: response.status,
    });
  }

  return payload as T;
}

/**
 * Multipart upload (document verification).
 *
 * The file is sent as `multipart/form-data`; the browser sets the boundary, so
 * `Content-Type` must not be set manually. A CSRF token is still required
 * because the request relies on cookie authentication.
 */
export async function apiUpload<T>(
  path: string,
  formData: FormData,
  options: { timeoutMs?: number } = {},
): Promise<T> {
  const { timeoutMs = 120_000 } = options;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  const headers = new Headers({ Accept: "application/json" });
  const csrfToken = readCookie(CSRF_COOKIE_NAME);
  if (csrfToken) {
    headers.set(CSRF_HEADER_NAME, csrfToken);
  }

  try {
    const response = await fetch(`${publicEnv.NEXT_PUBLIC_API_BASE_URL}${path}`, {
      method: "POST",
      body: formData,
      headers,
      credentials: "include",
      signal: controller.signal,
    });
    return await readResponse<T>(response);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError({
        code: "SERVICE_UNAVAILABLE",
        message: "The upload timed out. Try again with a smaller file or a stronger connection.",
        status: 408,
      });
    }
    throw new ApiError({
      code: "SERVICE_UNAVAILABLE",
      message: "The upload could not be completed. Please try again shortly.",
      status: 503,
    });
  } finally {
    clearTimeout(timeout);
  }
}
