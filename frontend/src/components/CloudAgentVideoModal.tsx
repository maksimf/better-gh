import { useCloudAgentVideo } from "../api/queries";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";

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
  const { data, isLoading, isError, error } = useCloudAgentVideo(
    agentId,
    path,
    open,
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      className="video-modal"
      ariaLabelledBy="video-modal-title"
    >
      <header className="video-modal-header">
        <h2 id="video-modal-title" className="video-modal-title">
          QA WALKTHROUGH
        </h2>
        <Button
          surface="close"
          modal="video"
          ariaLabel="Close video"
          onClick={onClose}
        >
          &times;
        </Button>
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
    </Dialog>
  );
}
