function getBaseUrl(): string {
  // Build-time env var (set by Docker --build-arg, default /api for production)
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  // Dev/mobile override via localStorage (Story 4.1 — Capacitor builds)
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('spending_tracker_backend_url');
    if (stored) return stored;
  }
  // Fallback: same-origin /api (nginx gateway)
  return '/api';
}

async function getCapacitorTokenIfNative(): Promise<string | null> {
  try {
    // Dynamic import — avoids bundling Capacitor modules in web builds
    const { Capacitor } = await import('@capacitor/core');
    if (!Capacitor.isNativePlatform()) return null;
    const { getCapacitorToken } = await import('./capacitor-auth');
    return getCapacitorToken();
  } catch {
    return null;
  }
}

// Browser (non-native) token: NextAuth session accessToken, cached briefly so
// each request does not hit /api/auth/session.
const SESSION_TOKEN_TTL_MS = 45_000;
let sessionTokenCache: { promise: Promise<string | null>; expires: number } | null = null;

export function clearSessionTokenCache(): void {
  sessionTokenCache = null;
}

function jwtExpMs(jwt: string): number | null {
  try {
    const part = jwt.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const exp = JSON.parse(atob(part)).exp;
    return typeof exp === 'number' ? exp * 1000 : null;
  } catch {
    return null;
  }
}

async function getSessionToken(): Promise<string | null> {
  if (typeof window === 'undefined') return null;
  const now = Date.now();
  if (sessionTokenCache && sessionTokenCache.expires > now) return sessionTokenCache.promise;
  const entry = { promise: null as unknown as Promise<string | null>, expires: now + SESSION_TOKEN_TTL_MS };
  entry.promise = (async () => {
    try {
      const { getSession, signOut } = await import('next-auth/react');
      const session = await getSession();
      if (session?.error === 'RefreshTokenError') {
        // Backend refresh failed (expired/revoked session): back to login.
        sessionTokenCache = null;
        void signOut({ callbackUrl: '/login' });
        return null;
      }
      const token = session?.accessToken ?? null;
      // The server refreshes tokens within 60 s of expiry, so a fresh token has >= 60 s left;
      // cap the cache at the token's own exp (minus 10 s) so a cached token never outlives it.
      const exp = token ? jwtExpMs(token) : null;
      if (exp) {
        entry.expires = Date.now() + Math.max(0, Math.min(SESSION_TOKEN_TTL_MS, exp - Date.now() - 10_000));
      }
      return token;
    } catch {
      return null;
    }
  })();
  sessionTokenCache = entry;
  return entry.promise;
}

async function getAuthToken(): Promise<string | null> {
  const nativeToken = await getCapacitorTokenIfNative();
  if (nativeToken) return nativeToken;
  return getSessionToken();
}

/** Authenticated fetch against the backend: attaches Bearer, retries once on 401. */
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { headers: initHeaders, ...restInit } = init;
  const send = async () => {
    const token = await getAuthToken();
    return fetch(`${getBaseUrl()}${path}`, {
      credentials: 'include',
      ...restInit,
      headers: {
        ...(initHeaders as Record<string, string>),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  };
  let res = await send();
  if (res.status === 401) {
    clearSessionTokenCache();
    res = await send();
  }
  return res;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { headers: initHeaders, ...restInit } = init ?? {};
  const isFormData = restInit.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
    ...(initHeaders as Record<string, string>),
  };
  const res = await authFetch(path, { ...restInit, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail ?? res.statusText), { status: res.status });
  }
  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return undefined as T;
  }
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: (path: string) => request<void>(path, { method: 'DELETE' }),
  upload: <T>(path: string, form: FormData) =>
    request<T>(path, { method: 'POST', body: form, headers: {} }),
};
