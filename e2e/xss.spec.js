import { test, expect } from '@playwright/test';

// WOF-18: stored-XSS regression test for the team-members page.
// Seeds members whose names carry XSS payloads, then asserts the page
// renders them inert and the toggle action still resolves the right member.

const API = 'http://localhost:8000/api/v1';
const PAYLOAD_QUOTE = "\\'-alert(1)-\\'";
const PAYLOAD_IMG = '<img src=x onerror=window.__xss=1>';

async function login(request) {
  const res = await request.post(`${API}/auth/login`, {
    data: { username: 'admin', password: 'Admin123!', remember_me: false },
  });
  expect(res.ok()).toBeTruthy();
  return res;
}

async function createMember(request, name, phone) {
  const res = await request.post(`${API}/team-members/`, {
    data: { name, phone },
  });
  expect(res.status()).toBe(201);
  return (await res.json()).id;
}

test.describe('WOF-18 XSS hardening', () => {
  const created = [];

  test.afterAll(async ({ request }) => {
    await login(request);
    for (const id of created) {
      await request.delete(`${API}/team-members/${id}/permanent`);
    }
  });

  test('member names with XSS payloads render inert', async ({ page, request }) => {
    await login(request);
    created.push(await createMember(request, PAYLOAD_QUOTE, '+12125550199'));
    created.push(await createMember(request, PAYLOAD_IMG, '+12125550198'));

    let sawDialog = false;
    let confirmText = null;
    page.on('dialog', async (dialog) => {
      if (dialog.type() === 'confirm') {
        confirmText = dialog.message();
        await dialog.dismiss();
      } else {
        sawDialog = true; // alert() fired -> payload executed
        await dialog.dismiss();
      }
    });

    // Login through the UI so the page session cookie is set
    await page.goto('/login.html');
    await page.fill('input[name="username"], #username', 'admin');
    await page.fill('input[name="password"], #password', 'Admin123!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/index\.html|\/$/);

    await page.goto('/team-members.html');
    await page.waitForSelector('#membersContainer .member-row');

    // Both payload names must appear as literal text
    await expect(page.getByText(PAYLOAD_QUOTE)).toBeVisible();
    await expect(page.getByText(PAYLOAD_IMG)).toBeVisible();

    // The onerror payload must not have executed
    expect(await page.evaluate(() => window.__xss)).toBeUndefined();
    expect(sawDialog).toBe(false);

    // Toggle on the quote-payload member: confirm dialog proves the
    // delegated handler resolved the member without JS-string breakout
    const row = page.locator('.member-row', { hasText: PAYLOAD_QUOTE });
    await row.locator('button[data-action="toggle-active"]').click();
    await page.waitForTimeout(250);
    expect(confirmText).toContain('deactivate');
    expect(sawDialog).toBe(false);
  });
});
