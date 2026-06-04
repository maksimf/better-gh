// Centered initial-load indicator. Shown while the first dashboard fetch
// is in flight, in place of the board/reviews.
export function Loader() {
  return (
    <div className="page-loader" role="status" aria-live="polite">
      <span className="page-loader-spinner" aria-hidden="true"></span>
      <span className="page-loader-text">{"Loading\u2026"}</span>
    </div>
  );
}
