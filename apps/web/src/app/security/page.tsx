import type { Metadata } from "next";

import { Card, CardBody, CardHeader } from "@verifyke/ui";

export const metadata: Metadata = {
  title: "Security",
  description:
    "How VerifyKE secures certificate issuance and verification: signed payloads, wrapped keys, tenant isolation, session policy and auditing.",
};

const CONTROLS = [
  {
    title: "Certificates are signed, not trusted",
    body: "Every issued certificate carries an Ed25519 signature over an RFC 8785 canonical JSON payload plus a SHA-256 hash of the exact bytes of the document. Verification checks the signature against the key version recorded at issuance.",
  },
  {
    title: "Private keys never sit at rest in the clear",
    body: "Institution signing keys are wrapped with AES-256-GCM under a master key held outside the database, and each wrapped key is bound to its institution and version. Copying a stored key to another record does not decrypt it.",
  },
  {
    title: "Tenant isolation has two independent layers",
    body: "Every query is scoped to the caller's institution in the application, and PostgreSQL row-level security enforces the same boundary at the database, so a missed filter still cannot read another institution's data.",
  },
  {
    title: "Sessions are short and rotated",
    body: "Access tokens live in HttpOnly, Secure, SameSite=Strict cookies and expire in ten minutes. Refresh tokens are rotated on every use, stored hashed and bound to a device fingerprint, so a replayed token is detected.",
  },
  {
    title: "State-changing requests need a CSRF token",
    body: "Cookies are SameSite=Strict and every state-changing request additionally requires a double-submit token, so a cross-site request cannot issue, revoke or export anything.",
  },
  {
    title: "Uploads are treated as hostile input",
    body: "Uploads are bounded by size, type, page count and pixel count, their type is decided by magic bytes rather than by the filename or the browser's header, and they are scanned before parsing. Page and pixel limits defeat decompression bombs.",
  },
];

export default function SecurityPage() {
  return (
    <div className="container-page grid gap-10 py-10 sm:py-14 lg:grid-cols-[1.1fr_0.9fr]">
      <section>
        <h1 className="text-2xl sm:text-3xl">Security</h1>
        <p className="mt-3 max-w-prose text-muted">
          The threat VerifyKE is built against is the forger: someone with a copied QR code, an
          edited PDF or stolen credentials. Each control below exists to close one of those paths,
          and each is verifiable rather than asserted.
        </p>

        <dl className="mt-6 space-y-4">
          {CONTROLS.map((control) => (
            <div key={control.title} className="border-l-2 border-muted-border pl-4">
              <dt className="text-base">{control.title}</dt>
              <dd className="mt-1 text-sm text-muted">{control.body}</dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg">Key rotation without downtime</h2>
          </CardHeader>
          <CardBody className="space-y-2 text-sm text-muted">
            <p>
              A new key version becomes active and the previous one is marked retired. Existing
              certificates keep verifying, because verification selects the key version recorded on
              the certificate rather than the current one. Nothing has to be re-issued.
            </p>
            <p>
              If a key is believed to be compromised, the version is marked as such, affected
              certificates are listed, the institution is notified, and certificates are re-issued
              from the new key.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg">Audit and monitoring</h2>
          </CardHeader>
          <CardBody className="space-y-2 text-sm text-muted">
            <p>
              The audit log is append-only and records the actor, institution, action, target, IP,
              user agent and request reference for sensitive actions.
            </p>
            <p>
              Security events - repeated failed sign-ins, MFA resets, key rotations, role changes,
              unusual verification volume - raise alerts with severity levels.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg">Reporting a vulnerability</h2>
          </CardHeader>
          <CardBody>
            <p className="text-sm text-muted">
              If you believe you have found a security issue, please report it through your
              institution&apos;s VerifyKE account contact rather than in a public channel, and give
              us the verification reference and request id from the result involved. We will confirm
              receipt and keep you informed while it is investigated.
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
