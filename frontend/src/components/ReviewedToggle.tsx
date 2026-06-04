import { CheckIcon } from "./icons";

export function ReviewedToggle({
  pressed,
  onToggle,
}: {
  pressed: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      className="reviewed-toggle"
      title="Toggle manually-reviewed marker"
      aria-label="Toggle manually-reviewed marker"
      aria-pressed={pressed}
      onClick={onToggle}
    >
      <span className="reviewed-toggle-check" aria-hidden="true">
        <CheckIcon />
      </span>
      <span className="reviewed-toggle-label">Reviewed</span>
    </button>
  );
}
