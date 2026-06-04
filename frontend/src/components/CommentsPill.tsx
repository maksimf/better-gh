function CommentsCell({
  letter,
  count,
  kind,
  title,
}: {
  letter: string;
  count: number;
  kind: "human" | "bot";
  title: string;
}) {
  const cls = count === 0 ? "comments-cell--zero" : `comments-cell--${kind}`;
  return (
    <span className={`comments-cell ${cls}`} title={title}>
      {letter} {count}
    </span>
  );
}

export function CommentsPill({
  human,
  bot,
}: {
  human: number;
  bot: number;
}) {
  return (
    <span className="comments" title="Unresolved comments: human / bot">
      <span className="comments-label">Comments</span>
      <CommentsCell
        letter="H"
        count={human}
        kind="human"
        title="Unresolved human review-thread comments + un-acked generic comments (react with any emoji to ack)"
      />
      <CommentsCell
        letter="B"
        count={bot}
        kind="bot"
        title="Unresolved bot comments (cursor + coderabbit)"
      />
    </span>
  );
}
