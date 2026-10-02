import type { Metadata } from "next";
import Link from "next/link";

import { Card, CardBody, CardHeader, StatusPill } from "@verifyke/ui";
import { VERIFICATION_STATUSES, type VerificationStatus } from "@verifyke/shared-types";

import { VerificationForm } from "@/components/verification-form";

export const metadata: Metadata = {
  title: "Verify a certificate or document",
  description:
    "Enter a VerifyKE certificate number, scan the QR code, or upload a document to check it against the issuing institution's records.",
  robots: { index: false, follow: false },
};

const STATUS_HELP: Record<VerificationStatus, string> = {
  VERIFIED: "The issuer's record, the digital signature and the document content all agree.",
  SUSPECT:
    "Something does not add up - for example a repaired PDF or a QR code that points elsewhere. A human should review it.",
  FAILED: "A decisive check failed. The document does not match what the institution issued.",
  NOT_FOUND:
    "No certificate matches that number or document in any connected institution's records.",
  REVOKED: "The certificate was validly issued but has since been withdrawn by the institution.",
  EXPIRED:
    "The certificate is past its validity date; it may still be genuine, but it is no longer current.",
  PENDING:
    "Verification is still running, usually because a document is being analysed. Check again in a moment.",
};

export default function VerifyPage() {
  return (
    <div className="container-page grid gap-10 py-10 lg:grid-cols-[1fr_0.8fr] sm:py-14">
      <section>
        <h1 className="text-2xl sm:text-3xl">Verify a certificate or document</h1>
        <p className="mt-3 max-w-prose text-muted">
          Choose whichever of these you have to hand. All three paths lead to the same checks; none
          of them is trusted on its own.
        </p>

        <ol className="mt-6 space-y-4">
          {[
            {
              step: "1",
              title: "Certificate number",
              body: "Type the number printed under the QR code, for example VK-KE-2026-7FQ2M9XB4KD1-Q. Typos are caught before a request is sent.",
            },
            {
              step: "2",
              title: "QR code",
              body: "Scanning the QR code opens the verification page for exactly one certificate. A QR code reprinted onto another document will be reported as needing review - it is a pointer, not proof.",
            },
            {
              step: "3",
              title: "Upload a photo or PDF",
              body: "Upload the document itself. VerifyKE reads it, compares it with the issuer's record and looks for signs of alteration.",
            },
          ].map((item) => (
            <li key={item.step} className="flex gap-4">
              <span
                aria-hidden="true"
                className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-600 text-sm font-semibold text-white"
              >
                {item.step}
              </span>
              <div>
                <h2 className="text-base">{item.title}</h2>
                <p className="mt-1 text-sm text-muted">{item.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="mt-6 text-sm text-muted">
          Documents you upload are processed to answer this one query and deleted under our
          retention policy. Read more in{" "}
          <Link href="/privacy" className="underline hover:text-brand-700">
            Privacy &amp; data protection
          </Link>
          .
        </p>
      </section>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg">Look up a certificate</h2>
          </CardHeader>
          <CardBody>
            <VerificationForm />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg">What the results mean</h2>
          </CardHeader>
          <CardBody className="space-y-3">
            {VERIFICATION_STATUSES.map((status) => (
              <div key={status} className="space-y-1">
                <StatusPill status={status} />
                <p className="text-sm text-muted">{STATUS_HELP[status]}</p>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
