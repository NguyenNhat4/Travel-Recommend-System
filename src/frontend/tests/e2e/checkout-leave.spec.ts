import { expect, test, type Page } from '@playwright/test';
import familyCart from '../../../shared/mocks/booking/getCart.200-family.json' with { type: 'json' };

/**
 * Hỏi lại trước khi rời trang thanh toán (FR-BKG-01, AC-BKG-20) trên trình duyệt thật: test đơn vị chạy trên jsdom không có router
 * của Next, nên nút Back (mục lịch sử chặn), `<Link>` ở chân trang và `router.push` được kiểm ở đây.
 */

/** Chặn API: phiên đã đăng nhập (trang giỏ mới cho vào /checkout) và giỏ gia đình của bộ mock dùng chung. */
async function mockApi(page: Page) {
  await page.route('**/api/auth/session', (route) => route.fulfill({
    json: {
      state: 'authenticated', csrfToken: 'x',
      user: { userId: 'u-1', cdpUserId: 'VP0000001', email: 'minhanh@example.vn', fullName: 'Nguyễn Minh Anh', phone: '0912345678' },
    },
  }));
  await page.route('**/api/v1/**', (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname.includes('/cart')) return route.fulfill({ json: familyCart });
    if (pathname.includes('/products/')) return route.fulfill({ json: { ...familyCart.items[0].product, attributes: {} } });
    return route.fulfill({ json: { results: [], total: 0, limit: 8, offset: 0 } });
  });
}

/** Vào /checkout bằng điều hướng trong ứng dụng (từ giỏ), để trang trước trong lịch sử là /cart. */
async function openCheckoutFromCart(page: Page) {
  await mockApi(page);
  await page.goto('/cart');
  await page.getByRole('button', { name: 'Tiến hành đặt chỗ' }).click();
  await expect(page).toHaveURL(/\/checkout/);
  await expect(page.getByRole('heading', { level: 2, name: 'Hành khách' })).toBeVisible();
}

const dialog = (page: Page) => page.getByRole('alertdialog');
const lastName = (page: Page) => page.getByLabel('Họ (Người lớn 2)');

/** Gõ như người dùng thật (bấm rồi gõ phím): trình duyệt chỉ cho chặn nút Back sau khi khách đã thao tác trên trang. */
async function typeLastName(page: Page) {
  await lastName(page).click();
  await lastName(page).pressSequentially('Trần');
}

test('logo và liên kết chân trang: hỏi lại, Ở lại giữ dữ liệu, Rời trang mới chuyển trang', async ({ page }) => {
  await openCheckoutFromCart(page);
  await typeLastName(page);

  await page.locator('header').getByText('V-OTA', { exact: true }).click();
  await expect(dialog(page)).toBeVisible();
  await expect(dialog(page)).toContainText('Rời trang thanh toán?');
  await expect(dialog(page)).toContainText('1 dịch vụ trong giỏ hàng vẫn được giữ nguyên');
  await expect(page.getByRole('button', { name: 'Ở lại thanh toán' })).toBeFocused();
  await expect(page).toHaveURL(/\/checkout/);

  await page.getByRole('button', { name: 'Ở lại thanh toán' }).click();
  await expect(dialog(page)).toBeHidden();
  await expect(lastName(page)).toHaveValue('Trần');

  // Đóng tab hoặc tải lại: trang yêu cầu trình duyệt hỏi lại.
  expect(await page.evaluate(() => {
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  })).toBe(true);

  await page.locator('footer a[href^="/"]').first().click();
  await expect(dialog(page)).toBeVisible();
  await expect(page).toHaveURL(/\/checkout/);
  await page.getByRole('button', { name: 'Rời trang' }).click();
  await expect(page).not.toHaveURL(/\/checkout/);
});

test('nút Back ở bước Hành khách: hỏi lại; Ở lại về lại trang với dữ liệu còn nguyên; Rời trang về trang trước', async ({ page }) => {
  await openCheckoutFromCart(page);
  await typeLastName(page);

  await page.goBack();
  await expect(dialog(page)).toBeVisible();
  await expect(page).toHaveURL(/\/checkout/);
  await expect(page.getByRole('heading', { level: 2, name: 'Hành khách' })).toBeVisible();

  await page.getByRole('button', { name: 'Ở lại thanh toán' }).click();
  await expect(dialog(page)).toBeHidden();
  await expect(lastName(page)).toHaveValue('Trần');

  await page.goBack();
  await expect(dialog(page)).toBeVisible();
  await page.getByRole('button', { name: 'Rời trang' }).click();
  await expect(page).toHaveURL(/\/cart$/);
  await expect(dialog(page)).toBeHidden();
});

test('nút Back giữa các bước chỉ lùi một bước, không hỏi; Back ở bước đầu mới hỏi', async ({ page }) => {
  await openCheckoutFromCart(page);
  await typeLastName(page);
  await page.getByLabel('Tên đệm và tên (Người lớn 2)').fill('Thu Hà');
  await page.getByLabel('Họ (Trẻ em 1)').fill('Nguyễn');
  await page.getByLabel('Tên đệm và tên (Trẻ em 1)').fill('Gia Bảo');
  await page.getByLabel('Ngày sinh (Trẻ em 1)').fill('12/05/2019');
  await page.locator('button:visible', { hasText: 'Tiếp tục' }).first().click();
  await expect(page).toHaveURL(/step=services/);

  await page.goBack();
  await expect(page.getByRole('heading', { level: 2, name: 'Hành khách' })).toBeVisible();
  await expect(dialog(page)).toBeHidden();
  await expect(lastName(page)).toHaveValue('Trần');

  await page.goBack();
  await expect(dialog(page)).toBeVisible();
  await expect(page).toHaveURL(/\/checkout/);
});

test('tải lại trang rồi bấm Back: vẫn chỉ một mục chặn, Rời trang về thẳng trang trước', async ({ page }) => {
  await openCheckoutFromCart(page);
  await typeLastName(page);
  // Tải lại là rời trang nên trình duyệt hỏi bằng hộp mặc định; đồng ý để tải lại.
  page.once('dialog', (browserDialog) => { void browserDialog.accept(); });
  await page.reload();
  await expect(page.getByRole('heading', { level: 2, name: 'Hành khách' })).toBeVisible();
  await typeLastName(page);

  await page.goBack();
  await expect(dialog(page)).toBeVisible();
  await page.getByRole('button', { name: 'Rời trang' }).click();
  await expect(page).toHaveURL(/\/cart$/);
});

test('điện thoại: hộp cảnh báo nằm sát đáy màn hình, hai nút xếp dọc', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 });
  await openCheckoutFromCart(page);
  await page.locator('header').getByText('V-OTA', { exact: true }).click();
  await expect(dialog(page)).toBeVisible();
  // Chờ hiệu ứng trượt lên xong rồi mới đo.
  await expect.poll(async () => {
    const box = await dialog(page).boundingBox();
    return box ? Math.round(box.y + box.height) : 0;
  }).toBe(800);
  const stay = await page.getByRole('button', { name: 'Ở lại thanh toán' }).boundingBox();
  const leave = await page.getByRole('button', { name: 'Rời trang' }).boundingBox();
  expect(stay!.y).toBeLessThan(leave!.y);
  expect(stay!.height).toBeGreaterThanOrEqual(44);
  expect(leave!.height).toBeGreaterThanOrEqual(44);
});
