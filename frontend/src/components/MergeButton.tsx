import { useState } from "react";

import { useMergePr } from "../api/queries";
import { ActionButton } from "../ui/ActionButton";
import { useTransientError } from "../ui/useTransientError";
import { CheckIcon } from "./icons";
import { MergeModal } from "./MergeModal";

/** Lift the `ENG-1234` identifier out of a `.../issue/ENG-1234` URL. */
function ticketFromUrl(linearUrl: string | null): string | null {
  if (!linearUrl) return null;
  const marker = "/issue/";
  const idx = linearUrl.indexOf(marker);
  if (idx < 0) return null;
  const rest = linearUrl.slice(idx + marker.length);
  const ticket = rest.split(/[/?#]/)[0];
  return ticket || null;
}

export function MergeButton({
  owner,
  repo,
  number,
  title,
  linearUrl = null,
}: {
  owner: string;
  repo: string;
  number: number;
  title: string;
  linearUrl?: string | null;
}) {
  const merge = useMergePr();
  const [merged, setMerged] = useState(false);
  const [open, setOpen] = useState(false);
  const { error, showError, clearError } = useTransientError();

  const linearTicket = ticketFromUrl(linearUrl);

  if (merged) {
    return (
      <ActionButton kind="merge" done>
        MERGED{" "}
        <span aria-hidden="true">
          <CheckIcon />
        </span>
      </ActionButton>
    );
  }

  function doMerge(markLinearDone: boolean) {
    clearError();
    merge.mutate(
      {
        ref: { owner, repo, number },
        markLinearDone,
        linearTicket,
      },
      {
        onSuccess: (result) => {
          setOpen(false);
          setMerged(true);
          // The merge landed; a Linear hiccup is non-fatal but worth flagging.
          if (markLinearDone && result && result.linear_error) {
            showError(`Merged, but Linear: ${result.linear_error}`);
          }
        },
        onError: (e) => {
          setOpen(false);
          showError(e instanceof Error ? e.message : String(e));
        },
      },
    );
  }

  return (
    <>
      <ActionButton
        kind="merge"
        error={Boolean(error)}
        title={error ?? "Merge this PR into the base branch"}
        disabled={merge.isPending}
        onClick={() => setOpen(true)}
      >
        MERGE &rarr;
      </ActionButton>
      <MergeModal
        open={open}
        title={title}
        number={number}
        linearTicket={linearTicket}
        pending={merge.isPending}
        onJustMerge={() => doMerge(false)}
        onMergeAndLinear={() => doMerge(true)}
        onClose={() => {
          if (!merge.isPending) setOpen(false);
        }}
      />
    </>
  );
}
