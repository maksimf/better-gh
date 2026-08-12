import { useCallback, useEffect, useState } from "react";

import { removeRaw } from "./prefsStore";

const KEY = "better-gh.theme";

type Theme = "light" | "dark";

function osTheme(): Theme {
  return window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
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
 * Theme follows the OS (prefers-color-scheme). The toggle flips for this
 * session only; when the OS theme changes, we re-sync to it. Legacy
 * saved preferences (localStorage + synced prefs) are cleared so stuck
 * overrides don't linger.
 */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(osTheme);

  useEffect(() => {
    removeRaw(KEY);
  }, []);

  const applyTheme = useCallback((t: Theme) => {
    applyToDom(t);
    setTheme(t);
  }, []);

  const toggle = useCallback(() => {
    applyTheme(theme === "dark" ? "light" : "dark");
  }, [applyTheme, theme]);

  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme(osTheme());
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [applyTheme]);

  return { theme, toggle };
}
