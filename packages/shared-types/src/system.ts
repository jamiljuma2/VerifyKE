/**
 * Service metadata and probe payloads (mirrors the API's /health, /version and
 * /ready responses).
 */

export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  uptime_seconds: number;
}

export interface VersionResponse {
  service: string;
  version: string;
  environment: "development" | "test" | "production";
}

export interface DependencyState {
  status?: "ok" | "error";
  available?: boolean;
  version?: string;
  error?: string;
}

export interface ReadinessResponse {
  status: "ok" | "degraded";
  dependencies: Record<"database" | "redis", DependencyState>;
}
