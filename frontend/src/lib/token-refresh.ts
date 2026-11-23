// SERVER-SIDE ONLY. Imported by src/auth.ts (NextAuth callbacks). Never import this from a
// client component: it holds the opaque backend refresh token flow.

export const API_BASE =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://backend:8000";

export interface RefreshedTokens {
  accessToken: string;
  /** Epoch milliseconds. */
  accessTokenExpires: number;
  /** The new (rotated) opaque refresh token. */
  refreshToken: string;
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

/** Decode the JWT `exp` claim (no signature check) and return epoch ms. */
export function jwtExpiresMs(jwt: string): number {
  const part = jwt.split(".")[1];
  if (!part) throw new Error("Malformed access token");
  const json = Buffer.from(part.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8");
  const exp = JSON.parse(json).exp;
  if (typeof exp !== "number") throw new Error("Access token has no exp claim");
  return exp * 1000;
}

/** Read the `refresh_token` value from a response's Set-Cookie headers. */
export function readRefreshCookie(res: Response): string | null {
  for (const line of res.headers.getSetCookie()) {
    const m = /^\s*refresh_token=([^;]*)/.exec(line);
    if (m) return m[1];
  }
  return null;
}

// Backend refresh tokens are STRICT single-use: presenting an already-rotated token is a 401.
// Several concurrent requests can carry the same old token (jwt callback runs per request),
// so share one in-flight call per old token, and keep the result for a short window so late
// requests still holding the old token get the new tokens instead of a reuse-401.
// NOTE: this Map is per Node process. Next standalone runs one process here; a multi-instance
// deploy needs a shared store (e.g. Redis) or a backend grace window instead.
const RESULT_TTL_MS = 60_000;
const flights = new Map<string, { promise: Promise<RefreshedTokens>; settledAt?: number }>();

export function _resetRefreshCacheForTests(): void {
  flights.clear();
}

async function callBackend(
  refreshToken: string,
  fetchImpl: FetchLike,
  baseUrl: string,
): Promise<RefreshedTokens> {
  const res = await fetchImpl(`${baseUrl}/auth/token/refresh`, {
    method: "POST",
    headers: { Cookie: `refresh_token=${refreshToken}` },
  });
  if (!res.ok) throw new Error(`Token refresh failed (${res.status})`);
  const data = await res.json();
  const newRefresh = readRefreshCookie(res);
  if (!data?.access_token || !newRefresh) throw new Error("Token refresh response incomplete");
  return {
    accessToken: data.access_token,
    accessTokenExpires: jwtExpiresMs(data.access_token),
    refreshToken: newRefresh,
  };
}

export function refreshBackendToken(
  refreshToken: string,
  fetchImpl: FetchLike = fetch,
  baseUrl: string = API_BASE,
): Promise<RefreshedTokens> {
  const now = Date.now();
  for (const [k, v] of flights) {
    if (v.settledAt !== undefined && now - v.settledAt > RESULT_TTL_MS) flights.delete(k);
  }
  const existing = flights.get(refreshToken);
  if (existing) return existing.promise;

  const entry: { promise: Promise<RefreshedTokens>; settledAt?: number } = {
    promise: callBackend(refreshToken, fetchImpl, baseUrl).then(
      (r) => {
        entry.settledAt = Date.now();
        return r;
      },
      (e) => {
        flights.delete(refreshToken); // do not cache failures
        throw e;
      },
    ),
  };
  flights.set(refreshToken, entry);
  return entry.promise;
}
