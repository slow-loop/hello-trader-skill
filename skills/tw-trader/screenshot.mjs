/**
 * screenshot.mjs — render ResearchCard to poster.png via Playwright
 *
 * Usage:
 *   node screenshot.mjs [output_path] [--url http://localhost:5173]
 *
 * The dev server must already be running (or use --url to point elsewhere).
 * Output defaults to skills/tw-trader/data/publish/<today>/poster.png
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
  const baseUrl = urlIdx >= 0 ? args[urlIdx + 1] : 'http://localhost:5173';

  const outputArg = args.find(a => !a.startsWith('--') && (urlIdx < 0 || args.indexOf(a) !== urlIdx + 1));
  const outputPath = outputArg
    ? resolve(outputArg)
    : resolve(__dir, 'data', 'publish', todayStr(), 'poster.png');

  await mkdir(dirname(outputPath), { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.setViewportSize({ width: 1200, height: 800 });
  await page.goto(`${baseUrl}/card`, { waitUntil: 'networkidle' });

  const card = page.locator('.card-root');
  await card.waitFor();

  // Expand viewport to full card height so element screenshot isn't clipped
  const box = await card.boundingBox();
  if (box) {
    await page.setViewportSize({ width: 1200, height: Math.ceil(box.height) + 40 });
  }

  await card.screenshot({ path: outputPath });
  await browser.close();

  console.log(`poster saved → ${outputPath}`);
}

main().catch(e => { console.error(e); process.exit(1); });
