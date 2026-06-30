import { useState } from "react";

import { useApprovePr } from "../api/queries";
import { CheckIcon } from "./icons";

export function ApproveButton({
  owner,
  repo,
  number,
}: {
  owner: string;
  repo: string;
  number: number;
}) {
  const approve = useApprovePr();
  const [approved, setApproved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (approved) {
    return (
      <span className="approve-button is-approved" aria-disabled="true">
        APPROVED{" "}
        <span aria-hidden="true">
          <CheckIcon />
        </span>
      </span>
    );
  }

  function showError(message: string) {
    setError(message);
    window.setTimeout(() => setError(null), 4000);
  }

  function doApprove() {
    setError(null);
    approve.mutate(
      { ref: { owner, repo, number } },
      {
        onSuccess: () => setApproved(true),
        onError: (e) => showError(e instanceof Error ? e.message : String(e)),
      },
    );
  }

  return (
    <button
      type="button"
      className={`approve-button${error ? " is-error" : ""}`}
      title={error ?? "Approve this PR"}
      disabled={approve.isPending}
      onClick={doApprove}
    >
      {approve.isPending ? "APPROVING…" : "APPROVE"}
      {!approve.isPending && !error && (
        <span aria-hidden="true">
          <CheckIcon />
        </span>
      )}
    </button>
  );
}
