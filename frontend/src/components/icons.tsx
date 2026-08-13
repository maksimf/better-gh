// Hard-edged geometric glyphs matching the Bauhaus brand vocabulary in
// styles.css. Sized via CSS (`.check-icon` etc.) so they inherit color
// through currentColor.

export function CheckIcon() {
  return (
    <svg className="check-icon" viewBox="0 0 16 16" focusable="false">
      <path
        d="M3 8.5 L7 12 L13 4"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="square"
        strokeLinejoin="miter"
      />
    </svg>
  );
}

export function EyeIcon() {
  return (
    <svg className="check-icon" viewBox="0 0 16 16" focusable="false">
      <path
        d="M1 8 C3 4 13 4 15 8 C13 12 3 12 1 8 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="miter"
      />
      <circle cx="8" cy="8" r="2" fill="currentColor" />
    </svg>
  );
}

export function NoteIcon() {
  return (
    <svg className="check-icon" viewBox="0 0 16 16" focusable="false">
      <rect
        x="2.5"
        y="1.5"
        width="11"
        height="13"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M5 5 H11 M5 8 H11 M5 11 H9"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="square"
      />
    </svg>
  );
}

export function PauseIcon() {
  return (
    <svg className="check-icon" viewBox="0 0 16 16" focusable="false">
      <rect x="4" y="3.5" width="2.5" height="9" fill="currentColor" />
      <rect x="9.5" y="3.5" width="2.5" height="9" fill="currentColor" />
    </svg>
  );
}

export function EllipsisIcon() {
  return (
    <svg className="check-icon" viewBox="0 0 16 16" focusable="false">
      <rect x="1" y="6.5" width="3" height="3" fill="currentColor" />
      <rect x="6.5" y="6.5" width="3" height="3" fill="currentColor" />
      <rect x="12" y="6.5" width="3" height="3" fill="currentColor" />
    </svg>
  );
}

export function VideoIcon() {
  return (
    <svg className="video-icon" viewBox="0 0 18 14" focusable="false">
      <rect
        x="1"
        y="1"
        width="16"
        height="12"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path d="M7 4 L12 7 L7 10 Z" fill="currentColor" />
    </svg>
  );
}

export function BrandMark({ large = false }: { large?: boolean }) {
  return (
    <span
      className={`brand-mark${large ? " brand-mark--large" : ""}`}
      aria-hidden="true"
    >
      <span className="shape shape--circle"></span>
      <span className="shape shape--square"></span>
      <span className="shape shape--triangle"></span>
    </span>
  );
}
