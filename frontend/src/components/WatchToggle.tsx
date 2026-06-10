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
      ? "Watching -- you'll get an ntfy notification when checks pass and the preview is ready"
      : "Watch -- notify me when checks pass and the preview is ready";
  return (
    <button
      type="button"
      className="watch-toggle"
      title={title}
      aria-label={title}
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onToggle}
    >
      <span className="watch-toggle-check" aria-hidden="true">
        <EyeIcon />
      </span>
      <span className="watch-toggle-label">Watch</span>
    </button>
  );
}
