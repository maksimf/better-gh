import { useSyncExternalStore } from "react";

import { putPrefs } from "../api/queries";
import { readString, removeKey, writeString } from "./storage";

/**
 * Reactive, cross-device preference store.
 *
 * Each synced preference is mirrored at three layers: this in-memory
 * store (the reactive source of truth for the React tree), the browser's
 * localStorage (an instant-render, offline cache), and the server's
 * SQLite table (the cross-device source of truth). Values are kept as the
 * raw localStorage string so the existing parse/serialize helpers in
 * ``storage.ts`` keep working unchanged -- the store stays type-agnostic.
 *
 * Reads render immediately from the localStorage cache; ``hydrate`` later
 * folds in the server's copy (server wins) so another device's changes
 * appear on the next dashboard refetch. Writes update the cache and queue
 * a debounced ``PUT /api/prefs`` (last-write-wins).
 */

// The exhaustive set of keys this store syncs. Must match the backend's
// ALLOWED_KEYS whitelist in ``backend/app/prefs.py``.
export const SYNCED_KEYS = [
  "better-gh.manually-reviewed",
  "better-gh.watched",
  "better-gh.selected-repos",
  "better-gh.reviewer-login",
  "better-gh.theme",
  "better-gh.cloud-agents",
  "better-gh.ntfy-channel",
  "better-gh.pr-notes",
] as const;

const SYNCED = new Set<string>(SYNCED_KEYS);

// Raw localStorage string per key (null === absent). Seeded synchronously
// from the cache so the first paint matches what the user last saw.
const state = new Map<string, string | null>();
for (const key of SYNCED_KEYS) state.set(key, readString(key));

const listeners = new Set<() => void>();

function notify(): void {
  for (const fn of listeners) fn();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getRaw(key: string): string | null {
  return state.get(key) ?? null;
}

// --- debounced server push -------------------------------------------------

const PUSH_DEBOUNCE_MS = 400;
const pending = new Set<string>();
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function queuePush(key: string): void {
  if (!SYNCED.has(key)) return;
  pending.add(key);
  if (flushTimer !== null) clearTimeout(flushTimer);
  flushTimer = setTimeout(flush, PUSH_DEBOUNCE_MS);
}

function flush(): void {
  flushTimer = null;
  if (pending.size === 0) return;
  // null value signals a delete to the server (the row is dropped).
  const body: Record<string, string | null> = {};
  for (const key of pending) body[key] = getRaw(key);
  pending.clear();
  // Fire-and-forget: a failed sync just leaves the local cache ahead of
  // the server until the next write or refetch reconciles it.
  void putPrefs(body).catch(() => {
    /* offline / transient -- the next write retries */
  });
}

// --- public mutators -------------------------------------------------------

export function setRaw(key: string, value: string): void {
  if (getRaw(key) === value) return;
  state.set(key, value);
  writeString(key, value);
  notify();
  queuePush(key);
}

export function removeRaw(key: string): void {
  if (getRaw(key) === null) return;
  state.set(key, null);
  removeKey(key);
  notify();
  queuePush(key);
}

/**
 * Fold the server's copy into the store (called after GET /api/prefs).
 *
 * Server values win for keys it knows about. For synced keys the server
 * is missing but we have locally, push the local value up so an existing
 * device seeds the store on first sync (one-time migration of pre-sync
 * localStorage). Never re-pushes a value we just adopted from the server.
 */
export function hydrate(server: Record<string, unknown>): void {
  let changed = false;
  for (const key of SYNCED_KEYS) {
    if (key in server) {
      const raw = server[key];
      // Stored opaquely as strings; coerce defensively.
      const next = typeof raw === "string" ? raw : JSON.stringify(raw);
      if (getRaw(key) !== next) {
        state.set(key, next);
        writeString(key, next);
        changed = true;
      }
    } else if (getRaw(key) !== null) {
      // Local-only value: seed the server with it.
      queuePush(key);
    }
  }
  if (changed) notify();
}

// --- React bindings --------------------------------------------------------

/** Subscribe to one preference's raw string (null when unset). */
export function useRawPref(key: string): string | null {
  return useSyncExternalStore(
    subscribe,
    () => getRaw(key),
    () => getRaw(key),
  );
}

/** Non-reactive read, for imperative callers (e.g. the theme OS-follow). */
export function peekRaw(key: string): string | null {
  return getRaw(key);
}
