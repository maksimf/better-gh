import type { RepoSummary } from "../api/types";
import { RepoPicker } from "./RepoPicker";

/**
 * Replaces the whole board when the viewer hasn't selected any repos
 * yet. Hosts the same checklist as the settings modal so a fresh user
 * can configure visibility without opening a dialog.
 */
export function PickerEmptyState({
  repos,
  has,
  onToggle,
}: {
  repos: RepoSummary[];
  has: (repo: string) => boolean;
  onToggle: (repo: string, checked: boolean) => void;
}) {
  return (
    <section className="empty-state empty-state--picker" aria-live="polite">
      <div className="empty-state-mark" aria-hidden="true">
        <span className="shape shape--circle"></span>
        <span className="shape shape--square"></span>
        <span className="shape shape--triangle"></span>
      </div>
      <h2 className="empty-state-title">PICK YOUR REPOS</h2>
      <p className="empty-state-sub">
        Select the repositories you want this board to track. Your choice
        stays in this browser.
      </p>
      <div className="empty-state-picker-card">
        <RepoPicker repos={repos} has={has} onToggle={onToggle} />
      </div>
    </section>
  );
}
