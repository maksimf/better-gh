import type { RepoSummary } from "../api/types";

/**
 * The repo checklist shared between the settings modal and the
 * "PICK YOUR REPOS" empty-state. Toggling a checkbox writes straight
 * into the selected-repos store so the board re-filters without a
 * round-trip.
 */
export function RepoPicker({
  repos,
  has,
  onToggle,
}: {
  repos: RepoSummary[];
  has: (repo: string) => boolean;
  onToggle: (repo: string, checked: boolean) => void;
}) {
  if (repos.length === 0) {
    return (
      <ul className="settings-repo-list" aria-live="polite">
        <li className="settings-empty">No open PRs in any repo.</li>
      </ul>
    );
  }

  return (
    <ul className="settings-repo-list" aria-live="polite">
      {repos.map((r) => (
        <li className="settings-row" key={r.repo}>
          <label>
            <input
              type="checkbox"
              name="repo"
              value={r.repo}
              checked={has(r.repo)}
              onChange={(e) => onToggle(r.repo, e.target.checked)}
            />
            <span className="settings-repo">{r.repo}</span>
            <span className="settings-count">{r.count}</span>
          </label>
        </li>
      ))}
    </ul>
  );
}
