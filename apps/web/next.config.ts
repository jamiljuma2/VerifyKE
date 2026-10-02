import type { NextConfig } from "next";

/**
 * VerifyKE web configuration.
 *
 * Security posture:
 * - `standalone` output keeps the container image small (see Dockerfile.web).
 * - `poweredByHeader: false` avoids advertising the framework version.
 * - A strict Content-Security-Policy is applied to every response. `unsafe-inline`
 *   is required only for styles (Tailwind/Next inject a small amount of inline
 *   CSS); scripts are restricted to same-origin.
 * - Images render through Next's optimiser so that untrusted documents are never
 *   served straight from their origin.
 */
const isProduction = process.env.NODE_ENV === "production";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(self), geolocation=(), microphone=(), payment=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      "script-src 'self' " + (isProduction ? "" : "'unsafe-eval'"),
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "connect-src 'self' " + (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"),
      "upgrade-insecure-requests",
    ].join("; "),
  },
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
