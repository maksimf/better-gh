import { useRef, useState } from "react";

import type { PrRef } from "../api/queries";
import { MetricCell, MetricPill } from "../ui/MetricPill";
import { useDismissOnOutside } from "../ui/useDismissOnOutside";
import { HumanCommentsPopover } from "./HumanCommentsPopover";

export function CommentsPill({
  human,
  bot,
  prRef,
}: {
  human: number;
  bot: number;
  prRef?: PrRef;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement>(null);
  useDismissOnOutside(open, () => setOpen(false), wrapRef);

  const clickable = prRef !== undefined && human > 0;

  return (
    <span ref={wrapRef}>
      <MetricPill
        label="Comments"
        title="Unresolved comments: human / bot"
        open={open}
        className="comments"
      >
        {clickable ? (
          <MetricCell
            family="comments"
            tone={human === 0 ? "zero" : "human"}
            as="button"
            title="Click to view human comments"
            ariaExpanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            H {human}
          </MetricCell>
        ) : (
          <MetricCell
            family="comments"
            tone={human === 0 ? "zero" : "human"}
            title="Unresolved human review-thread comments + un-acked generic comments (react with any emoji to ack)"
          >
            H {human}
          </MetricCell>
        )}

        <MetricCell
          family="comments"
          tone={bot === 0 ? "zero" : "bot"}
          title="Unresolved bot comments (cursor + coderabbit)"
        >
          B {bot}
        </MetricCell>

        {open && prRef && (
          <HumanCommentsPopover
            owner={prRef.owner}
            repo={prRef.repo}
            number={prRef.number}
          />
        )}
      </MetricPill>
    </span>
  );
}
