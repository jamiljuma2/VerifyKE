import type { NextConfig } from "next";

/**
 * VerifyKE web configuration.
 *
 * Security posture:
 * - `standalone` output keeps the container image small (see Dockerfile.web).
 * - `poweredByHeader: false` avoids advertising the framework version.
 * - Images render through Next's optimiser so that untrusted documents are never
 *   served straight from their origin.
 *
 * Content-Security-Policy is **not** set here. It is applied per request by
 * `src/middleware.ts`, which mints a nonce so Next's inline bootstrap scripts are
 * allowed without resorting to `'unsafe-inline'`. A policy declared statically
 * here would be sent alongside the nonce-based one, and the browser enforces the
 * *intersection* of multiple policies - which would block the very scripts that
 * nonce was added to permit.
 */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(self), geolocation=(), microphone=(), payment=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: "standalone",
  // Workspace packages ship TypeScript source; Next compiles them in-place.
  transpilePackages: ["@verifyke/shared-types", "@verifyke/ui"],
  // Surfaces accidental client-side use of server-only modules.
  // (Moved out of `experimental` in Next 15.5; the old location still works but warns.)
  typedRoutes: true,
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
