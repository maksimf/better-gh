import { useEffect, useMemo, useState } from "react";

import type { Pr } from "./api/types";
import { useDashboard, usePrefs } from "./api/queries";
import { Board } from "./components/Board";
import { Loader } from "./components/Loader";
import { ErrorBanner } from "./components/ErrorBanner";
import { FooterMeta } from "./components/FooterMeta";
import { NotesDrawer } from "./components/NotesDrawer";
import { PageTitleRow } from "./components/PageTitleRow";
import { PickerEmptyState } from "./components/PickerEmptyState";
import { ReviewsList } from "./components/ReviewsList";
import { SettingsModal } from "./components/SettingsModal";
import { Tabs } from "./components/Tabs";
import { TopBar } from "./components/TopBar";
import { hydrate as hydratePrefs } from "./hooks/prefsStore";
import { useActiveTab } from "./hooks/useActiveTab";
import { useDeferredKeys, deferredKey } from "./hooks/useDeferredKeys";
import { useReviewedKeys } from "./hooks/useReviewedKeys";
import { useNtfyChannel } from "./hooks/useNtfyChannel";
import { useReviewers } from "./hooks/useReviewers";
import { useSelectedRepos } from "./hooks/useSelectedRepos";
import { useWatchedKeys } from "./hooks/useWatchedKeys";

const TAB_LABELS = { mine: "MY PRs", reviews: "REVIEWING" } as const;

function countMyPrColumns(prs: Pr[]) {
  let wip = 0;
  let ready = 0;
  let approved = 0;
  for (const pr of prs) {
    if (pr.column === "progress") wip += 1;
    else if (pr.column === "ready") ready += 1;
    else if (pr.column === "approved") approved += 1;
  }
  return { wip, ready, approved };
}

export function App() {
  const {
    reviewers,
    param: reviewersParam,
    setReviewers,
  } = useReviewers();
  const repoStore = useSelectedRepos();
  const reviewed = useReviewedKeys();
  const deferred = useDeferredKeys();
  const watched = useWatchedKeys();
  const { channel: ntfyChannel, setChannel: setNtfyChannel } = useNtfyChannel();
  const { tab, setTab } = useActiveTab();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);

  const dashboard = useDashboard(reviewersParam);
  const data = dashboard.data;

  // Effective reviewers shown in SETTINGS: the viewer's local config, or
  // the server's resolved default while they haven't configured their own.
  const effectiveReviewers = reviewers ?? data?.reviewers ?? [];

  // Fold the server's synced preferences into the local store whenever they
  // (re)load -- this is how another device's changes show up here.
  const prefs = usePrefs();
  const prefsData = prefs.data;
  useEffect(() => {
    if (prefsData) hydratePrefs(prefsData);
  }, [prefsData]);

  // Watching is only meaningful once an ntfy channel is configured.
  const watchDisabled = ntfyChannel.trim() === "";
  const onToggleWatch = (key: string) => {
    watched.toggle(key);
  };

  // Consume any legacy ignored-repos list once the repo summary lands.
  const { migrateFromRepos } = repoStore;
  useEffect(() => {
    if (data) migrateFromRepos(data.repos.map((r) => r.repo));
  }, [data, migrateFromRepos]);

  const visiblePrs = useMemo(
    () => (data ? data.prs.filter((pr) => repoStore.isVisible(pr.repo)) : []),
    [data, repoStore],
  );
  const visibleReviews = useMemo(
    () =>
      data ? data.reviews.filter((pr) => repoStore.isVisible(pr.repo)) : [],
    [data, repoStore],
  );

  const splitByDeferred = <T extends { repo: string; number: number }>(
    items: T[],
  ) => {
    const active: T[] = [];
    const parked: T[] = [];
    for (const item of items) {
      const key = deferredKey(item.repo, item.number);
      if (deferred.has(key)) parked.push(item);
      else active.push(item);
    }
    return { active, parked };
  };

  const { active: activePrs, parked: deferredPrs } = useMemo(
    () => splitByDeferred(visiblePrs),
    [visiblePrs, deferred.has],
  );
  const { active: activeReviews, parked: deferredReviews } = useMemo(
    () => splitByDeferred(visibleReviews),
    [visibleReviews, deferred.has],
  );

  // Browser tab: "W: N, R: M, A: X ⋅ MY PRs · BETTER//GH"
  useEffect(() => {
    const suffix = `${TAB_LABELS[tab]} \u00B7 BETTER//GH`;
    if (!data) {
      document.title = suffix;
      return;
    }
    const { wip, ready, approved } = countMyPrColumns(activePrs);
    document.title = `W: ${wip}, R: ${ready}, A: ${approved} \u22C5 ${suffix}`;
  }, [tab, data, activePrs]);

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
            mineCount={activePrs.length}
            reviewsCount={activeReviews.length}
            onSelect={setTab}
          />
          <PageTitleRow title={TAB_LABELS[tab]} />
          <main>
            {tab === "mine" ? (
              <Board
                prs={activePrs}
                deferredPrs={deferredPrs}
                reviewedHas={reviewed.has}
                onToggleReviewed={reviewed.toggle}
                deferredHas={deferred.has}
                onToggleDeferred={deferred.toggle}
                watchedHas={watched.has}
                onToggleWatch={onToggleWatch}
                watchDisabled={watchDisabled}
              />
            ) : (
              <ReviewsList
                reviews={activeReviews}
                deferredReviews={deferredReviews}
                reviewedHas={reviewed.has}
                onToggleReviewed={reviewed.toggle}
                deferredHas={deferred.has}
                onToggleDeferred={deferred.toggle}
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
        reviewers={effectiveReviewers}
        onReviewersChange={setReviewers}
        ntfyChannel={ntfyChannel}
        onNtfyChannelChange={setNtfyChannel}
      />

      <NotesDrawer
        open={notesOpen}
        onOpen={() => setNotesOpen(true)}
        onClose={() => setNotesOpen(false)}
      />
    </>
  );
}
