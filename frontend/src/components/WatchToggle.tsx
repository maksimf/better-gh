import { EyeIcon } from "./icons";

export function WatchToggle({
  pressed,
  onToggle,
  disabled = false,
}: {
  pressed: boolean;
  onToggle: () => void;
  disabled?: boolean;
}) {
  const title = disabled
    ? "set ntfy channel in settings"
    : pressed
      ? "Watching — the server will ntfy you when checks pass and the preview is ready"
      : "Watch — notify me when checks pass and the preview is ready";
  return (
    <button
      type="button"
      className="card-toggle card-toggle--watch"
      title={title}
      aria-label={title}
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onToggle}
    >
      <span className="card-toggle-icon" aria-hidden="true">
        <EyeIcon />
      </span>
    </button>
  );
}
