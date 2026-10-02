import type { Metadata } from "next";

import { Card, CardBody, CardHeader } from "@verifyke/ui";

export const metadata: Metadata = {
  title: "Verification API",
  description:
    "Machine-to-machine certificate verification for employers and agencies: endpoints, authentication, rate limits and the response contract.",
};

const ENDPOINTS = [
  {
    method: "GET",
    path: "/api/v1/verify/{certificate_id}",
    body: "Look up a certificate by its public number. Returns the status and every check that produced it.",
  },
  {
    method: "POST",
    path: "/api/v1/verify/upload",
    body: "Submit a document to be analysed. Returns 202 with a verification id; poll the result endpoint until the status is final.",
  },
  {
    method: "GET",
    path: "/api/v1/verify/{verification_id}",
    body: "Read a verification result, including uploads that are still processing (status PENDING).",
  },
];

const LIMITS = [
  { route: "Public certificate lookup", limit: "60 per minute per IP" },
  { route: "Document upload", limit: "20 per 5 minutes per IP" },
  { route: "External verification API", limit: "600 per minute per API key" },
];

export default function DevelopersPage() {
  return (
    <div className="container-page grid gap-10 py-10 sm:py-14 lg:grid-cols-[1.1fr_0.9fr]">
      <section>
        <h1 className="text-2xl sm:text-3xl">Verification API</h1>
        <p className="mt-3 max-w-prose text-muted">
          Employers, agencies and background-check providers can verify without a person clicking
          through a form. The API returns the same evidence a person sees: a status plus the
          individual checks behind it.
        </p>

        <h2 className="mt-8 text-lg">Endpoints</h2>
        <ul className="mt-3 space-y-3">
          {ENDPOINTS.map((endpoint) => (
            <li key={endpoint.path} className="border-l-2 border-muted-border pl-4">
              <p className="font-mono text-sm">
                <span className="mr-2 font-semibold text-brand-700">{endpoint.method}</span>
                {endpoint.path}
              </p>
              <p className="mt-1 text-sm text-muted">{endpoint.body}</p>
            </li>
          ))}
        </ul>

        <h2 className="mt-8 text-lg">Response contract</h2>
        <p className="mt-3 max-w-prose text-sm text-muted">
          Successful responses carry the verification id, the status, an evidence level, a
          plain-language summary, the list of checks and the certificate details appropriate to the
          caller&apos;s authorisation. Errors always use one envelope, and never leak internals:
        </p>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-muted-soft p-4 font-mono text-xs leading-relaxed">
          {`{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please slow down and try again shortly.",
    "request_id": "…"
  }
}`}
        </pre>
        <p className="mt-3 text-sm text-muted">
          Quote the <code className="font-mono">request_id</code> in a support request: it ties a
          failure to the exact request in the logs, without exposing anything else.
        </p>
      </section>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg">Authentication</h2>
          </CardHeader>
          <CardBody className="space-y-2 text-sm text-muted">
            <p>
              Machine-to-machine calls authenticate with an API key issued per organisation. Keys
              are stored hashed and can be rotated without downtime; the previous key stays valid
              until you revoke it.
            </p>
            <p>
              Public lookups need no credentials, which is why they are rate-limited per IP. Bulk
              access requires a key so that the volume is attributable.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg">Rate limits</h2>
          </CardHeader>
          <CardBody>
            <dl className="space-y-3 text-sm">
              {LIMITS.map((row) => (
                <div key={row.route} className="flex flex-wrap justify-between gap-2">
                  <dt className="text-slate-800">{row.route}</dt>
                  <dd className="font-mono text-muted">{row.limit}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-xs text-muted">
              Limits are configurable per deployment; the values above are the defaults. A 429
              response includes a Retry-After header.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg">Uploads</h2>
          </CardHeader>
          <CardBody>
            <ul className="space-y-2 text-sm text-muted">
              <li>PDF, PNG or JPEG, at most 10 MB per file.</li>
              <li>PDFs up to 20 pages; images up to 40 megapixels.</li>
              <li>Type is decided by magic bytes, not by the filename or content type you send.</li>
              <li>Files are scanned before parsing and deleted on the retention schedule.</li>
            </ul>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
