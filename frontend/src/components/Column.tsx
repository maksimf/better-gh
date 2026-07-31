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
  actions,
  children,
}: {
  column: ColumnKey;
  count: number;
  hidden: boolean;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      className={`column column--${column}`}
      aria-labelledby={`col-${column}-title`}
      hidden={hidden}
    >
      <header className="column-header">
        <div className="column-heading">
          <h2 id={`col-${column}-title`} className="column-title">
            {TITLES[column]}
          </h2>
          <span className="column-count">{count}</span>
        </div>
        {actions}
      </header>
      <div className="column-body">{children}</div>
    </section>
  );
}
