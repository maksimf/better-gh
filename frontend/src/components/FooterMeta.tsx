import { formatRelative, useNow } from "../hooks/useRelativeTime";

export function FooterMeta({
  lastPolledAt,
}: {
  lastPolledAt: string | null;
}) {
  const now = useNow();
  const label = lastPolledAt ? formatRelative(lastPolledAt, now) : "never";
  return (
    <aside className="footer-meta" aria-live="polite">
      LAST UPDATED <span className="last-updated-relative">{label}</span>
    </aside>
  );
}
