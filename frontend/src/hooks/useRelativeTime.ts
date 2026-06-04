import { useEffect, useState } from "react";

/**
 * Re-render on a fixed interval so relative-time labels stay fresh
 * without a server round-trip. Returns the current epoch millis.
 */
export function useNow(intervalMs = 60_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

/** "just now" / "5 mins ago" / "2 hours ago" / "3 days ago". */
export function formatRelative(iso: string, now: number): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 30) return "just now";
  if (seconds < 90) return "1 min ago";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} mins ago`;
  const hours = Math.round(minutes / 60);
  if (hours === 1) return "1 hour ago";
  if (hours < 24) return `${hours} hours ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

function localTime(d: Date): string {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** "in 5 mins (at 14:32)" countdown used by the rate-limit error banner. */
export function formatUntil(iso: string, now: number): string {
  const then = new Date(iso);
  const t = then.getTime();
  if (Number.isNaN(t)) return "";
  const seconds = Math.round((t - now) / 1000);
  if (seconds <= 0) return `now (at ${localTime(then)})`;
  if (seconds < 60) return `in <1 min (at ${localTime(then)})`;
  const minutes = Math.round(seconds / 60);
  if (minutes === 1) return `in 1 min (at ${localTime(then)})`;
  if (minutes < 60) return `in ${minutes} mins (at ${localTime(then)})`;
  const hours = Math.round(minutes / 60);
  if (hours === 1) return `in 1 hour (at ${localTime(then)})`;
  return `in ${hours} hours (at ${localTime(then)})`;
}
