import { expect, test } from '@playwright/test';

test('live FastAPI assistant returns a completed itinerary in FloatingWidget and shares it with HeaderDrawer', async ({ page }) => {
  test.skip(process.env.RUN_ASSISTANT_LIVE_E2E !== '1', 'Set RUN_ASSISTANT_LIVE_E2E=1 with FastAPI running to execute the live assistant acceptance flow.');

  await page.goto('/');
  await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click();
  const responsePromise = page.waitForResponse((response) => response.url().includes('/api/v1/assistant/itineraries/stream'));
  await page.getByLabel('Tin nhắn cho trợ lý').fill('Lên lịch trình du lịch 2 ngày ở Nha Trang.');
  await page.getByRole('button', { name: 'Gửi' }).click();
  const streamResponse = await responsePromise;
  expect(streamResponse.status()).toBe(200);
  expect(streamResponse.headers()['content-type']).toContain('text/event-stream');
  const body = await streamResponse.text();
  expect(body).toMatch(/event: run\.completed/);
  expect(body).not.toMatch(/event: run\.failed/);
  const completedFrame = body.split(/\r?\n\r?\n/).find((frame) => frame.startsWith('event: run.completed'));
  expect(completedFrame).toBeTruthy();
  const eventData = completedFrame?.split(/\r?\n/).find((line) => line.startsWith('data: '))?.slice(6);
  expect(eventData).toBeTruthy();
  const envelope = JSON.parse(eventData || '{}') as { response?: { status?: string; itinerary?: { title?: string; stay?: { product?: { productId?: string; name?: string } }; days?: Array<{ slots?: Array<{ product?: { productId?: string; name?: string } | null }> }> } } };
  expect(envelope.response?.status).toBe('COMPLETED');
  expect(envelope.response?.itinerary?.days?.length).toBeGreaterThan(0);
  const productIds = envelope.response?.itinerary?.days?.flatMap((day) => day.slots ?? []).flatMap((slot) => slot.product?.productId ? [slot.product.productId] : []) ?? [];
  const productNames = envelope.response?.itinerary?.days?.flatMap((day) => day.slots ?? []).flatMap((slot) => slot.product?.name ? [slot.product.name] : []) ?? [];
  if (envelope.response?.itinerary?.stay?.product?.productId) productIds.push(envelope.response.itinerary.stay.product.productId);
  if (envelope.response?.itinerary?.stay?.product?.name) productNames.push(envelope.response.itinerary.stay.product.name);
  expect(productIds.length).toBeGreaterThan(0);
  expect(productIds.every((productId) => typeof productId === 'string' && productId.length > 0)).toBe(true);
  const visibleItineraryText = envelope.response?.itinerary?.title || productNames[0];
  expect(visibleItineraryText).toBeTruthy();
  await expect(page.getByText(visibleItineraryText!, { exact: false }).first()).toBeVisible({ timeout: 120_000 });

  await page.locator('#aiAssistantBtn').click();
  await expect(page.getByText(visibleItineraryText!, { exact: false }).last()).toBeVisible();
});
