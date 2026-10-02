import type { Metadata } from "next";
import Link from "next/link";

import { Card, CardBody, CardHeader } from "@verifyke/ui";

export const metadata: Metadata = {
  title: "For institutions",
  description:
    "Connect your institution to VerifyKE: push certificates through the API or in batches, and give every graduate a verifiable credential.",
};

const ONBOARDING = [
  {
    step: "1",
    title: "Registration and approval",
    body: "VerifyKE records who issues certificates in which country, under which regulator. Registration is reviewed before any certificate is accepted, because a connected institution defines what a VERIFIED result means.",
  },
  {
    step: "2",
    title: "Your signing keys",
    body: "Your institution holds versioned Ed25519 key pairs. Private keys are wrapped with AES-256-GCM under a master key held by VerifyKE, so a database compromise does not hand anyone the ability to forge your certificates. You can rotate a key at any time without invalidating certificates already issued.",
  },
  {
    step: "3",
    title: "Send certificates",
    body: "Push certificates individually through the issuance API or upload a batch. Every certificate is signed, hashed and given a public number that carries a checksum, so a mistyped number is caught before it becomes a support ticket.",
  },
  {
    step: "4",
    title: "Templates and branding",
    body: "Certificate layouts are defined as versioned templates, so an update to your format does not silently change documents already in circulation.",
  },
];

export default function ForInstitutionsPage() {
  return (
    <div className="container-page grid gap-10 py-10 sm:py-14 lg:grid-cols-[1.1fr_0.9fr]">
      <section>
        <h1 className="text-2xl sm:text-3xl">For institutions</h1>
        <p className="mt-3 max-w-prose text-muted">
          Universities, colleges and examining bodies connect once. After that, every certificate
          you issue can be verified by an employer, an agency or a member of the public without
          anyone phoning your registry.
        </p>

        <ol className="mt-6 space-y-4">
          {ONBOARDING.map((item) => (
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
          Automated checks? The{" "}
          <Link href="/developers" className="underline hover:text-brand-700">
            verification API
          </Link>{" "}
          describes the endpoints your systems call and the contract they return.
        </p>
      </section>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg">What your graduates get</h2>
          </CardHeader>
          <CardBody>
            <ul className="space-y-2 text-sm text-muted">
              <li>
                A certificate number printed under a QR code that resolves to exactly that
                certificate - not to a search page.
              </li>
              <li>
                Verification that works on a low-end phone over a slow connection: the result is
                rendered on the server, so it does not depend on a heavy JavaScript bundle.
              </li>
              <li>
                Evidence, not marketing: a result lists every check, including the ones that could
                not run.
              </li>
            </ul>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg">Access control</h2>
          </CardHeader>
          <CardBody className="space-y-2 text-sm text-muted">
            <p>
              Staff accounts are scoped to your institution in the application and in the database
              itself, so a missed filter cannot expose another institution&apos;s graduates.
            </p>
            <p>
              Administrative roles must enrol multi-factor authentication, and high-risk actions -
              key rotation, revocation, bulk export - require a fresh sign-in.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg">Every action is recorded</h2>
          </CardHeader>
          <CardBody>
            <p className="text-sm text-muted">
              Issuance, revocation, key changes and staff access are written to an append-only audit
              log with the actor, institution, time and request reference. If a question is ever
              raised about a certificate, the history is there to answer it.
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
