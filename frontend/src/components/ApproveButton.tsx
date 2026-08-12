import { useState } from "react";

import { useApprovePr } from "../api/queries";
import { ActionButton } from "../ui/ActionButton";
import { useTransientError } from "../ui/useTransientError";
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
  const { error, showError, clearError } = useTransientError();

  if (approved) {
    return (
      <ActionButton kind="approve" done>
        APPROVED{" "}
        <span aria-hidden="true">
          <CheckIcon />
        </span>
      </ActionButton>
    );
  }

  function doApprove() {
    clearError();
    approve.mutate(
      { ref: { owner, repo, number } },
      {
        onSuccess: () => setApproved(true),
        onError: (e) => showError(e instanceof Error ? e.message : String(e)),
      },
    );
  }

  return (
    <ActionButton
      kind="approve"
      error={Boolean(error)}
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
    </ActionButton>
  );
}
