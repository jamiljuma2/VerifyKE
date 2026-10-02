/**
 * Roles and authentication contracts.
 */

export const ROLES = [
  "SUPER_ADMIN",
  "INSTITUTION_ADMIN",
  "INSTITUTION_ISSUER",
  "VERIFIER",
  "AUDITOR",
] as const;

export type Role = (typeof ROLES)[number];

export const ROLE_LABELS: Record<Role, string> = {
  SUPER_ADMIN: "Platform administrator",
  INSTITUTION_ADMIN: "Institution administrator",
  INSTITUTION_ISSUER: "Certificate issuer",
  VERIFIER: "Verifier",
  AUDITOR: "Compliance auditor",
};

/** Roles that must enrol multi-factor authentication before using the platform. */
export const MFA_REQUIRED_ROLES: readonly Role[] = ["SUPER_ADMIN", "INSTITUTION_ADMIN"];

export function requiresMfa(role: Role): boolean {
  return MFA_REQUIRED_ROLES.includes(role);
}

export const MFA_METHODS = ["TOTP", "RECOVERY_CODE"] as const;
export type MfaMethod = (typeof MFA_METHODS)[number];
export const API_KEY_SCOPES = [
  "verify:certificate",
  "verify:document",
  "verify:bulk",
  "read:usage",
] as const;
export type ApiKeyScope = (typeof API_KEY_SCOPES)[number];
