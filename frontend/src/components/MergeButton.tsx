import { useState } from "react";

import { useMergePr } from "../api/queries";
import { CheckIcon } from "./icons";

export function MergeButton({
  owner,
  repo,
  number,
  title,
}: {
  owner: string;
  repo: string;
  number: number;
  title: string;
}) {
  const merge = useMergePr();
  const [merged, setMerged] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (merged) {
    return (
      <span className="merge-button is-merged" aria-disabled="true">
        MERGED{" "}
        <span aria-hidden="true">
          <CheckIcon />
        </span>
      </span>
    );
  }

  function onClick() {
    if (
      !window.confirm(
        `Merge "${title}" (#${number}) into the base branch?`,
      )
    ) {
      return;
    }
    setError(null);
    merge.mutate(
      { owner, repo, number },
      {
        onSuccess: () => setMerged(true),
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
      className={`merge-button${error ? " is-error" : ""}`}
      title={error ?? "Merge this PR into the base branch"}
      disabled={merge.isPending}
      onClick={onClick}
    >
      MERGE &rarr;
    </button>
  );
}
