import { NextResponse } from "next/server";

/**
 * Container liveness endpoint (used by the Docker HEALTHCHECK and the load
 * balancer). It deliberately checks nothing but the web process itself: the
 * API's own `/ready` endpoint is the source of truth for dependency health.
 */
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json(
    {
      status: "ok",
      service: "verifyke-web",
      git_sha: process.env.VERIFYKE_GIT_SHA ?? "unknown",
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
