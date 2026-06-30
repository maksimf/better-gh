import { useEffect, useRef, useState } from "react";

import { useCloudAgentModels } from "../api/queries";
import { readString, removeKey, writeString } from "../hooks/storage";

const QA_MODEL_KEY = "better-gh.qa-agent-model";

export function defaultQaPrompt(number: number): string {
  return `Launch a browser automation to QA PR #${number}. Your goal is to verify the feature/bug end to end manually in the browser and produce a video of the step by step verification. Save the screen recording to artifacts/walkthrough.mp4 so it can be retrieved afterwards.`;
}

export interface QaAgentLaunch {
  prompt: string;
  modelId: string | null;
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
  onLaunch: (launch: QaAgentLaunch) => void;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [prompt, setPrompt] = useState(() => defaultQaPrompt(number));
  const [modelId, setModelId] = useState(() => readString(QA_MODEL_KEY) ?? "");
  const { data: models, isLoading: modelsLoading } = useCloudAgentModels(open);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  // Reset to the default prompt each time the modal is (re)opened.
  useEffect(() => {
    if (open) {
      setPrompt(defaultQaPrompt(number));
      setModelId(readString(QA_MODEL_KEY) ?? "");
    }
  }, [open, number]);

  // Drop a stale saved model if it no longer appears in the list.
  useEffect(() => {
    if (!modelId || !models) return;
    if (!models.some((m) => m.id === modelId)) {
      setModelId("");
      removeKey(QA_MODEL_KEY);
    }
  }, [modelId, models]);

  function handleModelChange(next: string) {
    setModelId(next);
    if (next) writeString(QA_MODEL_KEY, next);
  }

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
        <label className="qa-modal-label" htmlFor="qa-modal-model">
          MODEL
        </label>
        <select
          id="qa-modal-model"
          className="qa-modal-select"
          value={modelId}
          disabled={pending || modelsLoading}
          onChange={(e) => handleModelChange(e.target.value)}
        >
          <option value="">
            {modelsLoading ? "Loading models\u2026" : "Default (configured)"}
          </option>
          {models?.map((m) => (
            <option key={m.id} value={m.id}>
              {m.displayName}
            </option>
          ))}
        </select>
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
          onClick={() =>
            onLaunch({ prompt: prompt.trim(), modelId: modelId || null })
          }
        >
          {pending ? "Launching\u2026" : "Launch agent \u2192"}
        </button>
      </footer>
    </dialog>
  );
}
