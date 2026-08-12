import { useRef, useState } from "react";

import { useAckComment, usePrComments, useReplyComment } from "../api/queries";
import type { PrRef } from "../api/queries";
import type { PrComment } from "../api/types";
import { Button } from "../ui/Button";

function truncate(text: string, max = 280): string {
  if (text.length <= max) return text;
  return text.slice(0, max).trimEnd() + "…";
}

function CommentRow({
  comment,
  prRef,
}: {
  comment: PrComment;
  prRef: PrRef;
}) {
  const [acked, setAcked] = useState(false);
  const [replied, setReplied] = useState(false);
  const [replyOpen, setReplyOpen] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [replyErr, setReplyErr] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const ack = useAckComment();
  const reply = useReplyComment();

  function handleAck() {
    ack.mutate(
      { ref: prRef, commentId: comment.id, commentType: comment.type },
      { onSuccess: () => setAcked(true) },
    );
  }

  function openReply() {
    setReplyOpen(true);
    setReplyText("");
    setReplyErr(null);
    setTimeout(() => textareaRef.current?.focus(), 0);
  }

  function handleReply() {
    const trimmed = replyText.trim();
    if (!trimmed) return;
    reply.mutate(
      {
        ref: prRef,
        quotedAuthor: comment.author,
        quotedBody: comment.body,
        reply: trimmed,
      },
      {
        onSuccess: () => {
          setReplied(true);
          setReplyOpen(false);
          setReplyText("");
          setReplyErr(null);
        },
        onError: (e) =>
          setReplyErr(e instanceof Error ? e.message : String(e)),
      },
    );
  }

  const acking = ack.isPending;
  const replying = reply.isPending;

  return (
    <li className={`hcp-comment${acked ? " hcp-comment--acked" : ""}`}>
      <div className="hcp-comment-meta">
        <a
          className="hcp-comment-author"
          href={comment.url}
          target="_blank"
          rel="noopener"
        >
          @{comment.author}
        </a>
        {comment.type === "review" && (
          <span className="hcp-comment-kind">review thread</span>
        )}
      </div>
      <p className="hcp-comment-body">{truncate(comment.body)}</p>
      <div className="hcp-comment-actions">
        {acked ? (
          <span className="hcp-badge">👀 acked</span>
        ) : (
          <Button surface="hcp" variant="ack" onClick={handleAck} disabled={acking}>
            {acking ? "…" : "Ack 👀"}
          </Button>
        )}
        {replied ? (
          <span className="hcp-badge">↩ replied</span>
        ) : replyOpen ? null : (
          <Button surface="hcp" variant="reply" onClick={openReply}>
            Reply
          </Button>
        )}
      </div>

      {replyOpen && (
        <div className="hcp-reply">
          <textarea
            ref={textareaRef}
            className="hcp-reply-input"
            placeholder="Type your reply…"
            value={replyText}
            rows={3}
            onChange={(e) => setReplyText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleReply();
              if (e.key === "Escape") {
                setReplyOpen(false);
                setReplyText("");
              }
            }}
          />
          {replyErr && <p className="hcp-reply-err">{replyErr}</p>}
          <div className="hcp-reply-buttons">
            <Button
              surface="hcp"
              variant="submit"
              onClick={handleReply}
              disabled={replying || !replyText.trim()}
            >
              {replying ? "Posting…" : "Post reply"}
            </Button>
            <Button
              surface="hcp"
              variant="cancel"
              onClick={() => {
                setReplyOpen(false);
                setReplyText("");
                setReplyErr(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

export function HumanCommentsPopover({
  owner,
  repo,
  number,
}: {
  owner: string;
  repo: string;
  number: number;
}) {
  const prRef: PrRef = { owner, repo, number };
  const { data, isLoading, error } = usePrComments(owner, repo, number, true);

  return (
    <div className="hcp" role="dialog" aria-label="Human comments">
      <div className="hcp-header">
        Comments
        {data && data.length > 0 && (
          <span className="hcp-count">{data.length}</span>
        )}
      </div>

      {isLoading && <p className="hcp-state">Loading…</p>}

      {error && (
        <p className="hcp-state hcp-state--err">
          {error instanceof Error ? error.message : "Failed to load comments"}
        </p>
      )}

      {data && data.length === 0 && (
        <p className="hcp-state">No unresolved comments.</p>
      )}

      {data && data.length > 0 && (
        <ul className="hcp-list">
          {data.map((c) => (
            <CommentRow key={`${c.type}-${c.id}`} comment={c} prRef={prRef} />
          ))}
        </ul>
      )}
    </div>
  );
}
