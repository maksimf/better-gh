import { EyeIcon } from "./icons";

export function WatchToggle({
  pressed,
  onToggle,
}: {
  pressed: boolean;
  onToggle: () => void;
}) {
  const title = pressed
    ? "Watching -- you'll get a browser notification when checks pass and the preview is ready"
    : "Watch -- notify me when checks pass and the preview is ready";
  return (
    <button
      type="button"
      className="watch-toggle"
      title={title}
      aria-label={title}
      aria-pressed={pressed}
      onClick={onToggle}
    >
      <span className="watch-toggle-check" aria-hidden="true">
        <EyeIcon />
      </span>
      <span className="watch-toggle-label">Watch</span>
    </button>
  );
}
