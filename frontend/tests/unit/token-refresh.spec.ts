// Node-only unit spec (no browser). Run: npm run test:unit
import { test, expect } from '@playwright/test';
import {
  refreshBackendToken,
  _resetRefreshCacheForTests,
} from '../../src/lib/token-refresh';

function b64url(o: object): string {
  return Buffer.from(JSON.stringify(o)).toString('base64url');
}
const EXP = Math.floor(Date.now() / 1000) + 900;
const JWT = `${b64url({ alg: 'HS256' })}.${b64url({ sub: 'u', exp: EXP })}.sig`;

function fakeFetch(status = 200) {
  let calls = 0;
  const impl = async (_url: string, init?: RequestInit) => {
    calls++;
    expect((init?.headers as Record<string, string>).Cookie).toBe('refresh_token=old-opaque');
    await new Promise((r) => setTimeout(r, 20));
    if (status !== 200) return new Response('{"detail":"nope"}', { status });
    return new Response(JSON.stringify({ access_token: JWT, is_admin: false }), {
      status: 200,
      headers: [
        ['content-type', 'application/json'],
        ['set-cookie', 'refresh_token=new-opaque; HttpOnly; Path=/auth'],
        ['set-cookie', `access_token=${JWT}; Path=/`],
      ],
    });
  };
  return { impl, calls: () => calls };
}

test.beforeEach(() => _resetRefreshCacheForTests());

test('parses new tokens from the backend response', async () => {
  const f = fakeFetch();
  const r = await refreshBackendToken('old-opaque', f.impl, 'http://b');
  expect(r.accessToken).toBe(JWT);
  expect(r.refreshToken).toBe('new-opaque');
  expect(r.accessTokenExpires).toBe(EXP * 1000);
});

test('5 concurrent calls share one backend call', async () => {
  const f = fakeFetch();
  const rs = await Promise.all(
    Array.from({ length: 5 }, () => refreshBackendToken('old-opaque', f.impl, 'http://b')),
  );
  expect(f.calls()).toBe(1);
  for (const r of rs) expect(r).toEqual(rs[0]);
});

test('late call with the old token reuses the cached result', async () => {
  const f = fakeFetch();
  const first = await refreshBackendToken('old-opaque', f.impl, 'http://b');
  const late = await refreshBackendToken('old-opaque', f.impl, 'http://b');
  expect(f.calls()).toBe(1);
  expect(late).toEqual(first);
});

test('backend 401 throws and is not cached', async () => {
  const f = fakeFetch(401);
  await expect(refreshBackendToken('old-opaque', f.impl, 'http://b')).rejects.toThrow(/401/);
  await expect(refreshBackendToken('old-opaque', f.impl, 'http://b')).rejects.toThrow(/401/);
  expect(f.calls()).toBe(2);
});
