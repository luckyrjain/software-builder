import { test, expect } from '@playwright/test';

test('home page has a title', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Home/);
});
