import { useEffect, useRef, useState } from "react";

export function defaultQaPrompt(number: number): string {
  return `Launch a browser automation to QA PR #${number}. Your goal is to verify the feature/bug end to end manually in the browser and produce a video of the step by step verification. Save the screen recording to artifacts/walkthrough.mp4 so it can be retrieved afterwards.`;
}

/**
 * Modal for launching a QA cloud agent against a PR. Pre-fills an editable
 * prompt (referencing the PR number) and, on confirm, hands the final text
 * back to the caller which POSTs it to /api/cloud-agent.
 */
export function CloudAgentModal({
  open,
  number,
  pending,
  error,
  onLaunch,
  onClose,
}: {
  open: boolean;
  number: number;
  pending: boolean;
  error: string | null;
  onLaunch: (prompt: string) => void;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [prompt, setPrompt] = useState(() => defaultQaPrompt(number));

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  // Reset to the default prompt each time the modal is (re)opened.
  useEffect(() => {
    if (open) setPrompt(defaultQaPrompt(number));
  }, [open, number]);

  return (
    <dialog
      ref={dialogRef}
      className="qa-modal"
      aria-labelledby="qa-modal-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === dialogRef.current && !pending) onClose();
      }}
    >
      <header className="qa-modal-header">
        <h2 id="qa-modal-title" className="qa-modal-title">
          START QA AGENT
        </h2>
        <button
          type="button"
          className="qa-modal-close"
          aria-label="Cancel"
          disabled={pending}
          onClick={onClose}
        >
          &times;
        </button>
      </header>

      <div className="qa-modal-body">
        <p className="qa-modal-summary">
          Launch a Cursor cloud agent to QA{" "}
          <span className="qa-modal-pr">#{number}</span>. Edit the prompt
          below, then launch.
        </p>
        <label className="qa-modal-label" htmlFor="qa-modal-prompt">
          PROMPT
        </label>
        <textarea
          id="qa-modal-prompt"
          className="qa-modal-textarea"
          rows={5}
          value={prompt}
          disabled={pending}
          onChange={(e) => setPrompt(e.target.value)}
        />
        {error && (
          <p className="qa-modal-error" role="alert">
            {error}
          </p>
        )}
      </div>

      <footer className="qa-modal-footer">
        <button
          type="button"
          className="qa-modal-btn qa-modal-btn--ghost"
          disabled={pending}
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          type="button"
          className="qa-modal-btn qa-modal-btn--launch"
          disabled={pending || prompt.trim().length === 0}
          onClick={() => onLaunch(prompt.trim())}
        >
          {pending ? "Launching\u2026" : "Launch agent \u2192"}
        </button>
      </footer>
    </dialog>
  );
}
