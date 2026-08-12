import type { ReactNode } from "react";

export type CardToggleVariant = "reviewed" | "watch" | "note" | "deferred";

export function CardToggle({
  variant,
  pressed = false,
  disabled = false,
  title,
  ariaLabel,
  onClick,
  icon,
}: {
  variant: CardToggleVariant;
  pressed?: boolean;
  disabled?: boolean;
  title: string;
  ariaLabel?: string;
  onClick: () => void;
  icon: ReactNode;
}) {
  return (
    <button
      type="button"
      className={`card-toggle card-toggle--${variant}`}
      title={title}
      aria-label={ariaLabel ?? title}
      aria-pressed={pressed}
      disabled={disabled}
      onClick={onClick}
    >
      <span className="card-toggle-icon" aria-hidden="true">
        {icon}
      </span>
    </button>
  );
}
