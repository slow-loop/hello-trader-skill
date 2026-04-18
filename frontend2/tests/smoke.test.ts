import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Trader/i);
});

test('navigation links work', async ({ page }) => {
    await page.goto('/');

    // Check for Portfolio link/content
    await page.click('nav a[title="Portfolio"]');
    await expect(page).toHaveURL(/.*portfolio/);

    // Check for Research link/content
    await page.click('nav a[title="Research"]');
    await expect(page).toHaveURL(/.*research/);
});

test('portfolio page loads data', async ({ page }) => {
    await page.goto('/portfolio');
    // Wait for the account value to be something other than "—"
    const av = page.locator('.text-xl.font-semibold', { hasText: /[\d,]+/ });
    await expect(av).toBeVisible({ timeout: 15000 });
});

test('trading desk loads chart', async ({ page }) => {
    await page.goto('/'); // TradingDesk is likely home
    // Use first() to avoid strict mode violation with multiple canvases
    await expect(page.locator('canvas').first()).toBeVisible({ timeout: 15000 });
});
