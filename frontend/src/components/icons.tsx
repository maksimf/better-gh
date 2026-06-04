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

export function CopyGlyph() {
  return (
    <svg
      className="icon icon--copy"
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
    >
      <rect
        x="2.5"
        y="2.5"
        width="9"
        height="9"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <rect
        x="5.5"
        y="5.5"
        width="9"
        height="9"
        fill="currentColor"
        stroke="currentColor"
        strokeWidth="2"
      />
      <rect x="6.5" y="6.5" width="7" height="7" fill="var(--white,#fafafa)" />
    </svg>
  );
}

export function CopyCheckGlyph() {
  return (
    <svg
      className="icon icon--check"
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
    >
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
