import type { Metadata } from "next";

import { ButtonLink, Card, CardBody, CardHeader } from "@verifyke/ui";

import { VerificationForm } from "@/components/verification-form";

export const metadata: Metadata = {
  title: "Verify a Kenyan certificate in seconds",
  description:
    "Scan a QR code, type a certificate number or upload a document. VerifyKE checks the issuer record, the cryptographic signature and the document content before returning a result.",
  // The marketing page is the one page search engines may index.
  robots: { index: true, follow: true },
};

const SIGNALS = [
  {
    title: "Issuer record",
    body: "The certificate must exist in the issuing institution's authoritative records, not merely look plausible.",
  },
  {
    title: "Cryptographic signature",
    body: "Every issued certificate is signed with the institution's Ed25519 key and verified against the key version that was active at issue time.",
  },
  {
    title: "Content hash",
    body: "The PDF you hold is hashed (SHA-256) and compared with the hash recorded at issuance - a single altered character is detected.",
  },
  {
    title: "QR destination",
    body: "A QR code is only a pointer. A copied or re-printed QR that leads to a different certificate is flagged, never trusted.",
  },
  {
    title: "Document structure",
    body: "Fonts, layout, metadata and edit history are examined for signs of tampering or digital reconstruction.",
  },
  {
    title: "Revocation and expiry",
    body: "Withdrawn, expired or suspended certificates are reported as such, even when the printed document looks perfect.",
  },
];

export default function HomePage() {
  return (
    <div className="container-page py-10 sm:py-14">
      <section className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-brand-600">
            Trust Every Credential. Verify Every Certificate.
          </p>
          <h1 className="mt-3 text-3xl sm:text-4xl">
            Check a certificate before you trust it - in seconds.
          </h1>
          <p className="mt-4 max-w-prose text-base text-muted">
            VerifyKE confirms that a document is genuine and unaltered by checking it against the
            institution that issued it. Employers, universities, licensing bodies and individuals
            get a clear answer with the evidence behind it - not just a green tick.
          </p>

          <ul className="mt-6 space-y-3 text-base">
            {[
              "Scan the QR code on the document",
              "Or type the certificate number",
              "Or upload a photo or PDF of the certificate",
            ].map((item) => (
              <li key={item} className="flex items-start gap-3 text-slate-700">
                <span aria-hidden="true" className="mt-0.5 text-brand-600">
                  &#10003;
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>

          <div className="mt-8 flex flex-wrap gap-3">
            <ButtonLink href="/verify">Verify a document</ButtonLink>
            <ButtonLink href="/for-institutions" variant="secondary">
              I issue certificates
            </ButtonLink>
          </div>
        </div>

        <Card className="lg:sticky lg:top-24">
          <CardHeader>
            <h2 className="text-lg">Start a verification</h2>
            <p className="mt-1 text-sm text-muted">
              No account needed. Your document is processed securely and deleted according to our
              retention policy.
            </p>
          </CardHeader>
          <CardBody>
            <VerificationForm />
          </CardBody>
        </Card>
      </section>

      <section aria-labelledby="signals" className="mt-16">
        <h2 id="signals" className="text-2xl">
          Six independent signals, reported honestly
        </h2>
        <p className="mt-2 max-w-prose text-muted">
          A &quot;verified&quot; result means multiple independent checks passed. If a check could
          not run, it is shown as not applicable rather than counted as a pass.
        </p>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SIGNALS.map((signal, index) => (
            <Card key={signal.title} className="h-full">
              <CardBody>
                <p className="font-mono text-xs text-brand-600">0{index + 1}</p>
                <h3 className="mt-1 text-base">{signal.title}</h3>
                <p className="mt-2 text-sm text-muted">{signal.body}</p>
              </CardBody>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
