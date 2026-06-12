import { test, expect } from '@playwright/test';

test.describe('WhoseOnFirst Smoke Tests', () => {
  test('app loads', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('body')).toBeVisible();
  });
});
