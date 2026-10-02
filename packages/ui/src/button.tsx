import type { Route } from "next";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import Link from "next/link";

import { cn } from "./cn";

type Variant = "primary" | "secondary" | "ghost";

export const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:cursor-not-allowed disabled:opacity-60";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700",
  secondary: "border border-muted-border bg-white text-brand-700 hover:bg-muted-soft",
  ghost: "text-brand-700 hover:bg-brand-50",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ variant = "primary", className, ...props }: ButtonProps) {
  return <button className={cn(BUTTON_BASE, VARIANTS[variant], className)} {...props} />;
}

export function ButtonLink({
  href,
  children,
  variant = "primary",
  className,
  prefetch,
}: {
  href: Route;
  children: ReactNode;
  variant?: Variant;
  className?: string;
  prefetch?: boolean;
}) {
  return (
    <Link href={href} prefetch={prefetch} className={cn(BUTTON_BASE, VARIANTS[variant], className)}>
      {children}
    </Link>
  );
}
