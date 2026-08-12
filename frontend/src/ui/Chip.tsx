import type { ReactNode } from "react";

export function Chip({
  variant,
  initial,
  checks,
  title,
  ariaLabel,
  error = false,
  disabled = false,
  onClick,
}: {
  variant: "approved" | "review" | "pending";
  initial: string;
  checks?: ReactNode;
  title?: string;
  ariaLabel?: string;
  error?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}) {
  if (variant === "pending") {
    const cls = [
      "chip",
      "reviewer-chip",
      "reviewer-chip--pending",
      error && "is-error",
    ]
      .filter(Boolean)
      .join(" ");
    return (
      <button
        type="button"
        className={cls}
        title={title}
        aria-label={ariaLabel ?? title}
        disabled={disabled}
        onClick={onClick}
      >
        <span className="chip-key">{initial}</span>
        {checks && <span className="chip-checks">{checks}</span>}
      </button>
    );
  }

  const cls =
    variant === "approved"
      ? "chip chip--approved reviewer-chip"
      : "chip chip--review reviewer-chip";

  return (
    <span className={cls} title={title}>
      <span className="chip-key">{initial}</span>
      {checks && <span className="chip-checks">{checks}</span>}
    </span>
  );
}
