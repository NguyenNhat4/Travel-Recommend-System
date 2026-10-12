import { expect, test } from '@playwright/test';
import completed from '../../../shared/mocks/itinerary-agent/completed.json' with { type: 'json' };

const openingPlaceholder = 'Mô tả chuyến đi bạn mong muốn…';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/session', (route) => route.fulfill({ json: { state: 'anonymous' } }));
  await page.route('**/api/v1/products?**', (route) => route.fulfill({ json: { results: [], total: 0, limit: 10, offset: 0 } }));
});

for (const width of [320, 768, 1024, 1440]) {
  test(`opening is usable at ${width}px without sending a request`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    let requests = 0;
    let destinationRequests = 0;
    await page.route('**/api/v1/assistant/itineraries/stream', async (route) => {
      requests += 1;
      await route.abort();
    });
    await page.route('**/api/v1/destinations', async (route) => {
      destinationRequests += 1;
      await route.fulfill({ json: { destinations: [{ destination: 'Hội An', productCount: 15 }] } });
    });
    await page.goto('/');
    // Home tự tải điểm đến khi khối "Bạn muốn đi đâu?" tới gần vùng nhìn; điều cần kiểm là việc mở widget không tải thêm.
    // Ở 768/1024 px khối này vào vùng nhìn trễ sau khi bố cục ổn định, nên cuộn tới khối để request của trang chủ xảy ra trước mốc đếm.
    await page.getByRole('heading', { name: 'Bạn muốn đi đâu?' }).scrollIntoViewIfNeeded();
    await expect.poll(() => destinationRequests).toBeGreaterThan(0);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForLoadState('networkidle');
    destinationRequests = 0;
    await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click();
    const dialog = page.getByRole('dialog', { name: 'Trợ lý du lịch AI' });
    const input = dialog.getByPlaceholder(openingPlaceholder);
    await expect(dialog.getByRole('heading', { name: 'Bạn muốn đi đâu tiếp theo?' })).toBeVisible();
    await expect(input).toBeFocused();
    await expect(dialog.getByRole('textbox')).toHaveCount(1);
    await expect(dialog.getByRole('button', { name: 'Gửi yêu cầu' })).toBeDisabled();
    await dialog.getByRole('button', { name: 'Nghỉ dưỡng', exact: true }).click();
    await expect(input).toHaveValue(/nghỉ dưỡng/);
    await expect(dialog.getByRole('button', { name: 'Gửi yêu cầu' })).toBeEnabled();
    expect(requests).toBe(0);
    expect(destinationRequests).toBe(0);
    await dialog.screenshot({ path: `/tmp/travel-ai-opening-${width}.png`, animations: 'disabled' });

    await dialog.getByRole('button', { name: 'Thêm thông tin chuyến đi' }).click();
    await expect(dialog.getByRole('button', { name: 'Hội An', exact: true })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Thêm thông tin chuyến đi' })).toHaveAttribute('aria-expanded', 'true');
    const geometry = await input.evaluate((element) => {
      const box = element.getBoundingClientRect();
      return { left: box.left, right: box.right, viewport: window.innerWidth };
    });
    expect(geometry.left).toBeGreaterThanOrEqual(0);
    expect(geometry.right).toBeLessThanOrEqual(geometry.viewport);
    await dialog.getByRole('button', { name: 'Thêm thông tin chuyến đi' }).click();
    await dialog.getByRole('button', { name: 'Mở rộng toàn màn hình' }).click();
    await expect(dialog.getByPlaceholder(openingPlaceholder)).toHaveValue(/nghỉ dưỡng/);
    await dialog.getByRole('button', { name: 'Đóng', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Mở trợ lý du lịch AI' })).toBeFocused();
    expect(requests).toBe(0);
    expect(errors).toEqual([]);
  });
}

test('keyboard submission switches to chat, preserves context, and resets to the opening', async ({ page }) => {
  const payloads: Array<Record<string, unknown>> = [];
  await page.route('**/api/v1/assistant/itineraries/stream', async (route) => {
    payloads.push(route.request().postDataJSON());
    const response = payloads.length === 1
      ? { status: 'NEEDS_CLARIFICATION', conversationId: 'opening-session', question: 'Bạn muốn đi ngày nào?', missingFields: ['startDate'] }
      : { status: 'NO_RESULTS', conversationId: 'opening-session', message: 'Chưa tìm thấy kết quả phù hợp.', suggestions: [] };
    await route.fulfill({ contentType: 'text/event-stream', body: `event: run.completed\ndata: ${JSON.stringify({ response })}\n\n` });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click();
  const dialog = page.getByRole('dialog', { name: 'Trợ lý du lịch AI' });
  const input = dialog.getByRole('textbox');
  await input.fill('Đi Hội An 3 ngày');
  await input.press('Shift+Enter');
  await expect(input).toHaveValue('Đi Hội An 3 ngày\n');
  expect(payloads).toHaveLength(0);
  await input.press('Enter');
  await expect(dialog.getByText('Bạn muốn đi ngày nào?')).toBeVisible();
  await expect(dialog.getByRole('textbox')).toHaveCount(1);
  await expect(dialog.getByRole('heading', { name: 'Bạn muốn đi đâu tiếp theo?' })).toHaveCount(0);
  await expect(dialog.getByRole('textbox')).toBeFocused();
  await dialog.getByRole('textbox').fill('Ngày 15/10, 2 người');
  await dialog.getByRole('button', { name: 'Gửi yêu cầu' }).click();
  await expect(dialog.getByText('Chưa tìm thấy kết quả phù hợp.')).toBeVisible();
  expect(payloads).toHaveLength(2);
  expect(payloads[0]).toMatchObject({ message: 'Đi Hội An 3 ngày', conversationId: null });
  expect(payloads[1]).toMatchObject({ message: 'Ngày 15/10, 2 người', conversationId: 'opening-session' });
  await dialog.getByRole('button', { name: 'Danh sách hội thoại & Tạo chat mới' }).click();
  await dialog.getByRole('button', { name: 'Đoạn chat mới' }).click();
  await expect(dialog.getByPlaceholder(openingPlaceholder)).toHaveValue('');
  await expect(dialog.getByRole('heading', { name: 'Bạn muốn đi đâu tiếp theo?' })).toBeVisible();
  await expect(dialog.getByRole('textbox')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(dialog.getByRole('button', { name: 'Đóng', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Mở trợ lý du lịch AI' })).toBeFocused();
});

test('completed results still open the timeline and map after the widget split', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/api/v1/assistant/itineraries/stream', async (route) => {
    await route.fulfill({ contentType: 'text/event-stream', body: `event: run.completed\ndata: ${JSON.stringify({ response: completed })}\n\n` });
  });
  await page.route('**/*.tile.openstreetmap.org/**', (route) => route.abort());
  await page.route('**/router.project-osrm.org/**', (route) => route.abort());
  await page.goto('/');
  await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click();
  await page.getByPlaceholder(openingPlaceholder).fill('Lập lịch trình Nha Trang 3 ngày');
  await page.getByRole('button', { name: 'Gửi yêu cầu' }).click();
  await page.getByRole('button', { name: 'Xem lộ trình & Bản đồ song song' }).click();
  const plan = page.getByRole('region', { name: 'Lịch trình theo ngày' });
  await expect(plan.getByRole('heading', { name: completed.itinerary.title, exact: true })).toBeVisible();
  await expect(plan.getByRole('button', { name: 'Tất cả', exact: true })).toBeVisible();
  await plan.getByRole('button', { name: 'Ngày 1', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Thanh toán tất cả', exact: true })).toHaveCount(0);
  await expect(page.getByRole('dialog', { name: 'Trợ lý du lịch AI' }).getByRole('textbox')).toHaveCount(1);
  expect(errors).toEqual([]);
});
