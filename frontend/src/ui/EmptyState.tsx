import type { ReactNode } from "react";

export function EmptyStateMark() {
  return (
    <div className="empty-state-mark" aria-hidden="true">
      <span className="shape shape--circle" />
      <span className="shape shape--square" />
      <span className="shape shape--triangle" />
    </div>
  );
}

export function EmptyState({
  variant,
  title,
  subtitle,
  children,
}: {
  variant?: "picker" | "reviews";
  title: string;
  subtitle: string;
  children?: ReactNode;
}) {
  const cls = ["empty-state", variant ? `empty-state--${variant}` : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={cls} aria-live="polite">
      <EmptyStateMark />
      <h2 className="empty-state-title">{title}</h2>
      <p className="empty-state-sub">{subtitle}</p>
      {children}
    </section>
  );
}
