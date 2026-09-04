import type { Column, StackNode } from "../api/types";

const COLUMN_LABELS: Record<Column, string> = {
  progress: "IN PROGRESS",
  ready: "READY FOR REVIEW",
  approved: "APPROVED",
};

const COLUMN_BADGES: Record<Column, string> = {
  progress: "PROGRESS",
  ready: "READY",
  approved: "APPROVED",
};

function prefixFor(depth: number): string {
  if (depth === 0) return "\u2022";
  return "\u00a0\u00a0".repeat(depth - 1) + "\u2514\u2500";
}

export function ColumnBadge({ column }: { column: Column }) {
  return (
    <span
      className={`pr-stack-col pr-stack-col--${column}`}
      title={`In ${COLUMN_LABELS[column]}`}
    >
      {COLUMN_BADGES[column]}
    </span>
  );
}

/**
 * Inline tree shown on each card of a stack that's split across columns
 * (when a stack is co-column the cards are grouped adjacently instead,
 * so the tree would just be noise).
 */
export function PrStack({ nodes }: { nodes: StackNode[] }) {
  return (
    <aside
      className="pr-stack"
      aria-label={`Stack of ${nodes.length} pull requests`}
    >
      <span className="pr-stack-label">STACK</span>
      <ol className="pr-stack-tree">
        {nodes.map((node) => (
          <li
            key={node.number}
            className={`pr-stack-node${node.is_self ? " is-self" : ""}`}
            data-depth={node.depth}
          >
            <span className="pr-stack-prefix" aria-hidden="true">
              {prefixFor(node.depth)}
            </span>
            <a
              className="pr-stack-link"
              href={node.url}
              target="_blank"
              rel="noopener"
            >
              #{node.number}
            </a>
            <span className="pr-stack-title">{node.title}</span>
            {!node.is_self && <ColumnBadge column={node.column} />}
          </li>
        ))}
      </ol>
    </aside>
  );
}
