/**
 * Client-side shape validation for a VerifyKE certificate number.
 *
 * This mirrors the API's identifier format (``VK-<country>-<year>-<12 Crockford
 * chars>-<checksum>``) so that obvious typos are caught before a request is
 * made. It is a usability helper only - the server re-validates everything, and
 * only the server can decide whether a certificate exists.
 */
const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const SHAPE = /^VK-[A-Z]{2}-\d{4}-[0-9A-HJKMNP-TV-Z]{12}-[0-9A-HJKMNP-TV-Z]$/;

/** Map ambiguous glyphs (as read off paper) onto Crockford characters. */
export function normaliseCertificateId(value: string): string {
  return value.trim().toUpperCase().replace(/\s+/g, "");
}

function checksumOf(body: string): string {
  let total = 0;
  for (let index = 0; index < body.length; index += 1) {
    total += CROCKFORD.indexOf(body[index] ?? "") * (index + 1);
  }
  return CROCKFORD[total % CROCKFORD.length] ?? "";
}

export function isCertificateIdShapeValid(value: string): boolean {
  const normalised = normaliseCertificateId(value).replace(/O/g, "0").replace(/[IL]/g, "1");
  if (!SHAPE.test(normalised)) {
    return false;
  }
  const [body, checksum] = normalised.split("-").slice(3) as [string, string];
  return checksumOf(body) === checksum;
}
