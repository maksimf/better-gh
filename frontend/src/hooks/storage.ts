// localStorage helpers that degrade gracefully in private mode (where
// reads/writes can throw). Mirrors the defensive try/catch the old
// inline scripts used.

export function readString(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeString(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode -- preference just won't persist */
  }
}

export function removeKey(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* private mode -- nothing to clear */
  }
}

export function readJsonArray(key: string): string[] | null {
  const raw = readString(key);
  if (raw === null) return null;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

export function writeJsonArray(key: string, value: string[]): void {
  writeString(key, JSON.stringify(value));
}
