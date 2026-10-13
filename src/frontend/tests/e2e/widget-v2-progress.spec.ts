import { expect, test } from '@playwright/test';
import answer from '../../../shared/mocks/assistant-v2/answer.json' with { type: 'json' };

// The regular Next.js build defaults to v2; no environment override is required.
for (const width of [390, 1024]) {
  test(`@assistant-v2 v2 shows real decision rounds at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route('**/api/auth/session', (route) => route.fulfill({ json: { state: 'anonymous' } }));
    await page.route('**/api/v1/products?**', (route) => route.fulfill({ json: { results: [], total: 0 } }));
    const zero = { found: 0, eligible: 0, selected: 0, displayed: 0 };
    const base = { groupId: 'c1', kind: 'catalog', status: 'running', taxonomy: 'attraction', destination: 'Huế', counts: zero };
    const rows = [
      { event: 'start', data: { conversationId: answer.conversationId, clientTurnId: 't1', planRevision: 0 } },
      { event: 'activity', data: { ...base, groupId: 'think:1', kind: 'think', status: 'completed', taxonomy: null,
        explanation: 'Mình sẽ tra thêm điểm tham quan và đối chiếu những nơi đã giới thiệu.' } },
      { event: 'activity', data: base },
      { event: 'tool-completed', data: { ...base, status: 'completed', outcome: 'ok',
        counts: { found: 12, eligible: 8, selected: 0, displayed: 0 } } },
      { event: 'activity', data: { ...base, groupId: 'think:2', kind: 'think', status: 'completed', taxonomy: null,
        explanation: 'Đã có lựa chọn mới để giới thiệu, mình sẽ trả lời từ kết quả vừa tra.' } },
      { event: 'tool-completed', data: { ...base, status: 'completed', outcome: 'ok',
        counts: { found: 12, eligible: 8, selected: 1, displayed: 1 } } },
      { event: 'final', data: answer },
    ];
    await page.route('**/api/v2/assistant/itineraries/stream', (route) => route.fulfill({ contentType: 'text/event-stream',
      body: rows.map((row, index) => `event: ${row.event}\ndata: ${JSON.stringify({ ...row, runId: answer.runId, sequence: index + 1 })}\n\n`).join('') }));
    await page.goto('/');
    await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click();
    const dialog = page.getByRole('dialog', { name: 'Trợ lý du lịch AI' });
    await dialog.getByPlaceholder('Mô tả chuyến đi bạn mong muốn…').fill('Huế có gì chơi?');
    await dialog.getByRole('button', { name: 'Gửi yêu cầu' }).click();
    await dialog.getByRole('button', { name: /Xem các bước/ }).click();
    await expect(dialog.getByText('Mình sẽ tra thêm điểm tham quan và đối chiếu những nơi đã giới thiệu.')).toBeVisible();
    await expect(dialog.getByText('Đã có lựa chọn mới để giới thiệu, mình sẽ trả lời từ kết quả vừa tra.')).toBeVisible();
    await expect(dialog.getByText('Think', { exact: true })).toHaveCount(0);
    await expect(dialog.getByRole('listitem').filter({ hasText: 'Tìm điểm tham quan ở Huế' })).toHaveCount(1);
    await expect(dialog.getByText('8/12 kết quả phù hợp, chọn 1 để giới thiệu.')).toBeVisible();
    await expect(dialog.getByText('Hiểu yêu cầu', { exact: true })).toHaveCount(0);
    expect(await dialog.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(false);
    expect(errors).toEqual([]);
    await dialog.screenshot({ path: `/tmp/travel-v2-progress-${width}.png`, animations: 'disabled' });
  });
}
