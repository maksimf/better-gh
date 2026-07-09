import { useMemo, useState } from "react";
import { marked } from "marked";

import {
  useAddLineComment,
  useAddPrComment,
  useMe,
  usePrDiff,
} from "../api/queries";
import type { DiffFile, DiffSide } from "../api/types";
import { ReviewActions } from "./ReviewActions";
import { PrLocStats } from "./PrLocStats";

type LineKind = "add" | "del" | "context" | "hunk" | "meta";

interface DiffLine {
  kind: LineKind;
  oldNo: number | null;
  newNo: number | null;
  text: string;
}

/** A commentable position on a diff line (GitHub side + line number). */
interface LineAnchor {
  side: DiffSide;
  line: number;
  /** Index into the parsed DiffLine[] for selection UI. */
  index: number;
}

interface LineRange {
  start: LineAnchor;
  end: LineAnchor;
}

const HUNK_RE = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/;

/** GitHub-hosted PR upload assets (images & videos) that need our token. */
const ATTACHMENT_RE = /^https:\/\/github\.com\/user-attachments\//i;

/** Route an authed GitHub asset through our same-origin token proxy. */
function proxyAttachment(src: string): string {
  return `/attachments?url=${encodeURIComponent(src)}`;
}

/**
 * Render a PR's markdown body the way GitHub does for uploaded media.
 *
 * `marked` alone turns a bare `user-attachments` URL into a plain link and
 * leaves `<img>` srcs pointing at an asset the browser can't load (GitHub's
 * session cookie is `SameSite=Lax`, so cross-origin subresource requests are
 * unauthenticated and 404). We post-process the HTML to:
 *   - proxy every `<img>/<video>/<source>` asset src through the backend, and
 *   - promote bare autolinked attachment URLs to inline `<video>` players
 *     (GitHub uploads videos as bare URLs; images use `![]()`/`<img>`).
 */
function renderPrBody(markdown: string): string {
  const html = marked(markdown) as string;
  if (typeof DOMParser === "undefined") return html;

  const doc = new DOMParser().parseFromString(html, "text/html");

  doc.querySelectorAll("img[src], video[src], source[src]").forEach((el) => {
    const src = el.getAttribute("src") ?? "";
    if (ATTACHMENT_RE.test(src)) el.setAttribute("src", proxyAttachment(src));
  });

  doc.querySelectorAll("a[href]").forEach((anchor) => {
    const href = anchor.getAttribute("href") ?? "";
    // Only bare autolinks (link text === url) are uploaded videos; a linked
    // image has an <img> child (empty text) and must stay an image.
    if (!ATTACHMENT_RE.test(href)) return;
    if ((anchor.textContent ?? "").trim() !== href) return;

    const video = doc.createElement("video");
    video.setAttribute("src", proxyAttachment(href));
    video.setAttribute("controls", "");
    video.setAttribute("preload", "metadata");
    video.className = "diff-media";
    anchor.replaceWith(video);
  });

  return doc.body.innerHTML;
}

/** Parse a GitHub unified-diff `patch` blob into renderable, numbered lines. */
function parsePatch(patch: string): DiffLine[] {
  const lines: DiffLine[] = [];
  let oldNo = 0;
  let newNo = 0;
  for (const raw of patch.split("\n")) {
    const hunk = HUNK_RE.exec(raw);
    if (hunk) {
      oldNo = Number(hunk[1]);
      newNo = Number(hunk[2]);
      lines.push({ kind: "hunk", oldNo: null, newNo: null, text: raw });
      continue;
    }
    const marker = raw[0];
    if (marker === "+") {
      lines.push({ kind: "add", oldNo: null, newNo: newNo++, text: raw.slice(1) });
    } else if (marker === "-") {
      lines.push({ kind: "del", oldNo: oldNo++, newNo: null, text: raw.slice(1) });
    } else if (marker === "\\") {
      // "\ No newline at end of file"
      lines.push({ kind: "meta", oldNo: null, newNo: null, text: raw });
    } else {
      lines.push({
        kind: "context",
        oldNo: oldNo++,
        newNo: newNo++,
        text: raw.startsWith(" ") ? raw.slice(1) : raw,
      });
    }
  }
  return lines;
}

