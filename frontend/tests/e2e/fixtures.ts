import { request } from '@playwright/test';

/** API base URL — always routes through nginx (BASE_URL/api).
 *  In CI: BASE_URL=http://127.0.0.1 (forces IPv4; Node.js resolves localhost to ::1 on Ubuntu 24)
 *  Locally: BASE_URL=http://localhost or unset — nginx on :80 proxies /api/ → backend:8000
 */
export function apiURL(): string {
  const base = process.env.BASE_URL ?? 'http://localhost';
  return `${base}/api`;
}

export async function seedCategory(name: string, slug: string): Promise<void> {
  const ctx = await request.newContext();
  await ctx.post(`${apiURL()}/categories`, {
    data: { name, slug, color: '#888888', icon: 'tag' },
  });
  await ctx.dispose();
}
