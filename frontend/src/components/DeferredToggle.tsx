import { SquareIcon } from "./icons";

export function DeferredToggle({
  pressed,
  onToggle,
}: {
  pressed: boolean;
  onToggle: () => void;
}) {
  const title = pressed
    ? "Deferred — click to restore to the board"
    : "Defer — hide from the board for now";
  return (
    <button
      type="button"
      className="card-toggle card-toggle--deferred"
      title={title}
      aria-label={title}
      aria-pressed={pressed}
      onClick={onToggle}
    >
      <span className="card-toggle-icon" aria-hidden="true">
        <SquareIcon />
      </span>
    </button>
  );
}
