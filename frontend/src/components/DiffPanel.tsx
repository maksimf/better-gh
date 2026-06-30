import { useMemo } from "react";
import { marked } from "marked";

import { usePrDiff } from "../api/queries";
import type { DiffFile } from "../api/types";
import { ApproveButton } from "./ApproveButton";
import { PrLocStats } from "./PrLocStats";

type LineKind = "add" | "del" | "context" | "hunk" | "meta";

interface DiffLine {
  kind: LineKind;
  oldNo: number | null;
  newNo: number | null;
  text: string;
}

const HUNK_RE = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/;

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

function FileDiff({ file }: { file: DiffFile }) {
  const lines = useMemo(
    () => (file.patch ? parsePatch(file.patch) : null),
    [file.patch],
  );

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
          {lines.map((line, i) => (
            <div key={i} className={`diff-line diff-line--${line.kind}`}>
              <span className="diff-gutter" aria-hidden="true">
                {line.oldNo ?? ""}
              </span>
              <span className="diff-gutter" aria-hidden="true">
                {line.newNo ?? ""}
              </span>
              <span className="diff-code">{line.text || "\u00A0"}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="diff-file-empty">No inline diff available (binary or too large).</p>
      )}
    </section>
  );
}

export function DiffPanel({
  owner,
  repo,
  number,
  title,
  url,
  onClose,
}: {
  owner: string;
  repo: string;
  number: number;
  title: string;
  url: string;
  onClose: () => void;
}) {
  const { data, isLoading, error } = usePrDiff(owner, repo, number, true);

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
          <ApproveButton owner={owner} repo={repo} number={number} />
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
        {isLoading && <p className="diff-panel-state">Loading diff…</p>}
        {error && (
          <p className="diff-panel-state diff-panel-state--err">
            {error instanceof Error ? error.message : "Failed to load diff"}
          </p>
        )}
        {data && data.body && (
          <section
            className="diff-description"
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: marked(data.body) as string }}
          />
        )}
        {data && data.files.length === 0 && (
          <p className="diff-panel-state">No files changed.</p>
        )}
        {data &&
          data.files.map((file) => (
            <FileDiff key={file.filename} file={file} />
          ))}
      </div>
    </aside>
  );
}
