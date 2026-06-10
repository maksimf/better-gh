import { useEffect, useRef, useState } from "react";

import type { PrRef } from "../api/queries";
import { HumanCommentsPopover } from "./HumanCommentsPopover";

function BotCell({ count }: { count: number }) {
  const cls = count === 0 ? "comments-cell--zero" : "comments-cell--bot";
  return (
    <span
      className={`comments-cell ${cls}`}
      title="Unresolved bot comments (cursor + coderabbit)"
    >
      B {count}
    </span>
  );
}

export function CommentsPill({
  human,
  bot,
  prRef,
}: {
  human: number;
  bot: number;
  prRef?: PrRef;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const humanCls = human === 0 ? "comments-cell--zero" : "comments-cell--human";
  const clickable = prRef !== undefined && human > 0;

  return (
    <span
      className={`comments${open ? " is-open" : ""}`}
      title="Unresolved comments: human / bot"
      ref={wrapRef}
    >
      <span className="comments-label">Comments</span>

      {clickable ? (
        <button
          type="button"
          className={`comments-cell comments-cell--btn ${humanCls}`}
          title="Click to view human comments"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          H {human}
        </button>
      ) : (
        <span
          className={`comments-cell ${humanCls}`}
          title="Unresolved human review-thread comments + un-acked generic comments (react with any emoji to ack)"
        >
          H {human}
        </span>
      )}

      <BotCell count={bot} />

      {open && prRef && (
        <HumanCommentsPopover
          owner={prRef.owner}
          repo={prRef.repo}
          number={prRef.number}
        />
      )}
    </span>
  );
}
