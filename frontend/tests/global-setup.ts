import { chromium, request } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const AUTH_DIR = path.join(__dirname, 'playwright/.auth');
const STATE_PATH = path.join(AUTH_DIR, 'user.json');
const TOKEN_PATH = path.join(AUTH_DIR, 'token.txt');

const base = process.env.BASE_URL ?? 'http://localhost';
const apiBase = `${base}/api`;
const email = process.env.E2E_EMAIL ?? 'e2e@example.com';
const password = process.env.E2E_PASSWORD ?? 'e2epassword';

async function setup() {
  fs.mkdirSync(AUTH_DIR, { recursive: true });

  const apiCtx = await request.newContext();

  // 1. Register E2E user — invite_token is optional; first user bypasses gate.
  //    409 = already exists, ignore.
  await apiCtx.post(`${apiBase}/auth/register`, {
    data: { email, password },
  }).catch(() => {});

  // 2. Promote first user to admin — POST /admin/bootstrap takes NO body.
  //    409 = already bootstrapped, ignore.
  await apiCtx.post(`${apiBase}/admin/bootstrap`).catch(() => {});

  // 3. Get raw backend JWT (for authedApiContext helper in seeding calls)
  const loginRes = await apiCtx.post(`${apiBase}/auth/login`, {
    data: { email, password },
  });
  if (!loginRes.ok()) throw new Error(`Login failed: ${await loginRes.text()}`);
  const { access_token } = await loginRes.json();
  fs.writeFileSync(TOKEN_PATH, access_token, 'utf-8');

  // 4. Log in via browser to capture NextAuth + backend cookies (storageState)
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(`${base}/login`);
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL(/^(?!.*\/login)/);
  await page.context().storageState({ path: STATE_PATH });
  await browser.close();
  await apiCtx.dispose();
}

export default setup;
