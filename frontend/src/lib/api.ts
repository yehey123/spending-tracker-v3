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

function getApiToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('spending_tracker_api_token');
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getApiToken();
  const { headers: initHeaders, ...restInit } = init ?? {};
  const isFormData = restInit.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
    ...(initHeaders as Record<string, string>),
    ...(token ? { 'X-API-Token': token } : {}),
  };
  const res = await fetch(`${getBaseUrl()}${path}`, { headers, ...restInit });
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
