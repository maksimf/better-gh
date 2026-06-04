import type { ReactNode } from "react";

import type { Column as ColumnKey } from "../api/types";

const TITLES: Record<ColumnKey, string> = {
  progress: "IN PROGRESS",
  ready: "READY FOR REVIEW",
  approved: "APPROVED",
};

export function Column({
  column,
  count,
  hidden,
  children,
}: {
  column: ColumnKey;
  count: number;
  hidden: boolean;
  children: ReactNode;
}) {
  return (
    <section
      className={`column column--${column}`}
      aria-labelledby={`col-${column}-title`}
      hidden={hidden}
    >
      <header className="column-header">
        <h2 id={`col-${column}-title`} className="column-title">
          {TITLES[column]}
        </h2>
        <span className="column-count">{count}</span>
      </header>
      <div className="column-body">{children}</div>
    </section>
  );
}
