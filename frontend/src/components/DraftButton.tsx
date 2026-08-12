import { useMarkReady } from "../api/queries";
import { ActionButton } from "../ui/ActionButton";
import { useTransientError } from "../ui/useTransientError";

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
  const { error, showError, clearError } = useTransientError();

  function onClick() {
    if (!window.confirm(`Mark #${number} as ready for review?`)) return;
    clearError();
    markReady.mutate(
      { owner, repo, number },
      {
        onError: (e) => {
          showError(e instanceof Error ? e.message : String(e));
        },
      },
    );
  }

  return (
    <ActionButton
      kind="ready"
      error={Boolean(error)}
      title={error ?? "Mark this PR as ready for review"}
      aria-label="Mark this PR as ready for review"
      disabled={markReady.isPending}
      onClick={onClick}
    >
      {markReady.isPending ? "Marking\u2026" : "Mark ready \u2192"}
    </ActionButton>
  );
}
