import { useEffect, useRef, useState } from "react";

import type { RepoSummary } from "../api/types";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { BrandMark } from "./icons";
import { RepoPicker } from "./RepoPicker";
import { ReviewerPicker } from "./ReviewerPicker";

export function SettingsModal({
  open,
  onClose,
  repos,
  has,
  onToggleRepo,
  reviewers,
  onReviewersChange,
  ntfyChannel,
  onNtfyChannelChange,
}: {
  open: boolean;
  onClose: () => void;
  repos: RepoSummary[];
  has: (repo: string) => boolean;
  onToggleRepo: (repo: string, checked: boolean) => void;
  reviewers: string[];
  onReviewersChange: (next: string[]) => void;
  ntfyChannel: string;
  onNtfyChannelChange: (value: string) => void;
}) {
  const [ntfy, setNtfy] = useState(ntfyChannel);
  const [ntfyStatus, setNtfyStatus] = useState<{ text: string; cls: string }>({
    text: "",
    cls: "",
  });
  const ntfyTimerRef = useRef<number | null>(null);

  // Keep the ntfy input synced with the persisted value while closed.
  useEffect(() => {
    if (!open) setNtfy(ntfyChannel);
  }, [ntfyChannel, open]);

  function commitNtfy(value: string) {
    onNtfyChannelChange(value.trim());
    setNtfyStatus({ text: "Saved", cls: "is-saved" });
    window.setTimeout(() => setNtfyStatus({ text: "", cls: "" }), 1500);
  }

  function onNtfyInput(value: string) {
    setNtfy(value);
    setNtfyStatus({ text: "Saving\u2026", cls: "is-saving" });
    if (ntfyTimerRef.current) window.clearTimeout(ntfyTimerRef.current);
    ntfyTimerRef.current = window.setTimeout(() => commitNtfy(value), 600);
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      className="settings-modal"
      ariaLabelledBy="settings-modal-title"
    >
      <header className="settings-modal-header">
        <BrandMark />
        <div className="settings-modal-titles">
          <h2 id="settings-modal-title" className="settings-modal-title">
            SETTINGS
          </h2>
        </div>
        <Button
          surface="close"
          modal="settings"
          ariaLabel="Close settings"
          onClick={onClose}
        >
          &times;
        </Button>
      </header>
      <div className="settings-modal-body">
        <section
          className="settings-section"
          aria-labelledby="settings-reviewer-label"
        >
          <h3 id="settings-reviewer-label" className="settings-section-title">
            REVIEWERS TO TRACK
          </h3>
          <p className="settings-section-hint">
            GitHub users whose approval moves a PR into the{" "}
            <strong>APPROVED</strong> column and unlocks the per-card{" "}
            <em>Request review</em> or <em>Notify reviewer</em> button. Track
            several &mdash; an approval from <em>any</em> of them counts.
            Search to add, or remove a chip to stop tracking. Leave empty to
            hide the chips entirely.
          </p>
          <ReviewerPicker reviewers={reviewers} onChange={onReviewersChange} />
        </section>
        <section
          className="settings-section"
          aria-labelledby="settings-ntfy-label"
        >
          <h3 id="settings-ntfy-label" className="settings-section-title">
            NTFY CHANNEL
          </h3>
          <p className="settings-section-hint">
            The{" "}
            <a href="https://ntfy.sh" target="_blank" rel="noopener">
              ntfy.sh
            </a>{" "}
            topic that watched-PR alerts are published to. Subscribe to the
            same topic in the ntfy app to get pushed when checks pass and the
            preview is ready. Until this is set the per-card <em>Watch</em>{" "}
            button stays disabled.
          </p>
          <label className="settings-reviewer-input">
            <span className="settings-reviewer-at" aria-hidden="true">
              #
            </span>
            <input
              type="text"
              name="ntfy-channel"
              autoComplete="off"
              spellCheck={false}
              autoCapitalize="off"
              placeholder="my-better-gh-alerts"
              value={ntfy}
              onChange={(e) => onNtfyInput(e.target.value)}
            />
            <span
              className={`settings-reviewer-status ${ntfyStatus.cls}`}
              aria-live="polite"
            >
              {ntfyStatus.text}
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
    </Dialog>
  );
}
