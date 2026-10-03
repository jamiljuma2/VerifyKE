/**
 * Per-request Content-Security-Policy.
 *
 * Why this exists
 * ---------------
 * Next.js renders the React Server Component payload and the hydration bootstrap
 * as *inline* `<script>` elements. A `script-src` list without `'unsafe-inline'`
 * or a nonce blocks every one of them: the server-rendered HTML paints once and
 * then React never hydrates, so the page goes blank.
 *
 * The fix keeps the strict policy by giving every request its own nonce. The
 * nonce is put on the *request* headers, where Next.js reads it while rendering
 * its inline scripts, and on the *response* headers, where the browser enforces
 * it. Nothing has to be weakened to `'unsafe-inline'`.
 */
import { NextResponse, type NextRequest } from "next/server";

const isDevelopment = process.env.NODE_ENV === "development";

/** Build the policy for one request, bound to that request's nonce. */
function buildCsp(nonce: string): string {
  const directives = [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    // 'strict-dynamic' lets the nonce'd bootstrap load the app's own chunks
    // without every path having to be enumerated. Development additionally needs
    // 'unsafe-eval' for React Fast Refresh.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${
      isDevelopment ? " 'unsafe-eval'" : ""
    }`,
    // Tailwind and Next inject a small amount of inline style data.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    // The browser talks to this origin only; the API is reached server-side.
    // Development allows the HMR websocket.
    `connect-src 'self'${
      isDevelopment ? " ws: wss: http://localhost:8000 https://localhost:8000" : ""
    }`,
    // Only in production: on http://localhost this would break hot reload.
    ...(isDevelopment ? [] : ["upgrade-insecure-requests"]),
  ];
  return directives.join("; ");
}

export function middleware(request: NextRequest): NextResponse {
  const nonce = btoa(crypto.randomUUID());
  const csp = buildCsp(nonce);

  // Next.js reads the nonce from the CSP header on the *request* and stamps it
  // onto every inline script it emits.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      /*
       * Static assets are served straight from the CDN-ish chunk directory and
       * need no policy of their own.
       */
      source: "/((?!_next/static|_next/image|favicon.ico).*)",
      /*
       * Prefetch requests are not rendered in the browser, so a fresh nonce for
       * each of them is wasted work.
       */
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
