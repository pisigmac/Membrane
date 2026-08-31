export type Memory = {
  id: string;
  type: string;
  content: string;
  confidence: string;
  stability: string;
  provenance: string;
  state: string;
  scope: string | null;
  estimated_tokens: number;
  created_at?: string | null;
  last_accessed_at?: string | null;
  access_count: number;
  contradicted_by: string[];
  embedding?: number[] | null;
};

export type Me = {
  sub: string;
  email?: string | null;
  org_id?: string | null;
  workspace_id?: string | null;
  role: string;
  user_scope: string;
  via: string;
};

const TOKEN_KEY = "membrane_access_token";
const REFRESH_KEY = "membrane_refresh_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setTokens(access: string, refresh?: string) {
  localStorage.setItem(TOKEN_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

const AUTH_BASE = import.meta.env.VITE_AUTH_URL || "/auth-api";

export async function authFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${AUTH_BASE}${path}`, { ...init, headers });
  return res;
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path.startsWith("/api") ? path : `/api${path}`, { ...init, headers });
  if (res.status === 401) {
    clearTokens();
  }
  return res;
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}
