import type { Metadata } from "next";
import Link from "next/link";

import type { VerificationResult } from "@verifyke/shared-types";
import { Card, CardBody, CardHeader, StatusPill } from "@verifyke/ui";

import { VerificationResultView } from "@/components/verification-result";
import { isCertificateIdShapeValid, normaliseCertificateId } from "@/lib/certificate-id";
import { serverApiFetch } from "@/lib/server-api";

/**
 * Certificate result page.
 *
 * The lookup happens on the server so the browser never receives a token it could
 * replay, and so the result renders without a client-side loading flash on slow
 * connections. The identifier is validated for shape first: a malformed number is
 * reported as such without spending an API call.
 */

export const metadata: Metadata = {
  title: "Verification result",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default async function CertificateResultPage({
  params,
}: {
  params: Promise<{ certificateId: string }>;
}) {
  const { certificateId } = await params;
  const normalised = normaliseCertificateId(decodeURIComponent(certificateId));

  if (!isCertificateIdShapeValid(normalised)) {
    return (
      <div className="container-page py-12">
        <Card className="max-w-2xl">
          <CardHeader>
            <h1 className="text-xl">That certificate number is not valid</h1>
          </CardHeader>
          <CardBody className="space-y-3 text-sm text-muted">
            <p>
              <span className="font-mono text-slate-800">{certificateId}</span> is not a VerifyKE
              certificate number. The expected format is{" "}
              <span className="font-mono">VK-KE-2026-XXXXXXXXXXXX-Q</span>, printed under the QR
              code on the document.
            </p>
            <p>
              If you copied it from a printed certificate, check the characters carefully: the
              letter O is never used (it is a zero), and neither are I or L (they are ones).
            </p>
            <p>
              <Link href="/verify" className="underline hover:text-brand-700">
                Try another number
              </Link>
            </p>
          </CardBody>
        </Card>
      </div>
    );
  }

  const response = await serverApiFetch<VerificationResult>(
    `/api/v1/verify/${encodeURIComponent(normalised)}`,
  );

  if (!response.ok || !response.data) {
    const notFound = response.error?.code === "NOT_FOUND";
    return (
      <div className="container-page py-12">
        <Card className="max-w-2xl">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h1 className="text-xl">
                {notFound ? "No matching certificate" : "We could not complete the check"}
              </h1>
              {notFound ? <StatusPill status="NOT_FOUND" /> : null}
            </div>
          </CardHeader>
          <CardBody className="space-y-3 text-sm text-muted">
            <p>
              {notFound
                ? "No connected institution has issued a certificate with this number. Check the number, or ask the institution that issued the document to confirm it."
                : (response.error?.message ?? "Please try again in a moment.")}
            </p>
            <p className="font-mono text-xs">
              Reference: {normalised}
              {response.error?.requestId ? ` - ${response.error.requestId}` : ""}
            </p>
            <p className="space-x-3">
              <Link href="/verify" className="underline hover:text-brand-700">
                Try another number
              </Link>
              <Link href="/verify/upload" className="underline hover:text-brand-700">
                Upload the document instead
              </Link>
            </p>
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <div className="container-page py-10">
      <nav aria-label="Breadcrumb" className="mb-4 text-sm text-muted">
        <Link href="/verify" className="hover:text-brand-700">
          Verify
        </Link>
        <span aria-hidden="true"> / </span>
        <span className="font-mono text-slate-700">{normalised}</span>
      </nav>
      <VerificationResultView result={response.data} />
    </div>
  );
}
