import Link from "next/link";

/**
 * Public site footer.
 *
 * The trust statement is deliberately precise: VerifyKE reports what the checks
 * found and never claims to certify authenticity on its own.
 */
export function SiteFooter() {
  return (
    <footer className="no-print mt-16 border-t border-muted-border bg-white">
      <div className="container-page grid gap-8 py-10 sm:grid-cols-3">
        <div>
          <p className="font-semibold text-brand-700">VerifyKE</p>
          <p className="mt-2 max-w-prose text-sm text-muted">
            Trust Every Credential. Verify Every Certificate. Results are evidence-based: every
            status lists the independent checks that produced it.
          </p>
        </div>

        <nav aria-label="Product" className="text-sm">
          <p className="font-semibold text-slate-800">Product</p>
          <ul className="mt-2 space-y-1.5 text-muted">
            <li>
              <Link href="/verify" className="hover:text-brand-700">
                Verify a certificate
              </Link>
            </li>
            <li>
              <Link href="/for-institutions" className="hover:text-brand-700">
                For institutions
              </Link>
            </li>
            <li>
              <Link href="/developers" className="hover:text-brand-700">
                Verification API
              </Link>
            </li>
          </ul>
        </nav>

        <nav aria-label="Trust and legal" className="text-sm">
          <p className="font-semibold text-slate-800">Trust</p>
          <ul className="mt-2 space-y-1.5 text-muted">
            <li>
              <Link href="/security" className="hover:text-brand-700">
                Security
              </Link>
            </li>
            <li>
              <Link href="/privacy" className="hover:text-brand-700">
                Privacy &amp; data protection
              </Link>
            </li>
            <li>
              <Link href="/how-it-works" className="hover:text-brand-700">
                How verification works
              </Link>
            </li>
          </ul>
        </nav>
      </div>

      <div className="border-t border-muted-border py-4">
        <p className="container-page text-xs text-muted">
          &copy; {new Date().getFullYear()} VerifyKE. Built for Kenyan institutions and the
          employers, agencies and individuals who rely on their documents.
        </p>
      </div>
    </footer>
  );
}
