import type { ReactNode } from "react";

import { cn } from "./cn";

interface CardProps {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article";
}

/** Neutral surface used for every content block in the product. */
export function Card({ children, className, as: Tag = "section" }: CardProps) {
  return (
    <Tag className={cn("rounded-xl border border-muted-border bg-white shadow-sm", className)}>
      {children}
    </Tag>
  );
}

export function CardHeader({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <header className={cn("border-b border-muted-border px-5 py-4", className)}>{children}</header>
  );
}

export function CardBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("px-5 py-4", className)}>{children}</div>;
}

export function CardFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <footer className={cn("border-t border-muted-border px-5 py-4", className)}>{children}</footer>
  );
}
