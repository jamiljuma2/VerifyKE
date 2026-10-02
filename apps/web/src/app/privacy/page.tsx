import type { Metadata } from "next";

import { Card, CardBody, CardHeader } from "@verifyke/ui";

export const metadata: Metadata = {
  title: "Privacy and data protection",
  description:
    "What VerifyKE collects when you verify a document, how long it keeps it, who can see holder details, and how to get a copy of your data.",
};

/** Defaults from the deployment configuration; deployments may shorten them. */
const RETENTION = [
  { item: "Uploaded documents", detail: "30 days" },
  { item: "Verification events", detail: "Retained while the certificate is current" },
  { item: "Audit log", detail: "7 years" },
];

export default function PrivacyPage() {
  return (
    <div className="container-page grid gap-10 py-10 sm:py-14 lg:grid-cols-[1.1fr_0.9fr]">
      <section>
        <h1 className="text-2xl sm:text-3xl">Privacy &amp; data protection</h1>
        <p className="mt-3 max-w-prose text-muted">
          Verifying a document means handling personal data, so the collection is deliberately
          small. VerifyKE is operated under the principles of the Kenya Data Protection Act:
          personal data is processed for a stated purpose, kept only as long as that purpose needs
          it, and never sold.
        </p>

        <h2 className="mt-8 text-lg">What a verification records</h2>
        <ul className="mt-3 space-y-2 text-sm text-muted">
          <li>
            The certificate number that was checked, the outcome, and each individual check that
            produced it.
          </li>
          <li>
            When the check happened and through which route - number, QR code or uploaded document.
          </li>
          <li>
            Holder details from the issuer&apos;s record, shown only where the lookup is authorised
            to see them.
          </li>
        </ul>

        <h2 className="mt-8 text-lg">Public results are masked</h2>
        <p className="mt-3 max-w-prose text-sm text-muted">
          By default a public result shows that a certificate exists and whether it checks out, not
          the holder&apos;s full name. Unmasked details require an authorised verifier or the
          holder&apos;s own access code, and every such disclosure is recorded in the verification
          history.
        </p>

        <h2 className="mt-8 text-lg">Uploads are transient</h2>
        <p className="mt-3 max-w-prose text-sm text-muted">
          A photo or PDF you upload is analysed to answer that one question and then deleted on the
          retention schedule below. The verification result and its audit entry remain, because they
          are the record that the check happened - not a copy of the document.
        </p>

        <h2 className="mt-8 text-lg">Your rights</h2>
        <p className="mt-3 max-w-prose text-sm text-muted">
          To see the personal data VerifyKE holds about you, to correct it, or to ask for it to be
          removed, contact the institution that issued the certificate - they are the source of the
          record - and they will pass the request to us. We respond within the statutory period.
        </p>
      </section>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg">Retention</h2>
          </CardHeader>
          <CardBody>
            <dl className="space-y-3 text-sm">
              {RETENTION.map((row) => (
                <div key={row.item}>
                  <dt className="font-medium text-slate-800">{row.item}</dt>
                  <dd className="text-muted">{row.detail}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-xs text-muted">
              Uploads may be deleted sooner on request. The audit log is kept longer because it is
              the evidence of what was issued, changed or accessed.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg">What we never do</h2>
          </CardHeader>
          <CardBody>
            <ul className="space-y-2 text-sm text-muted">
              <li>Sell or rent personal data.</li>
              <li>Use an uploaded document for training or advertising.</li>
              <li>Report a holder as fraudulent because an OCR pass was inconclusive.</li>
              <li>
                Reveal whether a certificate number belongs to a named institution to an anonymous
                caller beyond what the verification requires.
              </li>
            </ul>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg">Abuse</h2>
          </CardHeader>
          <CardBody>
            <p className="text-sm text-muted">
              Bulk lookups of other people&apos;s documents are rate-limited and monitored as an
              anomaly signal. Verification history - who checked what, when - exists precisely so
              that patterns like this are visible.
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
