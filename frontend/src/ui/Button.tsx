import type { ButtonHTMLAttributes, ReactNode } from "react";

type Common = {
  disabled?: boolean;
  onClick?: ButtonHTMLAttributes<HTMLButtonElement>["onClick"];
  children: ReactNode;
  title?: string;
  ariaLabel?: string;
  className?: string;
  type?: ButtonHTMLAttributes<HTMLButtonElement>["type"];
};

type ChromeButton = Common & {
  surface: "chrome";
  variant: "theme" | "settings" | "signout" | "refresh" | "signin";
};

type ModalButton = Common & {
  surface: "modal";
  modal: "merge" | "note" | "qa";
  variant: string;
};

type ReviewButton = Common & {
  surface: "review";
  variant: "changes" | "comment";
};

type ToggleButton = Common & {
  surface: "toggle";
  variant: "diff" | "code";
  active?: boolean;
};

type CommentButton = Common & {
  surface: "comment";
  variant: "line-submit" | "line-cancel" | "pr-submit";
};

type DrawerButton = Common & {
  surface: "drawer";
  variant: "clear" | "toggle";
  active?: boolean;
};

type HcpButton = Common & {
  surface: "hcp";
  variant: "ack" | "reply" | "submit" | "cancel";
};

type CloseButton = Common & {
  surface: "close";
  modal: "merge" | "settings" | "note" | "qa" | "video";
};

export type ButtonProps =
  | ChromeButton
  | ModalButton
  | ReviewButton
  | ToggleButton
  | CommentButton
  | DrawerButton
  | HcpButton
  | CloseButton;

function resolveClassName(props: ButtonProps): string {
  switch (props.surface) {
    case "chrome":
      return `btn btn--${props.variant}`;
    case "modal":
      return `${props.modal}-modal-btn ${props.modal}-modal-btn--${props.variant}`;
    case "review":
      return `review-button review-button--${props.variant}`;
    case "toggle": {
      const base =
        props.variant === "diff" ? "review-diff-toggle" : "pr-open-code";
      return `${base}${props.active ? " is-active" : ""}`;
    }
    case "comment": {
      const map = {
        "line-submit": "line-comment-submit",
        "line-cancel": "line-comment-cancel",
        "pr-submit": "pr-comment-submit",
      } as const;
      return map[props.variant];
    }
    case "drawer": {
      if (props.variant === "clear") {
        return "notes-drawer-btn notes-drawer-btn--clear";
      }
      return `notes-drawer-btn${props.active ? " notes-drawer-btn--active" : ""}`;
    }
    case "hcp":
      return `hcp-btn hcp-btn--${props.variant}`;
    case "close":
      return `${props.modal}-modal-close`;
  }
}

export function Button(props: ButtonProps) {
  const {
    disabled,
    onClick,
    children,
    title,
    ariaLabel,
    className,
    type = "button",
  } = props;

  const cls = [resolveClassName(props), className].filter(Boolean).join(" ");

  return (
    <button
      type={type}
      className={cls}
      title={title}
      aria-label={ariaLabel}
      aria-pressed={
        props.surface === "toggle" ||
        (props.surface === "drawer" && props.variant === "toggle")
          ? Boolean(props.active)
          : undefined
      }
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
