import type { ReactNode } from "react";

export function MetricCell({
  family,
  tone,
  value,
  as = "span",
  title,
  onClick,
  ariaExpanded,
  children,
}: {
  family: "checks" | "comments";
  tone: "pass" | "pending" | "fail" | "human" | "bot" | "zero";
  value?: number | string;
  as?: "span" | "button";
  title?: string;
  onClick?: () => void;
  ariaExpanded?: boolean;
  children?: ReactNode;
}) {
  const toneCls =
    tone === "zero" ? `${family}-cell--zero` : `${family}-cell--${tone}`;
  const cls = [
    `${family}-cell`,
    toneCls,
    as === "button" ? "comments-cell--btn" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const content = children ?? value;

  if (as === "button") {
    return (
      <button
        type="button"
        className={cls}
        title={title}
        aria-expanded={ariaExpanded}
        onClick={onClick}
      >
        {content}
      </button>
    );
  }

  return (
    <span className={cls} title={title}>
      {content}
    </span>
  );
}

export function MetricPill({
  label,
  title,
  open = false,
  className,
  children,
}: {
  label: string;
  title?: string;
  open?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const base = className ?? "checks";
  const cls = `${base}${open ? " is-open" : ""}`;
  const labelCls = base.startsWith("comments")
    ? "comments-label"
    : "checks-label";

  return (
    <span className={cls} title={title}>
      <span className={labelCls}>{label}</span>
      {children}
    </span>
  );
}
