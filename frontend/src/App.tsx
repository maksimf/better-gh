import { useEffect, useMemo, useState } from "react";

import { useDashboard } from "./api/queries";
import { Board } from "./components/Board";
import { Loader } from "./components/Loader";
import { ErrorBanner } from "./components/ErrorBanner";
import { FooterMeta } from "./components/FooterMeta";
import { PageTitleRow } from "./components/PageTitleRow";
import { PickerEmptyState } from "./components/PickerEmptyState";
import { ReviewsList } from "./components/ReviewsList";
import { SettingsModal } from "./components/SettingsModal";
import { Tabs } from "./components/Tabs";
import { TopBar } from "./components/TopBar";
import { useActiveTab } from "./hooks/useActiveTab";
import { useReviewedKeys } from "./hooks/useReviewedKeys";
import { useReviewer } from "./hooks/useReviewer";
import { useSelectedRepos } from "./hooks/useSelectedRepos";
import { useWatchedKeys } from "./hooks/useWatchedKeys";
import {
  ensureNotificationPermission,
  useWatchNotifications,
} from "./hooks/useWatchNotifications";

const TAB_LABELS = { mine: "MY PRs", reviews: "REVIEWING" } as const;

export function App() {
  const { reviewer, setReviewer } = useReviewer();
  const repoStore = useSelectedRepos();
  const reviewed = useReviewedKeys();
  const watched = useWatchedKeys();
  const { tab, setTab } = useActiveTab();
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Keep polling while the tab is hidden only when something is watched, so
  // the "checks went green" notification can fire on an inactive tab.
  const dashboard = useDashboard(reviewer, watched.hasAny);
  const data = dashboard.data;

  // Fire a browser notification when a watched PR's checks all turn green.
  useWatchNotifications(data?.prs, watched.has);

  // Request notification permission when the user opts a PR into watching.
  const onToggleWatch = (key: string) => {
    if (!watched.has(key)) void ensureNotificationPermission();
    watched.toggle(key);
  };

  // Consume any legacy ignored-repos list once the repo summary lands.
  const { migrateFromRepos } = repoStore;
  useEffect(() => {
    if (data) migrateFromRepos(data.repos.map((r) => r.repo));
  }, [data, migrateFromRepos]);

  // Reflect the active tab in the document title.
  useEffect(() => {
    document.title = `${TAB_LABELS[tab]} \u00B7 BETTER//GH`;
  }, [tab]);

  const visiblePrs = useMemo(
    () => (data ? data.prs.filter((pr) => repoStore.isVisible(pr.repo)) : []),
    [data, repoStore],
  );
  const visibleReviews = useMemo(
    () =>
      data ? data.reviews.filter((pr) => repoStore.isVisible(pr.repo)) : [],
    [data, repoStore],
  );

  const loading = dashboard.isLoading && !data;
  const selectionEmpty = repoStore.isSelectionEmpty();

  return (
    <>
      <TopBar onOpenSettings={() => setSettingsOpen(true)} />

      {data?.error && <ErrorBanner error={data.error} />}

      {loading ? (
        <main>
          <Loader />
        </main>
      ) : selectionEmpty ? (
        <main>
          <PickerEmptyState
            repos={data?.repos ?? []}
            has={repoStore.has}
            onToggle={repoStore.toggle}
          />
        </main>
      ) : (
        <>
          <Tabs
            active={tab}
            mineCount={visiblePrs.length}
            reviewsCount={visibleReviews.length}
            onSelect={setTab}
          />
          <PageTitleRow title={TAB_LABELS[tab]} />
          <main>
            {tab === "mine" ? (
              <Board
                prs={visiblePrs}
                reviewer={data?.reviewer ?? ""}
                reviewedHas={reviewed.has}
                onToggleReviewed={reviewed.toggle}
                watchedHas={watched.has}
                onToggleWatch={onToggleWatch}
              />
            ) : (
              <ReviewsList
                reviews={visibleReviews}
                reviewedHas={reviewed.has}
                onToggleReviewed={reviewed.toggle}
              />
            )}
          </main>
        </>
      )}

      {data && <FooterMeta lastPolledAt={data.last_polled_at} />}

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        repos={data?.repos ?? []}
        has={repoStore.has}
        onToggleRepo={repoStore.toggle}
        reviewerInitial={reviewer ?? data?.reviewer ?? ""}
        onReviewerChange={setReviewer}
      />
    </>
  );
}
