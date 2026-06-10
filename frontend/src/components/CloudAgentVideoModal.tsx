import { useEffect, useRef } from "react";

import { useCloudAgentVideo } from "../api/queries";

/**
 * Plays a cloud agent's recorded walkthrough. The presigned URL is fetched
 * lazily (only while open) since it expires in ~15 min.
 */
export function CloudAgentVideoModal({
  open,
  agentId,
  path,
  onClose,
}: {
  open: boolean;
  agentId: string;
  path: string | null;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const { data, isLoading, isError, error } = useCloudAgentVideo(
    agentId,
    path,
    open,
  );

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className="video-modal"
      aria-labelledby="video-modal-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === dialogRef.current) onClose();
      }}
    >
      <header className="video-modal-header">
        <h2 id="video-modal-title" className="video-modal-title">
          QA WALKTHROUGH
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
        {isLoading && <p className="video-modal-msg">Loading video&hellip;</p>}
        {isError && (
          <p className="video-modal-msg video-modal-msg--error">
            Couldn't load video
            {error instanceof Error ? `: ${error.message}` : ""}.
          </p>
        )}
        {data?.url && (
          // eslint-disable-next-line jsx-a11y/media-has-caption -- agent
          // recordings have no caption track.
          <video
            className="video-modal-player"
            src={data.url}
            controls
            autoPlay
            playsInline
          />
        )}
      </div>
    </dialog>
  );
}
