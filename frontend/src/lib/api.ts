export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const CSRF_STORAGE_KEY = "baf.csrf";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split("; ")) {
    if (part.startsWith(prefix)) return decodeURIComponent(part.slice(prefix.length));
  }
  return null;
}

export function storeCsrfToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(CSRF_STORAGE_KEY, token);
  } catch { /* storage unavailable */ }
}

export function clearCsrfToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(CSRF_STORAGE_KEY);
  } catch { /* storage unavailable */ }
}

function csrfToken(): string | null {
  const fromCookie = readCookie("baf_csrf");
  if (fromCookie) return fromCookie;
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(CSRF_STORAGE_KEY);
  } catch {
    return null;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  let resp: Response;
  const method = (init?.method ?? "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!SAFE_METHODS.has(method)) {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", token);
  }
  try {
    resp = await fetch(`${API_URL}${path}`, {
      ...init,
      method,
      signal,
      credentials: "include",
      headers,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(
      0,
      "No se pudo conectar con el backend. Verifica que esté corriendo en " + API_URL
    );
  }
  if (!resp.ok) {
    if (resp.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("baf:unauthorized"));
    }
    let detail = `Error HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* ignore */ }
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}

export function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) }, signal);
}

export function patch<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return apiFetch<T>(path, { method: "PATCH", body: JSON.stringify(body) }, signal);
}
