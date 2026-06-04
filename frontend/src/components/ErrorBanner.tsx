import type { DashboardError } from "../api/types";
import { formatUntil, useNow } from "../hooks/useRelativeTime";

export function ErrorBanner({ error }: { error: DashboardError | null }) {
  const now = useNow(30_000);
  if (!error) return null;

  return (
    <aside className="error-banner" role="alert" aria-live="polite">
      <div className="error-banner-inner" role="alert">
        <span className="error-banner-icon" aria-hidden="true">
          !
        </span>
        <span className="error-banner-text">
          <strong>{error.message}</strong>
          {error.reset_at && (
            <span className="error-banner-hint">
              {" "}
              Try again{" "}
              <span className="error-banner-relative">
                {formatUntil(error.reset_at, now)}
              </span>
              .
            </span>
          )}
        </span>
      </div>
    </aside>
  );
}
