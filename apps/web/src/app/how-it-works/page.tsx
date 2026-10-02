import type { Metadata } from "next";

import { Card, CardBody, CardHeader, STATUS_PRESENTATION, StatusPill } from "@verifyke/ui";
import { VERIFICATION_STATUSES } from "@verifyke/shared-types";

export const metadata: Metadata = {
  title: "How verification works",
  description:
    "The independent checks behind every VerifyKE result: issuer records, digital signatures, content hashes, QR destinations, document structure and revocation.",
};

/** The checks are listed in the order the engine runs them. */
const CHECKS = [
  {
    code: "issuer_record",
    label: "Issuing institution's record",
    body: "The certificate number is resolved against the authoritative record held for the institution that issued it. A number that exists nowhere is NOT_FOUND, not FAILED.",
  },
  {
    code: "pdf_signature",
    label: "Digital signature",
    body: "Issued certificates carry an Ed25519 signature over an RFC 8785 canonical JSON payload, using the institution's key version recorded at issuance. Rotating a key never invalidates what was already signed.",
  },
  {
    code: "content_hash",
    label: "Content hash",
    body: "The SHA-256 of the exact bytes of the issued document is compared with the document in hand. A name or grade edited into the PDF changes the hash immediately.",
  },
  {
    code: "qr_destination",
    label: "QR destination",
    body: "The QR code must resolve to the certificate number printed on the same document. A legitimate QR reprinted onto a different certificate is reported as SUSPECT - a pointer is not proof.",
  },
  {
    code: "document_structure",
    label: "Document structure and metadata",
    body: "Page structure, incremental updates and producer metadata are inspected for signs of repair or re-assembly.",
  },
  {
    code: "revocation",
    label: "Revocation and validity",
    body: "A certificate withdrawn by its institution is REVOKED; one past its validity date is EXPIRED. Both are reported as their own statuses rather than as failures.",
  },
];

export default function HowItWorksPage() {
  return (
    <div className="container-page grid gap-10 py-10 sm:py-14 lg:grid-cols-[1.1fr_0.9fr]">
      <section>
        <h1 className="text-2xl sm:text-3xl">How verification works</h1>
        <p className="mt-3 max-w-prose text-muted">
          No single signal decides a result. Each check is independent, each one is reported, and a
          check that could not run is shown as not applicable rather than quietly counted as a pass.
        </p>

        <ol className="mt-6 space-y-4">
          {CHECKS.map((check) => (
            <li key={check.code} className="border-l-2 border-muted-border pl-4">
              <h2 className="text-base">{check.label}</h2>
              <p className="mt-1 text-sm text-muted">{check.body}</p>
              <p className="mt-1 font-mono text-xs text-slate-500">{check.code}</p>
            </li>
          ))}
        </ol>

        <p className="mt-6 max-w-prose text-sm text-muted">
          VerifyKE reports what the checks found. It does not certify authenticity on its own, and
          it never presents a confidence percentage: the evidence is listed so that you can judge
          it.
        </p>
      </section>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg">What each status means</h2>
          </CardHeader>
          <CardBody className="space-y-4">
            {VERIFICATION_STATUSES.map((status) => (
              <div key={status} className="space-y-1">
                <StatusPill status={status} />
                <p className="text-sm text-muted">{STATUS_PRESENTATION[status].explanation}</p>
              </div>
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg">The case a QR-only checker misses</h2>
          </CardHeader>
          <CardBody>
            <p className="text-sm text-muted">
              A genuine QR code is photographed from certificate A and printed onto a forged
              certificate B. The QR resolves, the number is real, and the scan looks perfect.
              Because the number on the document in hand belongs to B, the issuer record, signature
              and content hash disagree - and the result is SUSPECT instead of VERIFIED.
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
