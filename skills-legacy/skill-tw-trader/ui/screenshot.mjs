/**
 * screenshot.mjs — render a card component to PNG via Playwright
 *
 * Usage:
 *   node screenshot.mjs --url http://localhost:5173/research-card
 *   node screenshot.mjs --url http://localhost:5173/trading-card
 *   node screenshot.mjs --url http://localhost:5173/research-card [output_path]
 *
 * --url  Full URL of the card to screenshot (required).
 *        Available routes:
 *          /research-card   — 盤後研究卡
 *          /trading-card    — 交易決策卡
 *
 * Output defaults to data/publish/<today>/<card-name>.png derived from the URL path.
 * The dev server must already be running on the given host.
 */

import { chromium } from 'playwright';
import { mkdir } from 'fs/promises';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dir = dirname(fileURLToPath(import.meta.url));

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

async function main() {
  const args = process.argv.slice(2);

  const urlIdx = args.indexOf('--url');
  if (urlIdx < 0 || !args[urlIdx + 1]) {
    console.error('Error: --url <full-url> is required.');
    console.error('  e.g. node screenshot.mjs --url http://localhost:5173/research-card');
    process.exit(1);
  }
  const fullUrl = args[urlIdx + 1];

  // Derive a default filename from the URL path (e.g. /trading-card → trading-card.png)
  const routeName = new URL(fullUrl).pathname.replace(/^\//, '') || 'card';

  const outputArg = args.find(
    (a, i) => !a.startsWith('--') && i !== urlIdx + 1
  );
  const outputPath = outputArg
    ? resolve(outputArg)
    : resolve(__dir, '..', '..', '..', 'skills', 'tw-trader', 'data', 'publish', todayStr(), `${routeName}.png`);

  await mkdir(dirname(outputPath), { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.setViewportSize({ width: 1200, height: 800 });
  await page.goto(fullUrl, { waitUntil: 'networkidle' });

  const card = page.locator('.card-root');
  await card.waitFor();

  // Expand viewport to full card height so element screenshot isn't clipped
  const box = await card.boundingBox();
  if (box) {
    await page.setViewportSize({ width: 1200, height: Math.ceil(box.height) + 40 });
  }

  await card.screenshot({ path: outputPath });
  await browser.close();

  console.log(`saved → ${outputPath}`);
}

main().catch(e => { console.error(e); process.exit(1); });
