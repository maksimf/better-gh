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

// Pure parsers that operate on a raw string (e.g. one handed back by the
// preference store) rather than reading localStorage themselves. null in
// -> null out ("never set"); an unparseable value collapses to the empty
// shape so a corrupt cache degrades gracefully.

export function parseJsonArray(raw: string | null): string[] | null {
  if (raw === null) return null;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

export function parseJsonRecord(raw: string | null): Record<string, string> | null {
  if (raw === null) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const out: Record<string, string> = {};
      for (const [k, v] of Object.entries(parsed)) out[k] = String(v);
      return out;
    }
    return {};
  } catch {
    return {};
  }
}

export function readJsonArray(key: string): string[] | null {
  return parseJsonArray(readString(key));
}

export function writeJsonArray(key: string, value: string[]): void {
  writeString(key, JSON.stringify(value));
}

export function readJsonRecord(key: string): Record<string, string> | null {
  return parseJsonRecord(readString(key));
}

export function writeJsonRecord(
  key: string,
  value: Record<string, string>,
): void {
  writeString(key, JSON.stringify(value));
}
