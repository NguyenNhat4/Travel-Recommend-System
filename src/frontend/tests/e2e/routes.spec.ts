import { expect, test } from '@playwright/test';

const routes = [
  '/',
  '/search?q=khach-san&type=hotel',
  '/product/nt-hotel-01',
  '/cart',
  '/checkout',
  '/booking/VOTA-TEST',
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

test('floating assistant widget opens and allows typing a request', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click({ force: true });
  await expect(page.getByPlaceholder('Mô tả chuyến đi bạn mong muốn…')).toBeVisible();
  await page.getByPlaceholder('Mô tả chuyến đi bạn mong muốn…').fill('Gợi ý chuyến đi Nha Trang');
  await expect(page.getByRole('textbox', { name: 'Tin nhắn cho trợ lý du lịch AI' })).toHaveValue('Gợi ý chuyến đi Nha Trang');
  await expect(page.getByRole('button', { name: 'Gửi yêu cầu' })).toBeEnabled();
});

test('floating assistant drawer streams a backend result', async ({ page }) => {
  await page.route('**/api/v1/assistant/itineraries/stream', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'cache-control': 'no-cache' },
      body: [
        'event: run.started\ndata: {"runId":"e2e-run"}\n\n',
        'event: graph.topology\ndata: {"nodes":["search"]}\n\n',
        'event: node.completed\ndata: {"sequence":1,"nodeId":"search","outcome":"completed","message":"Tìm kiếm hoàn tất"}\n\n',
        'event: run.completed\ndata: {"response":{"status":"NO_RESULTS","conversationId":"e2e-conversation","message":"Chưa tìm thấy kết quả phù hợp.","suggestions":[]}}\n\n',
      ].join(''),
    });
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click({ force: true });
  await expect(page.getByPlaceholder('Mô tả chuyến đi bạn mong muốn…')).toBeVisible();
  await page.getByPlaceholder('Mô tả chuyến đi bạn mong muốn…').fill('Gợi ý chuyến đi');
  await page.getByRole('button', { name: 'Gửi yêu cầu' }).click();
  await expect(page.getByText('Chưa tìm thấy kết quả phù hợp.').first()).toBeVisible();
  await expect(page.getByText('Đang tiếp tục cuộc trò chuyện').first()).toBeVisible();
});
