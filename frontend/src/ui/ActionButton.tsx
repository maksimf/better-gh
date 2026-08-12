import type { ButtonHTMLAttributes, ReactNode } from "react";

export type ActionKind =
  | "approve"
  | "merge"
  | "ready"
  | "bulk-merge"
  | "review-request";

const KIND_CLASS: Record<ActionKind, string> = {
  approve: "approve-button",
  merge: "merge-button",
  ready: "ready-button",
  "bulk-merge": "bulk-merge-button",
  "review-request": "review-request",
};

const DONE_CLASS: Partial<Record<ActionKind, string>> = {
  approve: "is-approved",
  merge: "is-merged",
};

type CommonProps = {
  kind: ActionKind;
  error?: boolean;
  disabled?: boolean;
  title?: string;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
  type?: ButtonHTMLAttributes<HTMLButtonElement>["type"];
  "aria-label"?: string;
};

type IdleProps = CommonProps & { done?: false };
type DoneProps = CommonProps & { done: true; kind: "approve" | "merge" };

export type ActionButtonProps = IdleProps | DoneProps;

export function ActionButton(props: ActionButtonProps) {
  const {
    kind,
    done = false,
    error = false,
    disabled = false,
    title,
    onClick,
    children,
    className,
    type = "button",
    "aria-label": ariaLabel,
  } = props;

  const base = KIND_CLASS[kind];
  const doneMod = done ? DONE_CLASS[kind] : undefined;
  const cls = [base, doneMod, error && "is-error", className]
    .filter(Boolean)
    .join(" ");

  if (done && (kind === "approve" || kind === "merge")) {
    return (
      <span className={cls} aria-disabled="true" title={title}>
        {children}
      </span>
    );
  }

  return (
    <button
      type={type}
      className={cls}
      title={title}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
