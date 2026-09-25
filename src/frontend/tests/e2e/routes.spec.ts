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
  '/assistant',
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

test('assistant route shows the itinerary workspace and no-coordinate map state', async ({ page }) => {
  const response = await page.goto('/assistant');
  expect(response?.ok()).toBeTruthy();
  await expect(page.getByRole('heading', { name: 'Trợ lý du lịch AI' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Bản đồ lịch trình' }).first()).toContainText('tọa độ');
});

test('floating assistant widget opens and allows typing a request', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click({ force: true });
  await expect(page.getByPlaceholder('Nhập yêu cầu du lịch hoặc lịch trình...')).toBeVisible();
  await page.getByPlaceholder('Nhập yêu cầu du lịch hoặc lịch trình...').fill('Gợi ý chuyến đi Nha Trang');
  await page.getByRole('button', { name: 'Gửi yêu cầu' }).click();
  await expect(page.getByText('AI đang lập kế hoạch và tính toán lộ trình...').or(page.getByText('Làm rõ yêu cầu chuyến đi của bạn'))).toBeVisible();
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
  await expect(page.getByPlaceholder('Nhập yêu cầu du lịch hoặc lịch trình...')).toBeVisible();
  await page.getByPlaceholder('Nhập yêu cầu du lịch hoặc lịch trình...').fill('Gợi ý chuyến đi');
  await page.getByRole('button', { name: 'Gửi yêu cầu' }).click();
  await expect(page.getByText('Chưa tìm thấy kết quả phù hợp.').first()).toBeVisible();
  await expect(page.getByText('Phiên backend đang hoạt động').first()).toBeVisible();
});

test('clarification submits an intent override on the same backend conversation', async ({ page }) => {
  const payloads: Array<Record<string, unknown>> = [];
  await page.route('**/api/v1/assistant/itineraries/stream', async (route) => {
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    payloads.push(payload);
    const response = payload.intentOverride
      ? { status: 'NO_RESULTS', conversationId: 'clarification-session', message: 'Chưa tìm thấy lựa chọn phù hợp.', suggestions: [] }
      : {
          status: 'NEEDS_CLARIFICATION',
          conversationId: 'clarification-session',
          question: 'Bạn muốn đi trong bao nhiêu ngày?',
          missingFields: ['days'],
          suggestedValues: { days: [3] },
        };
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: `event: run.completed\ndata: ${JSON.stringify({ response })}\n\n`,
    });
  });

  await page.goto('/assistant');
  await page.getByLabel('Tin nhắn cho trợ lý').fill('Tôi muốn đi nghỉ dưỡng');
  await page.getByRole('button', { name: 'Gửi' }).click();
  await page.getByRole('button', { name: '3 ngày' }).click();
  await expect(page.getByText('Chưa tìm thấy lựa chọn phù hợp.').first()).toBeVisible();

  expect(payloads).toHaveLength(2);
  expect(payloads[0]).toMatchObject({ message: 'Tôi muốn đi nghỉ dưỡng', conversationId: null });
  expect(payloads[1]).toMatchObject({ message: null, conversationId: 'clarification-session', intentOverride: { days: 3 } });
});
