import { useCallback, useEffect, useState } from "react";

import { peekRaw, setRaw, useRawPref } from "./prefsStore";

const KEY = "better-gh.theme";

type Theme = "light" | "dark";

function domTheme(): Theme {
  return document.documentElement.getAttribute("data-theme") === "dark"
    ? "dark"
    : "light";
}

function applyToDom(t: Theme): void {
  if (t === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

/**
 * Theme toggle. The pre-paint script in index.html's <head> applies the
 * saved / OS-preferred theme before first render (reading the same
 * localStorage cache the preference store keeps warm); this hook flips
 * and persists the user's choice (synced across devices), reflects a
 * choice synced in from another device, and follows OS changes while the
 * user hasn't made an explicit pick.
 */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const raw = useRawPref(KEY);
  const [theme, setTheme] = useState<Theme>(domTheme);

  // Reflect an explicit (persisted / cross-device synced) choice onto the
  // DOM + local state. Skips the null case so the OS preference stands.
  useEffect(() => {
    if (raw === "dark" || raw === "light") {
      applyToDom(raw);
      setTheme(raw);
    }
  }, [raw]);

  const toggle = useCallback(() => {
    const next: Theme = domTheme() === "dark" ? "light" : "dark";
    applyToDom(next);
    setTheme(next);
    setRaw(KEY, next);
  }, []);

  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => {
      // Only follow the OS if the user hasn't picked a theme.
      if (peekRaw(KEY)) return;
      applyToDom(e.matches ? "dark" : "light");
      setTheme(domTheme());
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return { theme, toggle };
}
