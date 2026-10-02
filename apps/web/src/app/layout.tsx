import type { Metadata, Viewport } from "next";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

import "./globals.css";

/**
 * Root layout.
 *
 * `robots` defaults to noindex: verification result pages contain personal data
 * and must never be indexed by search engines. Individual public marketing pages
 * opt in explicitly.
 */
export const metadata: Metadata = {
  title: {
    default: "VerifyKE - Trust Every Credential. Verify Every Certificate.",
    template: "%s | VerifyKE",
  },
  description:
    "Verify Kenyan and international academic certificates and important documents in seconds. Issuer-backed, cryptographically signed, evidence-based results.",
  applicationName: "VerifyKE",
  robots: { index: false, follow: false },
  formatDetection: { telephone: false, email: false, address: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#166149",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-KE">
      <body className="flex min-h-screen flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-4 focus:py-2"
        >
          Skip to main content
        </a>
        <SiteHeader />
        <main id="main" className="flex-1">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
