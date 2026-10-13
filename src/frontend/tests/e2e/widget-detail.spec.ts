import { expect, test } from '@playwright/test';
import completed from '../../../shared/mocks/itinerary-agent/completed.json' with { type: 'json' };

const product = completed.itinerary.days[0].slots[0].product;

for (const width of [1024, 1440]) {
  test(`product detail keeps its actions visible and returns to the plan at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route('**/api/auth/session', (route) => route.fulfill({ json: { state: 'anonymous' } }));
    await page.route('**/api/v1/products?**', (route) => route.fulfill({ json: { results: [], total: 0, limit: 10, offset: 0 } }));
    await page.route(`**/api/v1/products/${product.productId}`, (route) => route.fulfill({ json: product }));
    await page.route('**/api/v1/destinations', (route) => route.fulfill({ json: { destinations: [] } }));
    await page.route('**/api/v1/assistant/itineraries/stream', (route) => route.fulfill({
      contentType: 'text/event-stream',
      body: `event: run.completed\ndata: ${JSON.stringify({ response: completed })}\n\n`,
    }));
    await page.route('**/*.tile.openstreetmap.org/**', (route) => route.abort());
    await page.route('**/router.project-osrm.org/**', (route) => route.abort());
    await page.goto('/');
    await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click();
    const dialog = page.getByRole('dialog', { name: 'Trợ lý du lịch AI' });
    await dialog.getByRole('textbox').fill('Lập lịch trình Phú Quốc 1 ngày');
    await dialog.getByRole('button', { name: 'Gửi yêu cầu' }).click();

    // Open the card with the keyboard, preserving the map beside the detail.
    const card = dialog.getByRole('button', { name: `Xem chi tiết ${product.name}` });
    await expect(card).toBeVisible();
    await card.focus();
    await card.press('Enter');
    const detail = dialog.getByRole('region', { name: 'Chi tiết sản phẩm' });
    await expect(detail.getByRole('heading', { name: product.name, exact: true })).toBeVisible();
    await expect(dialog.locator('.leaflet-container')).toBeVisible();
    const chatBounds = await dialog.getByRole('log').evaluate((element) => ({
      width: element.clientWidth, contentWidth: element.scrollWidth,
    }));
    expect(chatBounds.contentWidth).toBeLessThanOrEqual(chatBounds.width);
    const viewProduct = detail.getByRole('link', { name: 'Xem trang chi tiết' });
    await expect(viewProduct).toHaveAttribute('href', `/product/${product.productId}`);
    await expect(viewProduct).toBeInViewport();

    const mainImage = detail.getByRole('button', { name: /^Phóng to ảnh / }).getByRole('img');
    const galleryBefore = await mainImage.boundingBox();
    await detail.getByRole('button', { name: `Xem ảnh 2 của ${product.name}` }).click();
    const lightbox = detail.getByRole('dialog', { name: `Ảnh của ${product.name}` });
    await expect(lightbox).toBeVisible();
    await expect(lightbox.getByRole('img')).not.toHaveAttribute('src', product.imageUrl);
    await lightbox.press('Escape');
    await expect(lightbox).not.toBeVisible();
    await expect(detail).toBeVisible();
    await expect(mainImage).not.toHaveAttribute('src', product.imageUrl);
    const galleryAfter = await mainImage.boundingBox();
    expect(galleryAfter?.height).toBe(galleryBefore?.height);
    await detail.getByRole('button', { name: `Xem ảnh 1 của ${product.name}` }).click();
    await expect(lightbox).toBeVisible();
    await expect(lightbox.getByRole('img')).toHaveAttribute('src', product.imageUrl);
    await lightbox.getByRole('button', { name: 'Đóng ảnh phóng to' }).click();
    await expect(lightbox).not.toBeVisible();
    await expect(mainImage).toHaveAttribute('src', product.imageUrl);

    await detail.getByRole('button', { name: 'Xem thêm', exact: true }).click();
    await expect(detail.getByRole('button', { name: 'Thu gọn', exact: true })).toHaveAttribute('aria-expanded', 'true');
    await detail.getByText('Giờ mở cửa', { exact: true }).scrollIntoViewIfNeeded();
    await expect(viewProduct).toBeInViewport();
    const bounds = await detail.evaluate((element) => ({
      width: element.clientWidth,
      contentWidth: element.scrollWidth,
      right: element.getBoundingClientRect().right,
      viewport: window.innerWidth,
    }));
    expect(bounds.contentWidth).toBeLessThanOrEqual(bounds.width);
    expect(bounds.right).toBeLessThanOrEqual(bounds.viewport);
    await detail.getByRole('button', { name: 'Thu gọn', exact: true }).click();
    await detail.locator('.overflow-y-auto').evaluate((element) => { element.scrollTop = 0; });
    await expect(detail.locator('img').first()).toBeInViewport();
    await dialog.screenshot({ path: `/tmp/travel-widget-detail-${width}.png`, animations: 'disabled' });

    await page.keyboard.press('Escape');
    await expect(detail).toHaveCount(0);
    await expect(dialog.getByRole('heading', { name: completed.itinerary.title, exact: true, level: 2 })).toBeVisible();
    await expect(dialog.locator('.leaflet-container')).toBeVisible();
    await dialog.screenshot({ path: `/tmp/travel-widget-plan-${width}.png`, animations: 'disabled' });
    expect(errors).toEqual([]);
  });
}
