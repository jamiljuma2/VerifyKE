"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { isCertificateIdShapeValid } from "@/lib/certificate-id";

type Mode = "id" | "qr";

/**
 * Entry point for a verification.
 *
 * The form performs *shape* validation only, so a user gets immediate feedback
 * without a round trip. Whether a certificate actually exists is decided by the
 * API, never by the browser.
 */
export function VerificationForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("id");
  const [certificateId, setCertificateId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = certificateId.trim();

    if (!value) {
      setError("Enter the certificate number printed on the document.");
      return;
    }
    if (!isCertificateIdShapeValid(value)) {
      setError(
        "That does not look like a VerifyKE certificate number. It looks like VK-KE-2026-XXXXXXXXXXXX-Q.",
      );
      return;
    }

    setError(null);
    setSubmitting(true);
    router.push(`/verify/${encodeURIComponent(value.toUpperCase())}`);
  }

  return (
    <div>
      <div
        role="tablist"
        aria-label="Verification method"
        className="mb-4 grid grid-cols-2 gap-1 rounded-lg bg-muted-soft p-1 text-sm font-medium"
      >
        {(
          [
            { id: "id", label: "Certificate number" },
            { id: "qr", label: "QR / upload" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={mode === tab.id}
            onClick={() => setMode(tab.id)}
            className={
              mode === tab.id
                ? "rounded-md bg-white px-3 py-2 text-brand-700 shadow-sm"
                : "rounded-md px-3 py-2 text-muted hover:text-slate-700"
            }
          >
            {tab.label}
          </button>
        ))}
      </div>

      {mode === "id" ? (
        <form onSubmit={handleSubmit} noValidate>
          <label htmlFor="certificate-id" className="field-label">
            Certificate number
          </label>
          <input
            id="certificate-id"
            name="certificate-id"
            className="field-input font-mono uppercase"
            placeholder="VK-KE-2026-7FQ2M9XB4KD1-Q"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            inputMode="text"
            maxLength={32}
            value={certificateId}
            onChange={(event) => setCertificateId(event.target.value)}
            aria-invalid={error !== null}
            aria-describedby={error ? "certificate-id-error" : undefined}
          />

          {error ? (
            <p id="certificate-id-error" role="alert" className="mt-2 text-sm text-failed">
              {error}
            </p>
          ) : (
            <p className="mt-2 text-xs text-muted">
              Printed on the certificate, under the QR code.
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-4 w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-60"
          >
            {submitting ? "Checking\u2026" : "Verify certificate"}
          </button>
        </form>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted">
            Point your phone camera at the QR code on the certificate. If it will not scan, upload a
            photo or PDF instead.
          </p>
          <a
            href="/verify/upload"
            className="block w-full rounded-lg bg-brand-600 px-4 py-2.5 text-center text-sm font-semibold text-white transition-colors hover:bg-brand-700"
          >
            Upload a document
          </a>
        </div>
      )}
    </div>
  );
}
