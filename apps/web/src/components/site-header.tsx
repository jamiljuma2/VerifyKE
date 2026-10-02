import Link from "next/link";

/**
 * Public site header.
 *
 * Navigation is intentionally minimal while the console is built out: the public
 * verification entry point is the one thing that must never be more than one tap
 * away on a phone.
 */
export function SiteHeader() {
  return (
    <header className="no-print border-b border-muted-border bg-white">
      <div className="container-page flex h-16 items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2 font-semibold text-brand-700">
          <span
            aria-hidden="true"
            className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-sm font-bold text-white"
          >
            VK
          </span>
          <span className="text-base">VerifyKE</span>
        </Link>

        <nav aria-label="Primary" className="flex items-center gap-1 text-sm font-medium">
          <Link href="/verify" className="rounded-md px-3 py-2 text-slate-700 hover:bg-muted-soft">
            Verify a document
          </Link>
          <Link
            href="/for-institutions"
            className="hidden rounded-md px-3 py-2 text-slate-700 hover:bg-muted-soft sm:block"
          >
            For institutions
          </Link>
          {/* Sign-in appears with the institution console; until the auth service is
              live, a link here would only lead to a dead end. */}
        </nav>
      </div>
    </header>
  );
}
