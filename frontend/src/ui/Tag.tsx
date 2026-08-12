import type { ReactNode } from "react";

export function Tag({
  variant,
  children,
  className,
}: {
  variant: "draft";
  children: ReactNode;
  className?: string;
}) {
  const cls = [`pr-tag pr-tag--${variant}`, className]
    .filter(Boolean)
    .join(" ");
  return <span className={cls}>{children}</span>;
}