/** Map a parsed diff line to a GitHub review-comment anchor, or null. */
function lineAnchor(line: DiffLine, index: number): LineAnchor | null {
  if (line.kind === "del" && line.oldNo != null) {
    return { side: "LEFT", line: line.oldNo, index };
  }
  if (
    (line.kind === "add" || line.kind === "context") &&
    line.newNo != null
  ) {
    return { side: "RIGHT", line: line.newNo, index };
  }
  return null;
}

/** Normalize a selection so start is the earlier index. */
function normalizeRange(a: LineAnchor, b: LineAnchor): LineRange {
  return a.index <= b.index ? { start: a, end: b } : { start: b, end: a };
}

function FileDiff({
  file,
  headSha,
  owner,
  repo,
  number,
}: {
  file: DiffFile;
  headSha: string | null;
  owner: string;
  repo: string;
  number: number;
}) {
  const lines = useMemo(
    () => (file.patch ? parsePatch(file.patch) : null),
    [file.patch],
  );
  const addLine = useAddLineComment();
  const [anchorStart, setAnchorStart] = useState<LineAnchor | null>(null);
  const [range, setRange] = useState<LineRange | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  function clearComposer() {
    setAnchorStart(null);
    setRange(null);
    setDraft("");
    setError(null);
  }

  function onLineClick(line: DiffLine, index: number, shiftKey: boolean) {
    const anchor = lineAnchor(line, index);
    if (!anchor || !headSha) return;

    if (shiftKey && anchorStart) {
      // Extend selection from the previous click into a range.
      setRange(normalizeRange(anchorStart, anchor));
      setError(null);
      return;
    }

    setAnchorStart(anchor);
    setRange({ start: anchor, end: anchor });
    setDraft("");
    setError(null);
  }

  function submitLineComment() {
    if (!range || !headSha || !draft.trim()) return;
    setError(null);
    const multi = range.start.index !== range.end.index;
    addLine.mutate(
      {
        ref: { owner, repo, number },
        commitId: headSha,
        path: file.filename,
        body: draft.trim(),
        line: range.end.line,
        side: range.end.side,
        startLine: multi ? range.start.line : undefined,
        startSide: multi ? range.start.side : undefined,
      },
      {
        onSuccess: () => clearComposer(),
        onError: (e) =>
          setError(e instanceof Error ? e.message : String(e)),
      },
    );
  }

  const selectedLo = range?.start.index ?? -1;
  const selectedHi = range?.end.index ?? -1;
  const composerAfter = range?.end.index ?? -1;

  return (
    <section className="diff-file">
      <header className="diff-file-head">
        <span className={`diff-file-status diff-file-status--${file.status}`}>
          {file.status}
        </span>
        <span className="diff-file-name">
          {file.previous_filename && file.previous_filename !== file.filename ? (
            <>
              {file.previous_filename} <span aria-hidden="true">→</span>{" "}
              {file.filename}
            </>
          ) : (
            file.filename
          )}
        </span>
        <PrLocStats additions={file.additions} deletions={file.deletions} />
      </header>
      {lines ? (
        <div className="diff-file-body">
          {lines.map((line, i) => {
            const commentable = lineAnchor(line, i) != null && headSha != null;
            const selected = range != null && i >= selectedLo && i <= selectedHi;
            return (
              <div key={i}>
                <div
                  className={`diff-line diff-line--${line.kind}${
                    commentable ? " diff-line--commentable" : ""
                  }${selected ? " is-selected" : ""}`}
                  role={commentable ? "button" : undefined}
                  tabIndex={commentable ? 0 : undefined}
                  title={
                    commentable
                      ? "Click to comment · Shift+click for range"
                      : undefined
                  }
                  onClick={
                    commentable
                      ? (e) => onLineClick(line, i, e.shiftKey)
                      : undefined
                  }
                  onKeyDown={
                    commentable
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onLineClick(line, i, e.shiftKey);
                          }
                        }
                      : undefined
                  }
                >
                  <span className="diff-gutter" aria-hidden="true">
                    {line.oldNo ?? ""}
                  </span>
                  <span className="diff-gutter" aria-hidden="true">
                    {line.newNo ?? ""}
                  </span>
                  <span className="diff-code">{line.text || "\u00A0"}</span>
                </div>
                {composerAfter === i && range && (
                  <div className="line-comment-composer">
                    <textarea
                      className="line-comment-input"
                      placeholder="Leave a comment on this line…"
                      rows={3}
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      disabled={addLine.isPending}
                    />
                    <div className="line-comment-actions">
                      <button
                        type="button"
                        className="line-comment-submit"
                        disabled={addLine.isPending || !draft.trim()}
                        onClick={submitLineComment}
                      >
                        {addLine.isPending ? "POSTING…" : "COMMENT"}
                      </button>
                      <button
                        type="button"
                        className="line-comment-cancel"
                        disabled={addLine.isPending}
                        onClick={clearComposer}
                      >
                        CANCEL
                      </button>
                    </div>
                    {error && (
                      <p className="line-comment-error">{error}</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="diff-file-empty">No inline diff available (binary or too large).</p>
      )}
    </section>
  );
}

function PrCommentComposer({
  owner,
  repo,
  number,
}: {
  owner: string;
  repo: string;
  number: number;
}) {
  const add = useAddPrComment();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [posted, setPosted] = useState(false);

  function submit() {
    if (!draft.trim()) return;
    setError(null);
    add.mutate(
      { ref: { owner, repo, number }, body: draft.trim() },
      {
        onSuccess: () => {
          setDraft("");
          setPosted(true);
          window.setTimeout(() => setPosted(false), 2000);
        },
        onError: (e) =>
          setError(e instanceof Error ? e.message : String(e)),
      },
    );
  }

  return (
    <section className="pr-comment-composer" aria-label="Leave a PR comment">
      <textarea
        className="pr-comment-input"
        placeholder="Leave a comment on this PR…"
        rows={3}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        disabled={add.isPending}
      />
      <div className="pr-comment-actions">
        <button
          type="button"
          className="pr-comment-submit"
          disabled={add.isPending || !draft.trim()}
          onClick={submit}
        >
          {add.isPending ? "POSTING…" : posted ? "POSTED" : "COMMENT"}
        </button>
      </div>
      {error && <p className="pr-comment-error">{error}</p>}
    </section>
  );
}

export function DiffPanel({
  owner,
  repo,
  number,
  title,
  url,
  author,
  onClose,
}: {
  owner: string;
  repo: string;
  number: number;
  title: string;
  url: string;
  author: string;
  onClose: () => void;
}) {
  const { data: me } = useMe();
  const isOwnPr =
    me?.login != null &&
    author.toLowerCase() === me.login.toLowerCase();
  const { data, isLoading, error } = usePrDiff(owner, repo, number, true);
  const bodyHtml = useMemo(
    () => (data?.body ? renderPrBody(data.body) : ""),
    [data?.body],
  );

  return (
    <aside className="diff-panel" aria-label={`Diff for #${number}`}>
      <header className="diff-panel-head">
        <div className="diff-panel-title">
          <a
            className="diff-panel-number"
            href={url}
            target="_blank"
            rel="noopener"
          >
            #{number}
          </a>
          <h2 className="diff-panel-name">{title}</h2>
        </div>
        <div className="diff-panel-actions">
          <button
            type="button"
            className="diff-panel-close"
            title="Close diff"
            aria-label="Close diff"
            onClick={onClose}
          >
            ✕
          </button>
        </div>
      </header>

      <div className="diff-panel-body">
        <ReviewActions
          owner={owner}
          repo={repo}
          number={number}
          isOwnPr={isOwnPr}
        />

        <PrCommentComposer owner={owner} repo={repo} number={number} />

        {isLoading && <p className="diff-panel-state">Loading diff…</p>}
        {error && (
          <p className="diff-panel-state diff-panel-state--err">
            {error instanceof Error ? error.message : "Failed to load diff"}
          </p>
        )}
        {bodyHtml && (
          <section
            className="diff-description"
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: bodyHtml }}
          />
        )}
        {data && data.files.length === 0 && (
          <p className="diff-panel-state">No files changed.</p>
        )}
        {data &&
          data.files.map((file) => (
            <FileDiff
              key={file.filename}
              file={file}
              headSha={data.head_sha}
              owner={owner}
              repo={repo}
              number={number}
            />
          ))}
      </div>
    </aside>
  );
}
