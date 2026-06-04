import { useCallback, useEffect, useState } from "react";

import { readString, writeString } from "./storage";

const KEY = "better-gh.theme";

type Theme = "light" | "dark";

function currentTheme(): Theme {
  return document.documentElement.getAttribute("data-theme") === "dark"
    ? "dark"
    : "light";
}

function applyTheme(t: Theme): void {
  if (t === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
  writeString(KEY, t);
}

/**
 * Theme toggle. The pre-paint script in index.html's <head> applies the
 * saved / OS-preferred theme before first render; this hook just flips
 * and persists the user's choice, and follows OS changes while the user
 * hasn't made an explicit pick.
 */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(currentTheme);

  const toggle = useCallback(() => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  }, []);

  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => {
      // Only follow the OS if the user hasn't picked a theme.
      if (readString(KEY)) return;
      if (e.matches) {
        document.documentElement.setAttribute("data-theme", "dark");
      } else {
        document.documentElement.removeAttribute("data-theme");
      }
      setTheme(currentTheme());
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return { theme, toggle };
}
