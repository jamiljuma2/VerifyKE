/**
 * @verifyke/shared-types
 *
 * Single source of truth for the contracts shared by the FastAPI backend and
 * every TypeScript client. Values here are copied verbatim from the API's
 * documentation so that a status string can never drift between the services.
 */
export * from "./verification";
export * from "./auth";
export * from "./api-error";
export * from "./system";
