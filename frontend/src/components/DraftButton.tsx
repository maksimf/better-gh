import { useState } from "react";

import { useMarkReady } from "../api/queries";

export function DraftButton({
  owner,
  repo,
  number,
}: {
  owner: string;
  repo: string;
  number: number;
}) {
  const markReady = useMarkReady();
  const [error, setError] = useState<string | null>(null);

  function onClick() {
    if (!window.confirm(`Mark #${number} as ready for review?`)) return;
    setError(null);
    markReady.mutate(
      { owner, repo, number },
      {
        onError: (e) => {
          setError(e instanceof Error ? e.message : String(e));
          window.setTimeout(() => setError(null), 4000);
        },
      },
    );
  }

  return (
    <button
      type="button"
      className={`ready-button${error ? " is-error" : ""}`}
      title={error ?? "Mark this PR as ready for review"}
      aria-label="Mark this PR as ready for review"
      disabled={markReady.isPending}
      onClick={onClick}
    >
      {markReady.isPending ? "Marking\u2026" : "Mark ready \u2192"}
    </button>
  );
}
