import { useState } from "react";

import { useMergePr } from "../api/queries";
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
  const [error, setError] = useState<string | null>(null);

  const linearTicket = ticketFromUrl(linearUrl);

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

  function showError(message: string) {
    setError(message);
    window.setTimeout(() => setError(null), 4000);
  }

  function doMerge(markLinearDone: boolean) {
    setError(null);
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
      <button
        type="button"
        className={`merge-button${error ? " is-error" : ""}`}
        title={error ?? "Merge this PR into the base branch"}
        disabled={merge.isPending}
        onClick={() => setOpen(true)}
      >
        MERGE &rarr;
      </button>
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
