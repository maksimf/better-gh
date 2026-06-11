import { useEffect, useRef, useState, type ReactNode } from "react";

import { EllipsisIcon } from "./icons";

/**
 * A small "⋯" disclosure for a PR card's rare/occasional actions (today:
 * the QA-agent tooling). Closes on
 * outside click or Escape; the trigger advertises its state via
 * aria-expanded for keyboard / screen-reader users.
 */
export function OverflowMenu({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
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

  return (
    <div className={`pr-overflow${open ? " is-open" : ""}`} ref={ref}>
      <button
        type="button"
        className="pr-overflow-trigger"
        title="More actions"
        aria-label="More actions"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="card-toggle-icon" aria-hidden="true">
          <EllipsisIcon />
        </span>
      </button>
      {open && (
        <div className="pr-overflow-menu" role="menu">
          {children}
        </div>
      )}
    </div>
  );
}
