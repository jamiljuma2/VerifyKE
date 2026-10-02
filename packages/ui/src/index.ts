/**
 * @verifyke/ui - shared presentational primitives.
 *
 * These components are deliberately small and unstyled-by-default: the web app
 * owns layout, this package owns the repeated visual language (cards, badges,
 * status pills, buttons) so that verification status is rendered identically in
 * the public site, the institution console and the admin console.
 */
export { cn } from "./cn";
export { Card, CardHeader, CardBody, CardFooter } from "./card";
export { Badge, type BadgeTone } from "./badge";
export { Button, ButtonLink } from "./button";
export { StatusPill, STATUS_PRESENTATION } from "./status-pill";
