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

test('itinerary map renders OSRM geometry with intermediate route vertices', async ({ page }) => {
  await page.route(/https:\/\/routing\.openstreetmap\.de\/routed-(car|foot|bike)\/route\/v1\/driving\/.*/, async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        code: 'Ok',
        routes: [{
          distance: 2400,
          duration: 600,
          geometry: {
            coordinates: [[109.2, 12.2], [109.205, 12.202], [109.21, 12.21]],
            type: 'LineString',
          },
        }],
      }),
    });
  });

  await page.goto('/assistant');
  await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click();
  await page.getByRole('button', { name: 'Mở rộng toàn màn hình' }).click();
  await page.getByRole('button', { name: /Lịch trình Đà Lạt 7 ngày/ }).click();

  const routePath = page.locator('.leaflet-overlay-pane svg path').first();
  await expect(routePath).toBeVisible({ timeout: 10_000 });
  const pathData = await routePath.getAttribute('d');
  expect(pathData).toBeTruthy();
  expect((pathData?.match(/L/g) ?? []).length).toBeGreaterThanOrEqual(2);
  await expect(page.getByText('Một số chặng chưa có geometry từ OSRM.')).toHaveCount(0);
});
