import { useEffect, useMemo, useRef, useState } from "react";

import { useUserSearch } from "../api/queries";

const SEARCH_DEBOUNCE_MS = 300;

/**
 * Multi-reviewer editor: a row of removable chips plus a typeahead that
 * searches GitHub users (debounced) and lets the viewer add a reviewer by
 * clicking a result or pressing Enter on a raw login. The parent owns the
 * list; every change calls ``onChange`` with the full next array.
 */
export function ReviewerPicker({
  reviewers,
  onChange,
}: {
  reviewers: string[];
  onChange: (next: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(query), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [query]);

  const search = useUserSearch(debounced);

  const have = useMemo(
    () => new Set(reviewers.map((r) => r.toLowerCase())),
    [reviewers],
  );

  // Drop anyone already tracked so the dropdown only offers new logins.
  const results = (search.data ?? []).filter((u) => !have.has(u.login.toLowerCase()));

  function add(login: string) {
    const value = login.trim();
    if (!value) return;
    if (have.has(value.toLowerCase())) {
      setQuery("");
      return;
    }
    onChange([...reviewers, value]);
    setQuery("");
    setOpen(false);
    inputRef.current?.focus();
  }

  function remove(login: string) {
    onChange(reviewers.filter((r) => r.toLowerCase() !== login.toLowerCase()));
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      // Prefer the top search hit; otherwise add the raw typed login.
      if (results.length > 0) add(results[0].login);
      else if (query.trim()) add(query);
    } else if (e.key === "Backspace" && query === "" && reviewers.length > 0) {
      remove(reviewers[reviewers.length - 1]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const showDropdown =
    open && debounced.trim().length > 0 && (search.isFetching || results.length > 0);

  return (
    <div className="reviewer-picker">
      <div className="reviewer-picker-chips">
        {reviewers.map((login) => (
          <span key={login} className="reviewer-token">
            <span className="reviewer-token-at" aria-hidden="true">
              @
            </span>
            <span className="reviewer-token-login">{login}</span>
            <button
              type="button"
              className="reviewer-token-remove"
              aria-label={`Stop tracking @${login}`}
              title={`Stop tracking @${login}`}
              onClick={() => remove(login)}
            >
              &times;
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          className="reviewer-picker-input"
          autoComplete="off"
          spellCheck={false}
          autoCapitalize="off"
          maxLength={39}
          placeholder={reviewers.length === 0 ? "search github users\u2026" : "add\u2026"}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-expanded={showDropdown}
          aria-controls="reviewer-search-results"
        />
      </div>
      {showDropdown && (
        <ul
          className="reviewer-search-results"
          id="reviewer-search-results"
          role="listbox"
        >
          {results.length === 0 && search.isFetching ? (
            <li className="reviewer-search-empty">{"Searching\u2026"}</li>
          ) : (
            results.map((u) => (
              <li key={u.login} role="option" aria-selected="false">
                <button
                  type="button"
                  className="reviewer-search-option"
                  // Use onMouseDown so the click registers before the input
                  // blur closes the dropdown.
                  onMouseDown={(e) => {
                    e.preventDefault();
                    add(u.login);
                  }}
                >
                  {u.avatar_url && (
                    <img
                      className="reviewer-search-avatar"
                      src={u.avatar_url}
                      alt=""
                      width={20}
                      height={20}
                    />
                  )}
                  <span className="reviewer-search-login">@{u.login}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
