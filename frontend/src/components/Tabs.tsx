import type { TabName } from "../hooks/useActiveTab";

export function Tabs({
  active,
  mineCount,
  reviewsCount,
  onSelect,
}: {
  active: TabName;
  mineCount: number;
  reviewsCount: number;
  onSelect: (tab: TabName) => void;
}) {
  return (
    <nav className="tabs" role="tablist" aria-label="Dashboard tabs">
      <button
        type="button"
        className={`tab${active === "mine" ? " is-active" : ""}`}
        role="tab"
        aria-selected={active === "mine"}
        onClick={() => onSelect("mine")}
      >
        MY PRs <span className="tab-count">{mineCount}</span>
      </button>
      <button
        type="button"
        className={`tab${active === "reviews" ? " is-active" : ""}`}
        role="tab"
        aria-selected={active === "reviews"}
        onClick={() => onSelect("reviews")}
      >
        REVIEWING <span className="tab-count">{reviewsCount}</span>
      </button>
    </nav>
  );
}
