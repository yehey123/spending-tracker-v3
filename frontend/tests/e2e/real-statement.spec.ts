/**
 * Real-statement OCR tests.
 *
 * - Tesseract (default CI): uses tesseract_fixture.png — a synthetic high-contrast PNG
 *   with pipe-delimited rows that Tesseract reliably parses. Always runs in CI.
 * - AI providers (anthropic / openai / gemini): uses statement_filled.png (committed public
 *   fixture) or private/statement.png (gitignored, preferred when USE_PRIVATE_STATEMENT=1).
 *   Set ANTHROPIC_API_KEY (etc.) to enable.
 */
import { test, expect, request } from '@playwright/test';
import { apiURL } from './fixtures';
import * as fs from 'fs';
import * as path from 'path';

const TESSERACT_FIXTURE = path.join(__dirname, 'fixtures', 'tesseract_fixture.png');
const PRIVATE_STATEMENT = path.join(__dirname, 'fixtures', 'private', 'statement.png');
const FILLED_STATEMENT  = path.join(__dirname, 'fixtures', 'statement_filled.png');
const AI_STATEMENT      = process.env.USE_PRIVATE_STATEMENT === '1' && fs.existsSync(PRIVATE_STATEMENT)
  ? PRIVATE_STATEMENT
  : FILLED_STATEMENT;

function chooseFixture(ocrProvider: string): string {
  return ocrProvider === 'tesseract' ? TESSERACT_FIXTURE : AI_STATEMENT;
}

// Collect statement IDs created across tests so the cleanup test can reverse their transactions
const createdStatementIds: number[] = [];

test.describe('real statement OCR pipeline', () => {
  test.afterEach(async () => {
    // Always reset staging flag regardless of test outcome
    const ctx = await request.newContext();
    await ctx.patch(`${apiURL()}/settings`, { data: { review_before_commit: false } });
    await ctx.dispose();
  });

  test('upload extracts transactions and lands on review page', async ({ page }) => {
    test.setTimeout(120000);

    const ctx = await request.newContext();
    const settingsResp = await ctx.get(`${apiURL()}/settings`);
    const { ocr_provider } = await settingsResp.json() as { ocr_provider: string };
    await ctx.patch(`${apiURL()}/settings`, { data: { review_before_commit: true } });
    await ctx.dispose();

    const fixture = chooseFixture(ocr_provider);
    await page.goto('/upload');
    await page.locator('input[type="file"]').setInputFiles(fixture);
    await page.getByRole('button', { name: 'Credit Card' }).click();
    await page.getByText(/upload & process/i).click();

    await expect(page).toHaveURL(/\/statements\/\d+\/review/, { timeout: 90000 });

    // Capture statement ID from URL for cleanup
    const match = page.url().match(/\/statements\/(\d+)\/review/);
    if (match) createdStatementIds.push(Number(match[1]));

    // Commit button reports how many transactions were extracted — must be > 0
    const commitBtn = page.getByRole('button', { name: /commit/i });
    await expect(commitBtn).toBeVisible();
    const label = await commitBtn.textContent() ?? '';
    const count = Number(label.match(/commit (\d+)/i)?.[1] ?? 0);
    expect(count, `OCR extracted ${count} transactions — expected > 0`).toBeGreaterThan(0);
  });

  test('commit imported statement adds transactions to ledger', async ({ page }) => {
    test.setTimeout(120000);

    // Upload via API directly (faster than UI — OCR still runs server-side)
    const ctx = await request.newContext();
    const settingsResp = await ctx.get(`${apiURL()}/settings`);
    const { ocr_provider } = await settingsResp.json() as { ocr_provider: string };
    await ctx.patch(`${apiURL()}/settings`, { data: { review_before_commit: true } });
    const fixture = chooseFixture(ocr_provider);
    const buffer = fs.readFileSync(fixture);
    const uploadResp = await ctx.post(`${apiURL()}/statements/upload`, {
      multipart: {
        file: { name: 'statement.png', mimeType: 'image/png', buffer },
        statement_kind: 'credit_card',
      },
    });
    const { id } = await uploadResp.json() as { id: number };
    await ctx.dispose();
    createdStatementIds.push(id);

    await page.goto(`/statements/${id}/review`);
    await expect(page.getByRole('heading', { name: /review statement/i })).toBeVisible();

    const commitBtn = page.getByRole('button', { name: /commit/i });
    await expect(commitBtn).toBeVisible();
    await commitBtn.click();

    // After commit, app navigates to /transactions and entries should be visible
    await expect(page).toHaveURL('/transactions', { timeout: 15000 });
    // At least one transaction row should exist
    await expect(page.locator('ul li').first()).toBeVisible();
  });

  test('cleanup — reverse all transactions from OCR-imported statements', async ({ page }) => {
    if (createdStatementIds.length === 0) return;

    const ctx = await request.newContext();
    const listResp = await ctx.get(`${apiURL()}/transactions?limit=200`);
    const transactions: Array<{ id: number; statement_id: number | null; status: string }> =
      await listResp.json();

    const toReverse = transactions.filter(
      (tx) => tx.statement_id !== null && createdStatementIds.includes(tx.statement_id),
    );

    if (toReverse.length > 0) {
      await ctx.post(`${apiURL()}/transactions/reverse`, {
        data: { ids: toReverse.map((tx) => tx.id), reason: 'user_error' },
      });
    }

    await ctx.dispose();
    await page.goto('/transactions');
  });
});
