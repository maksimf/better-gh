import {
  useEffect,
  useRef,
  type MouseEvent,
  type ReactNode,
} from "react";

/**
 * Native &lt;dialog&gt; shell used by every modal in the app.
 * Emits the caller-supplied className unchanged so existing CSS keeps working.
 */
export function Dialog({
  open,
  onClose,
  className,
  ariaLabelledBy,
  closeOnBackdrop = true,
  blockBackdropClose = false,
  onDialogClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  className: string;
  ariaLabelledBy: string;
  closeOnBackdrop?: boolean;
  blockBackdropClose?: boolean;
  onDialogClose?: () => void;
  children: ReactNode;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  function handleClick(e: MouseEvent<HTMLDialogElement>) {
    if (!closeOnBackdrop) return;
    if (e.target !== dialogRef.current) return;
    if (blockBackdropClose) return;
    onClose();
  }

  return (
    <dialog
      ref={dialogRef}
      className={className}
      aria-labelledby={ariaLabelledBy}
      onClose={onDialogClose ?? onClose}
      onClick={handleClick}
    >
      {children}
    </dialog>
  );
}
