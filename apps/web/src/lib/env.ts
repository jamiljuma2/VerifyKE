import { z } from "zod";

/**
 * Validated public (browser-visible) environment.
 *
 * Only `NEXT_PUBLIC_*` values may live here - anything else would be inlined
 * into the client bundle and leak. Secrets belong on the server (see
 * `server-env.ts`).
 */
const publicEnvSchema = z.object({
  NEXT_PUBLIC_API_BASE_URL: z.string().url().default("http://localhost:8000"),
  NEXT_PUBLIC_WEB_BASE_URL: z.string().url().default("http://localhost:3000"),
});

export type PublicEnv = z.infer<typeof publicEnvSchema>;

export function readPublicEnv(): PublicEnv {
  const parsed = publicEnvSchema.safeParse({
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
    NEXT_PUBLIC_WEB_BASE_URL: process.env.NEXT_PUBLIC_WEB_BASE_URL,
  });

  if (!parsed.success) {
    // Fail loudly at startup rather than producing broken links at runtime.
    throw new Error(
      `Invalid public environment configuration: ${parsed.error.issues
        .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
        .join("; ")}`,
    );
  }
  return parsed.data;
}

export const publicEnv: PublicEnv = readPublicEnv();
