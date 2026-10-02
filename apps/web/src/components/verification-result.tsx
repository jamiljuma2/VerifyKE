import { Card, CardBody, CardHeader, StatusPill } from "@verifyke/ui";
import {
  STATUS_PRESENTATION,
  type CheckOutcome,
  type VerificationResult as VerificationResultData,
} from "@verifyke/shared-types";

const OUTCOME_STYLE: Record<CheckOutcome, { label: string; className: string; mark: string }> = {
  PASS: { label: "Passed", className: "text-verified", mark: "\u2713" },
  FAIL: { label: "Failed", className: "text-failed", mark: "\u00d7" },
  WARN: { label: "Warning", className: "text-suspect", mark: "!" },
  NOT_APPLICABLE: { label: "Not applicable", className: "text-muted", mark: "\u2013" },
  ERROR: { label: "Could not run", className: "text-muted", mark: "?" },
};

/**
 * Renders a verification result.
 *
 * Deliberate choices:
 * - The overall status is shown first, with the summary sentence that explains it.
 * - Every check is listed, including the ones that did not run. Hiding an
 *   inconclusive check would overstate confidence.
 * - No raw numbers are presented as a "score": a percentage would imply a
 *   precision the underlying evidence does not have.
 */
export function VerificationResultView({ result }: { result: VerificationResultData }) {
  const presentation = STATUS_PRESENTATION[result.status];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted">Result</p>
            <div className="mt-1">
              <StatusPill status={result.status} />
            </div>
          </div>
          <div className="text-right text-xs text-muted">
            <p>
              Evidence level:{" "}
              <span className="font-semibold text-slate-700">{result.evidence_level}</span>
            </p>
            <p className="mt-0.5">Checked {new Date(result.verified_at).toLocaleString()}</p>
          </div>
        </CardHeader>
        <CardBody>
          <p className="text-base text-slate-800">{result.summary}</p>
          <p className="mt-2 text-sm text-muted">{presentation.explanation}</p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-lg">Checks performed</h2>
          <p className="mt-1 text-sm text-muted">
            Each check is independent. A conclusion is only drawn when they agree.
          </p>
        </CardHeader>
        <CardBody>
          <ul className="divide-y divide-muted-border">
            {result.checks.map((check) => {
              const style = OUTCOME_STYLE[check.outcome];
              // Defensive: an unexpected outcome string must not crash the page.
              const safeStyle = style ?? OUTCOME_STYLE.ERROR;
              return (
                <li key={check.code} className="flex gap-3 py-3">
                  <span aria-hidden="true" className={`mt-0.5 font-mono ${safeStyle.className}`}>
                    {safeStyle.mark}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-slate-800">
                      {check.label}{" "}
                      <span className="font-normal text-muted">- {safeStyle.label}</span>
                    </p>
                    <p className="mt-0.5 text-sm text-muted">{check.detail}</p>
                  </div>
                </li>
              );
            })}
          </ul>
          {result.checks.length === 0 ? (
            <p className="text-sm text-muted">No checks were recorded for this result.</p>
          ) : null}
        </CardBody>
      </Card>

      {result.subject ? (
        <Card>
          <CardHeader>
            <h2 className="text-lg">Certificate details</h2>
          </CardHeader>
          <CardBody>
            <dl className="grid gap-3 sm:grid-cols-2">
              {(
                [
                  ["Certificate number", result.subject.certificate_id],
                  ["Holder", result.subject.holder_name],
                  ["Institution", result.subject.institution_name],
                  ["Qualification", result.subject.qualification],
                  ["Issued on", result.subject.issued_on],
                  ["Valid until", result.subject.valid_until],
                ] as const
              ).map(([label, value]) => (
                <div key={label}>
                  <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
                  <dd className="text-sm text-slate-800">{value ?? "Not disclosed"}</dd>
                </div>
              ))}
            </dl>
            {result.subject.holder_name === null ? (
              <p className="mt-3 text-xs text-muted">
                Holder details are hidden because this lookup was not authorised to see personal
                data.
              </p>
            ) : null}
          </CardBody>
        </Card>
      ) : null}

      <p className="text-xs text-muted">
        Verification reference <span className="font-mono">{result.verification_id}</span>. Quote
        this reference when contacting support about this result. VerifyKE reports what the checks
        found and does not itself certify authenticity.
      </p>
    </div>
  );
}
