// Thin fetch wrapper. A 401 anywhere means the signed session cookie
// expired or was revoked -- bounce to /login rather than leaving a
// half-broken tab showing stale data forever.

export class HttpError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(body || `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

function redirectToLogin(): never {
  window.location.href = "/login";
  // Throw so callers stop; the navigation will unload the page anyway.
  throw new HttpError(401, "unauthorized");
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(path, {
    credentials: "same-origin",
    ...init,
  });
  if (res.status === 401) redirectToLogin();
  return res;
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await request(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new HttpError(res.status, await res.text());
  return (await res.json()) as T;
}

export async function postJson<T = unknown>(
  path: string,
  body?: unknown,
): Promise<T | null> {
  const res = await request(path, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new HttpError(res.status, await res.text());
  // 204 (mutations) and empty bodies are common -- don't choke on them.
  if (res.status === 204) return null;
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : null;
}

export async function putJson<T = unknown>(
  path: string,
  body: unknown,
): Promise<T | null> {
  const res = await request(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new HttpError(res.status, await res.text());
  if (res.status === 204) return null;
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : null;
}
