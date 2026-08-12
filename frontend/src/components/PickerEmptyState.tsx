import type { RepoSummary } from "../api/types";
import { EmptyState } from "../ui/EmptyState";
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
    <EmptyState
      variant="picker"
      title="PICK YOUR REPOS"
      subtitle="Select the repositories you want this board to track. Your choice stays in this browser."
    >
      <div className="empty-state-picker-card">
        <RepoPicker repos={repos} has={has} onToggle={onToggle} />
      </div>
    </EmptyState>
  );
}
