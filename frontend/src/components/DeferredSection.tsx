import type { ReactNode } from "react";

export function DeferredSection({
  count,
  children,
}: {
  count: number;
  children: ReactNode;
}) {
  return (
    <details className="deferred-section">
      <summary className="deferred-section-summary">
        Deferred <span className="deferred-section-count">({count})</span>
      </summary>
      <div className="deferred-section-list">{children}</div>
    </details>
  );
}
