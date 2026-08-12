import { useCallback, useState } from "react";

/**
 * Transient error flag/message used by action buttons.
 * Clears automatically after `ms` (default 4000).
 */
export function useTransientError(ms = 4000) {
  const [error, setError] = useState<string | null>(null);

  const showError = useCallback(
    (message: string) => {
      setError(message);
      window.setTimeout(() => setError(null), ms);
    },
    [ms],
  );

  const clearError = useCallback(() => setError(null), []);

  return {
    error,
    showError,
    clearError,
    isError: error !== null,
  };
}

/** Boolean-only variant for chips / request-review CTAs. */
export function useTransientFlag(ms = 2400) {
  const [flag, setFlag] = useState(false);

  const show = useCallback(() => {
    setFlag(true);
    window.setTimeout(() => setFlag(false), ms);
  }, [ms]);

  const clear = useCallback(() => setFlag(false), []);

  return { flag, show, clear, isError: flag };
}
