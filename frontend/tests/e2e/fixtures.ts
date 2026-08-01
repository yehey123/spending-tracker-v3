import { request } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

export const AUTH_STATE_PATH = path.join(__dirname, '../playwright/.auth/user.json');
export const AUTH_TOKEN_PATH = path.join(__dirname, '../playwright/.auth/token.txt');

/** API base URL — always routes through nginx (BASE_URL/api).
 *  In CI: BASE_URL=http://127.0.0.1 (forces IPv4; Node.js resolves localhost to ::1 on Ubuntu 24)
 *  Locally: BASE_URL=http://localhost or unset — nginx on :80 proxies /api/ → backend:8000
 */
export function apiURL(): string {
  const base = process.env.BASE_URL ?? 'http://localhost';
  return `${base}/api`;
}

export async function authedApiContext() {
  const token = fs.readFileSync(AUTH_TOKEN_PATH, 'utf-8').trim();
  return request.newContext({
    extraHTTPHeaders: { Authorization: `Bearer ${token}` },
  });
}

export async function seedCategory(name: string, slug: string): Promise<void> {
  const ctx = await authedApiContext();
  await ctx.post(`${apiURL()}/categories`, {
    data: { name, slug, color: '#888888', icon: 'tag' },
  });
  await ctx.dispose();
}
