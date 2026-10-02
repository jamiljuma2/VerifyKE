"use client";

import { useRef, useState, type ChangeEvent } from "react";

import type { VerificationResult } from "@verifyke/shared-types";

import { ApiError, apiUpload } from "@/lib/api-client";
import { VerificationResultView } from "./verification-result";

/** Mirrors the server-side limits so a bad file is rejected before it is sent. */
const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPTED_TYPES = ["application/pdf", "image/png", "image/jpeg"];
const ACCEPTED_LABEL = "PDF, PNG or JPEG";

type Stage = "idle" | "checking" | "done";

/**
 * Document upload verification.
 *
 * Client-side checks are convenience only: the API re-validates the MIME type by
 * sniffing the file's magic bytes, enforces the same size limit, and runs malware
 * scanning when it is enabled. Nothing is uploaded until the user presses the
 * button, and the file is never stored in this component's state beyond the
 * native file handle.
 */
export function UploadForm() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [apiError, setApiError] = useState<ApiError | null>(null);

  function describeFile(selected: File | null): string | null {
    if (!selected) {
      return "Choose the certificate file to check.";
    }
    if (selected.size === 0) {
      return "That file is empty.";
    }
    if (selected.size > MAX_BYTES) {
      return `That file is larger than ${Math.round(MAX_BYTES / (1024 * 1024))} MB. Compress it or photograph the certificate at a lower resolution.`;
    }
    if (!ACCEPTED_TYPES.includes(selected.type)) {
      return `Unsupported file type. Upload a ${ACCEPTED_LABEL} file.`;
    }
    return null;
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setResult(null);
    setApiError(null);
    setClientError(selected ? describeFile(selected) : null);
  }

  async function handleSubmit() {
    const problem = describeFile(file);
    if (problem || !file) {
      setClientError(problem);
      return;
    }

    setClientError(null);
    setApiError(null);
    setStage("checking");

    const formData = new FormData();
    formData.append("file", file);
    // The client declares how it obtained the document; the server records it for
    // audit purposes but never trusts it for the decision itself.
    formData.append("channel", "UPLOAD_IMAGE");

    try {
      const response = await apiUpload<VerificationResult>("/api/v1/verify/upload", formData);
      setResult(response);
    } catch (error) {
      setApiError(
        error instanceof ApiError
          ? error
          : new ApiError({ code: "INTERNAL_ERROR", message: "Something went wrong.", status: 500 }),
      );
    } finally {
      setStage("done");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <label htmlFor="document" className="field-label">
          Certificate file ({ACCEPTED_LABEL}, up to 10 MB)
        </label>
        <input
          ref={inputRef}
          id="document"
          name="document"
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          onChange={handleFileChange}
          className="block w-full cursor-pointer rounded-lg border border-muted-border bg-white px-3 py-2.5 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-brand-700"
          aria-invalid={clientError !== null}
          aria-describedby={clientError ? "document-error" : "document-hint"}
        />

        {clientError ? (
          <p id="document-error" role="alert" className="mt-2 text-sm text-failed">
            {clientError}
          </p>
        ) : (
          <p id="document-hint" className="mt-2 text-xs text-muted">
            Photograph the whole certificate, flat and well lit. Do not crop the QR code or the
            certificate number.
          </p>
        )}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={stage === "checking" || file === null}
          className="mt-4 w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-60 sm:w-auto"
        >
          {stage === "checking" ? "Checking the document\u2026" : "Check this document"}
        </button>
      </div>

      {apiError ? (
        <div role="alert" className="rounded-lg border border-failed-border bg-failed-soft p-4">
          <p className="text-sm font-medium text-failed">{apiError.message}</p>
          {apiError.requestId ? (
            <p className="mt-1 font-mono text-xs text-muted">Reference: {apiError.requestId}</p>
          ) : null}
          {apiError.code === "RATE_LIMITED" ? (
            <p className="mt-2 text-sm text-muted">
              Too many checks from this connection. Wait a few minutes before trying again.
            </p>
          ) : null}
        </div>
      ) : null}

      {result ? <VerificationResultView result={result} /> : null}
    </div>
  );
}
