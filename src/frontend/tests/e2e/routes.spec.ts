import { expect, test } from '@playwright/test';

const routes = [
  '/',
  '/search?q=khach-san&type=hotel',
  '/product/nt-hotel-01',
  '/cart',
  '/checkout',
  '/booking/VOTA-TEST',
  '/assistant',
  '/login',
  '/register',
];

test.describe('Next route smoke matrix', () => {
  for (const route of routes) {
    test(`direct load ${route}`, async ({ page }) => {
      const response = await page.goto(route);
      expect(response?.ok()).toBeTruthy();
      await expect(page.locator('.min-h-screen').first()).toBeVisible();
    });
  }
});

test('BFF forwards the API health contract', async ({ request }) => {
  const response = await request.get('/api/health');
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toMatchObject({
    status: 'ok',
    service: 'v-ota-recsys-demo',
  });
});
