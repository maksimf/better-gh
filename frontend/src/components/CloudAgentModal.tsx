import { useEffect, useState } from "react";

import { useCloudAgentModels } from "../api/queries";
import { readString, writeString } from "../hooks/storage";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";

const QA_MODEL_KEY = "better-gh.qa-agent-model";
const DEFAULT_QA_MODEL_ID = "composer-2.5";

function resolveDefaultModelId(
  models: { id: string; displayName: string }[] | undefined,
): string {
  if (!models?.length) return DEFAULT_QA_MODEL_ID;
  const exact = models.find((m) => m.id === DEFAULT_QA_MODEL_ID);
  if (exact) return exact.id;
  const byName = models.find((m) =>
    m.displayName.toLowerCase().includes("composer 2.5"),
  );
  return byName?.id ?? DEFAULT_QA_MODEL_ID;
}

function initialModelId(): string {
  return readString(QA_MODEL_KEY) ?? DEFAULT_QA_MODEL_ID;
}

export function defaultQaPrompt(number: number): string {
  return `Launch a browser automation to QA PR #${number}. Your goal is to verify the feature/bug end to end manually in the browser and produce a video of the step by step verification. Save the screen recording to artifacts/walkthrough.mp4 so it can be retrieved afterwards.`;
}

export interface QaAgentLaunch {
  prompt: string;
  modelId: string;
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
  const [prompt, setPrompt] = useState(() => defaultQaPrompt(number));
  const [modelId, setModelId] = useState(() => initialModelId());
  const { data: models, isLoading: modelsLoading } = useCloudAgentModels(open);

  // Reset to defaults each time the modal is (re)opened.
  useEffect(() => {
    if (open) {
      setPrompt(defaultQaPrompt(number));
      setModelId(initialModelId());
    }
  }, [open, number]);

  // Resolve composer-2.5 against the live model list once it arrives.
  useEffect(() => {
    if (!models?.length || readString(QA_MODEL_KEY)) return;
    setModelId((current) =>
      models.some((m) => m.id === current)
        ? current
        : resolveDefaultModelId(models),
    );
  }, [models]);

  // Drop a stale saved model if it no longer appears in the list.
  useEffect(() => {
    if (!modelId || !models) return;
    if (!models.some((m) => m.id === modelId)) {
      const fallback = resolveDefaultModelId(models);
      setModelId(fallback);
      writeString(QA_MODEL_KEY, fallback);
    }
  }, [modelId, models]);

  function handleModelChange(next: string) {
    setModelId(next);
    if (next) writeString(QA_MODEL_KEY, next);
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      className="qa-modal"
      ariaLabelledBy="qa-modal-title"
      blockBackdropClose={pending}
    >
      <header className="qa-modal-header">
        <h2 id="qa-modal-title" className="qa-modal-title">
          START QA AGENT
        </h2>
        <Button
          surface="close"
          modal="qa"
          ariaLabel="Cancel"
          disabled={pending}
          onClick={onClose}
        >
          &times;
        </Button>
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
          {modelsLoading && (
            <option value={modelId}>{"Loading models\u2026"}</option>
          )}
          {!modelsLoading &&
            models?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.displayName}
              </option>
            ))}
          {!modelsLoading && !models?.length && (
            <option value={DEFAULT_QA_MODEL_ID}>Composer 2.5</option>
          )}
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
        <Button
          surface="modal"
          modal="qa"
          variant="ghost"
          disabled={pending}
          onClick={onClose}
        >
          Cancel
        </Button>
        <Button
          surface="modal"
          modal="qa"
          variant="launch"
          disabled={pending || prompt.trim().length === 0}
          onClick={() => onLaunch({ prompt: prompt.trim(), modelId })}
        >
          {pending ? "Launching\u2026" : "Launch agent \u2192"}
        </Button>
      </footer>
    </Dialog>
  );
}
