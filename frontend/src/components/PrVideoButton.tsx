import { useEffect, useId, useMemo, useRef, useState } from "react";

import { VideoIcon } from "./icons";

const GITHUB_ATTACHMENT_RE = /^https:\/\/github\.com\/user-attachments\//i;

export function PrVideoButton({
  url,
  number,
}: {
  url: string;
  number: number;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        className="pr-video-button"
        title="Play video from PR description"
        aria-label={`Play video from pull request ${number}`}
        onClick={() => setOpen(true)}
      >
        <VideoIcon />
      </button>
      <PrVideoModal
        open={open}
        url={url}
        number={number}
        onClose={() => setOpen(false)}
      />
    </>
  );
}

function PrVideoModal({
  open,
  url,
  number,
  onClose,
}: {
  open: boolean;
  url: string;
  number: number;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [mediaError, setMediaError] = useState(false);
  const embedUrl = useMemo(() => videoEmbedUrl(url), [url]);
  const playbackUrl = GITHUB_ATTACHMENT_RE.test(url)
    ? `/attachments?url=${encodeURIComponent(url)}`
    : url;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
    if (open) setMediaError(false);
  }, [open, url]);

  return (
    <dialog
      ref={dialogRef}
      className="video-modal"
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialogRef.current) onClose();
      }}
    >
      <header className="video-modal-header">
        <h2 id={titleId} className="video-modal-title">
          PR #{number} VIDEO
        </h2>
        <button
          type="button"
          className="video-modal-close"
          aria-label="Close video"
          onClick={onClose}
        >
          &times;
        </button>
      </header>
      <div className="video-modal-body">
        {open && embedUrl && (
          <iframe
            className="video-modal-player video-modal-embed"
            src={embedUrl}
            title={`Video from pull request ${number}`}
            allow="autoplay; fullscreen; picture-in-picture"
            allowFullScreen
          />
        )}
        {open && !embedUrl && !mediaError && (
          // eslint-disable-next-line jsx-a11y/media-has-caption -- PR
          // walkthroughs do not include a separate caption track.
          <video
            className="video-modal-player"
            src={playbackUrl}
            controls
            autoPlay
            playsInline
            onError={() => setMediaError(true)}
          />
        )}
        {open && mediaError && (
          <p className="video-modal-msg video-modal-msg--error">
            This video could not be played here.{" "}
            <a href={url} target="_blank" rel="noopener">
              Open the video
            </a>
            .
          </p>
        )}
      </div>
    </dialog>
  );
}

function videoEmbedUrl(rawUrl: string): string | null {
  try {
    const url = new URL(rawUrl);
    const host = url.hostname.toLowerCase().replace(/^www\./, "");
    const parts = url.pathname.split("/").filter(Boolean);
    const lastPart = parts[parts.length - 1] ?? "";

    if (host === "youtu.be") {
      return youtubeEmbed(parts[0]);
    }
    if (host === "youtube.com") {
      if (url.pathname === "/watch") return youtubeEmbed(url.searchParams.get("v"));
      if (parts[0] === "shorts" || parts[0] === "embed") {
        return youtubeEmbed(parts[1]);
      }
    }
    if (host === "loom.com" && (parts[0] === "share" || parts[0] === "embed")) {
      return safeEmbedId(parts[1])
        ? `https://www.loom.com/embed/${parts[1]}`
        : null;
    }
    if (
      (host === "vimeo.com" || host === "player.vimeo.com") &&
      /^\d+$/.test(lastPart)
    ) {
      return `https://player.vimeo.com/video/${lastPart}`;
    }
  } catch {
    return null;
  }
  return null;
}

function youtubeEmbed(id: string | null | undefined): string | null {
  return safeEmbedId(id) ? `https://www.youtube-nocookie.com/embed/${id}` : null;
}

function safeEmbedId(id: string | null | undefined): id is string {
  return typeof id === "string" && /^[a-zA-Z0-9_-]+$/.test(id);
}
