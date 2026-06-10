import { CheckIcon } from "./icons";

export function ReviewedToggle({
  pressed,
  onToggle,
}: {
  pressed: boolean;
  onToggle: () => void;
}) {
  const title = pressed
    ? "Reviewed by you -- click to unmark"
    : "Mark as reviewed by you";
  return (
    <button
      type="button"
      className="card-toggle card-toggle--reviewed"
      title={title}
      aria-label={title}
      aria-pressed={pressed}
      onClick={onToggle}
    >
      <span className="card-toggle-icon" aria-hidden="true">
        <CheckIcon />
      </span>
    </button>
  );
}
