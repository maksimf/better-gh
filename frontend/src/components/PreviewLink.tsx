import { useState } from "react";

import { CopyCheckGlyph, CopyGlyph } from "./icons";

function fallbackCopy(text: string): boolean {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  document.body.removeChild(ta);
  return ok;
}

export function PreviewLink({ url }: { url: string | null }) {
  const [copied, setCopied] = useState(false);

  if (!url) {
    return <span className="preview preview--pending">preview is pending</span>;
  }

  function flash() {
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  function onCopy() {
    if (!url) return;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(url)
        .then(flash)
        .catch(() => {
          if (fallbackCopy(url)) flash();
        });
    } else if (fallbackCopy(url)) {
      flash();
    }
  }

  return (
    <span className="preview-group">
      <a
        className="preview preview--live"
        href={url}
        target="_blank"
        rel="noopener"
      >
        preview &uarr;
      </a>
      <button
        type="button"
        className={`preview-copy${copied ? " is-copied" : ""}`}
        aria-label="Copy preview URL"
        title="Copy preview URL"
        onClick={onCopy}
      >
        <CopyGlyph />
        <CopyCheckGlyph />
      </button>
    </span>
  );
}
