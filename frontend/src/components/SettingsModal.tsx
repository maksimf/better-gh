import { useEffect, useRef, useState } from "react";

import type { RepoSummary } from "../api/types";
import { BrandMark } from "./icons";
import { RepoPicker } from "./RepoPicker";

export function SettingsModal({
  open,
  onClose,
  repos,
  has,
  onToggleRepo,
  reviewerInitial,
  onReviewerChange,
}: {
  open: boolean;
  onClose: () => void;
  repos: RepoSummary[];
  has: (repo: string) => boolean;
  onToggleRepo: (repo: string, checked: boolean) => void;
  reviewerInitial: string;
  onReviewerChange: (value: string) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [reviewer, setReviewer] = useState(reviewerInitial);
  const [status, setStatus] = useState<{ text: string; cls: string }>({
    text: "",
    cls: "",
  });
  const timerRef = useRef<number | null>(null);

  // Drive the native <dialog> from the `open` prop.
  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  // Keep the input synced when the effective reviewer changes while the
  // modal is closed (e.g. first dashboard load resolves the default).
  useEffect(() => {
    if (!open) setReviewer(reviewerInitial);
  }, [reviewerInitial, open]);

  function commit(value: string) {
    onReviewerChange(value.trim());
    setStatus({ text: "Saved", cls: "is-saved" });
    window.setTimeout(() => setStatus({ text: "", cls: "" }), 1500);
  }

  function onInput(value: string) {
    setReviewer(value);
    setStatus({ text: "Saving\u2026", cls: "is-saving" });
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => commit(value), 600);
  }

  return (
    <dialog
      ref={dialogRef}
      className="settings-modal"
      aria-labelledby="settings-modal-title"
      onClose={onClose}
      onClick={(e) => {
        // Backdrop click (lands on the <dialog> itself) closes.
        if (e.target === dialogRef.current) onClose();
      }}
    >
      <header className="settings-modal-header">
        <BrandMark />
        <div className="settings-modal-titles">
          <h2 id="settings-modal-title" className="settings-modal-title">
            SETTINGS
          </h2>
        </div>
        <button
          type="button"
          className="settings-modal-close"
          aria-label="Close settings"
          onClick={onClose}
        >
          &times;
        </button>
      </header>
      <div className="settings-modal-body">
        <section
          className="settings-section"
          aria-labelledby="settings-reviewer-label"
        >
          <h3 id="settings-reviewer-label" className="settings-section-title">
            REVIEWER TO TRACK
          </h3>
          <p className="settings-section-hint">
            GitHub login of the reviewer whose approval moves a PR into the{" "}
            <strong>APPROVED</strong> column and unlocks the per-card{" "}
            <em>Request review</em> button. Leave empty to hide the chip
            entirely.
          </p>
          <label className="settings-reviewer-input">
            <span className="settings-reviewer-at" aria-hidden="true">
              @
            </span>
            <input
              type="text"
              name="reviewer"
              autoComplete="off"
              spellCheck={false}
              autoCapitalize="off"
              maxLength={39}
              placeholder="github-login"
              value={reviewer}
              onChange={(e) => onInput(e.target.value)}
            />
            <span
              className={`settings-reviewer-status ${status.cls}`}
              aria-live="polite"
            >
              {status.text}
            </span>
          </label>
        </section>
        <section
          className="settings-section"
          aria-labelledby="settings-repos-label"
        >
          <h3 id="settings-repos-label" className="settings-section-title">
            SHOW REPOS
          </h3>
          <p className="settings-section-hint">
            Check the repositories you want this board to track. Unchecked
            repos are hidden from both <strong>MY PRs</strong> and{" "}
            <strong>REVIEWING</strong>.
          </p>
          <RepoPicker repos={repos} has={has} onToggle={onToggleRepo} />
        </section>
      </div>
      <footer className="settings-modal-footer">
        Stored in your browser. No server-side state.
      </footer>
    </dialog>
  );
}
