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

test('clarification is a plain assistant message and the answer continues the same backend conversation', async ({ page }) => {
  const payloads: Array<Record<string, unknown>> = [];
  await page.route('**/api/v1/assistant/itineraries/stream', async (route) => {
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    payloads.push(payload);
    const response = payloads.length > 1
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
  // Câu hỏi làm rõ chỉ hiện một lần, dạng tin nhắn thường (không có card/nút gợi ý riêng).
  await expect(page.getByText('Bạn muốn đi trong bao nhiêu ngày?')).toHaveCount(1);
  await expect(page.getByRole('button', { name: '3 ngày' })).toHaveCount(0);

  await page.getByLabel('Tin nhắn cho trợ lý').fill('3 ngày');
  await page.getByRole('button', { name: 'Gửi' }).click();
  await expect(page.getByText('Chưa tìm thấy lựa chọn phù hợp.').first()).toBeVisible();

  expect(payloads).toHaveLength(2);
  expect(payloads[0]).toMatchObject({ message: 'Tôi muốn đi nghỉ dưỡng', conversationId: null });
  expect(payloads[1]).toMatchObject({ message: '3 ngày', conversationId: 'clarification-session', intentOverride: null });
});
