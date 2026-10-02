import type { Metadata } from "next";
import Link from "next/link";

import { Card, CardBody, CardHeader } from "@verifyke/ui";

import { UploadForm } from "@/components/upload-form";

export const metadata: Metadata = {
  title: "Verify an uploaded document",
  description:
    "Upload a photo or PDF of a certificate. VerifyKE reads it, compares it with the issuer's record and reports what it found.",
  robots: { index: false, follow: false },
};

export default function UploadVerifyPage() {
  return (
    <div className="container-page py-10 sm:py-14">
      <nav aria-label="Breadcrumb" className="mb-4 text-sm text-muted">
        <Link href="/verify" className="hover:text-brand-700">
          Verify
        </Link>
        <span aria-hidden="true"> / </span>
        <span className="text-slate-700">Upload a document</span>
      </nav>

      <h1 className="text-2xl sm:text-3xl">Check a certificate you have in hand</h1>
      <p className="mt-3 max-w-prose text-muted">
        Upload a photo or PDF and VerifyKE will read the certificate number, look the certificate up
        with the issuer, and compare the document you uploaded with the record on file. Alterations
        show up as mismatches in the content hash, the layout or the file&apos;s own metadata.
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <h2 className="text-lg">Upload the document</h2>
          </CardHeader>
          <CardBody>
            <UploadForm />
          </CardBody>
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <h2 className="text-lg">Before you upload</h2>
          </CardHeader>
          <CardBody className="space-y-3 text-sm text-muted">
            <p>
              Uploads are used only to answer this check. They are deleted under our retention
              policy once the result has been produced and its audit record written.
            </p>
            <p>
              Do not upload documents that are not yours to check. Every access to a certificate
              record is logged, and repeated lookups of other people&apos;s documents are flagged.
            </p>
            <p>
              This is not a substitute for contacting the issuing institution. VerifyKE reports what
              the evidence shows; the institution remains the authority on its own certificates.
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
