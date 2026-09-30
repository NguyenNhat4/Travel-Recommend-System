import { expect, test, type Page } from '@playwright/test';

const product = (id: number) => ({
  productId: `p${id}`, name: `Sản phẩm ${id}`, taxonomy: 'hotel', destination: 'Nha Trang', unitPrice: 1000000 + id,
  currency: 'VND', priceUnit: 'PER_NIGHT', available: true, imageUrl: null, attributes: { level: 'property' },
});

/** Chặn API để đếm request: test không cần Backend. */
async function mockApi(page: Page) {
  const requests: string[] = [];
  await page.route('**/api/auth/session', (route) => route.fulfill({ json: { state: 'anonymous', csrfToken: 'x' } }));
  await page.route('**/api/v1/**', (route) => {
    const url = new URL(route.request().url());
    requests.push(url.pathname);
    if (url.pathname.endsWith('/destinations')) {
      return route.fulfill({ json: { destinations: [{ destination: 'Nha Trang', productCount: 12 }, { destination: 'Phú Quốc', productCount: 8 }] } });
    }
    return route.fulfill({ json: { results: [1, 2, 3, 4].map(product), total: 4, limit: 8, offset: 0 } });
  });
  return requests;
}

test('Home loads one catalog request up front and the rest only when scrolled to', async ({ page }) => {
  const requests = await mockApi(page);
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  expect(requests.filter((p) => p.endsWith('/products'))).toHaveLength(1);
  expect(requests.filter((p) => p.endsWith('/recommendations'))).toHaveLength(0);
  expect(requests.filter((p) => p.endsWith('/destinations'))).toHaveLength(0);

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect.poll(() => requests.filter((p) => p.endsWith('/destinations')).length).toBe(1);
});

test('header groups open by keyboard and lead to the category pages', async ({ page }) => {
  await mockApi(page);
  await page.goto('/');
  const stay = page.getByRole('button', { name: 'Lưu trú' });
  await stay.focus();
  await page.keyboard.press('Enter');
  await expect(stay).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(stay).toHaveAttribute('aria-expanded', 'false');

  await page.keyboard.press('Enter');
  await page.getByRole('group', { name: 'Lưu trú' }).getByRole('link', { name: /Khách sạn & resort/ }).click();
  await expect(page).toHaveURL(/\/hotels$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Khách sạn & resort' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Lưu trú' })).toHaveClass(/bg-white\/25|bg-slate-900/);

  for (const [group, item, path] of [
    ['Di chuyển', /Vé máy bay/, /\/flights$/],
    ['Tour và trải nghiệm', /Sân golf/, /\/experiences\?type=golf$/],
    ['Tiện ích khác', /Combo du lịch/, /\/combos$/],
  ] as const) {
    await page.getByRole('button', { name: group }).click();
    await page.getByRole('group', { name: group }).getByRole('link', { name: item }).click();
    await expect(page).toHaveURL(path);
  }
});

test('a header menu lists services only: no popular destinations, no API call, five services under "Tất cả dịch vụ"', async ({ page }) => {
  const requests = await mockApi(page);
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  const destinationCalls = () => requests.filter((p) => p.endsWith('/destinations')).length;
  const before = destinationCalls();

  await page.getByRole('button', { name: 'Lưu trú' }).click();
  const panel = page.getByRole('group', { name: 'Lưu trú' });
  await expect(panel.getByRole('link')).toHaveCount(1);
  await expect(panel.getByText('Điểm đến phổ biến')).toHaveCount(0);

  await page.getByRole('button', { name: 'Tất cả dịch vụ' }).click();
  await expect(page.getByRole('group', { name: 'Tất cả dịch vụ' }).getByRole('link')).toHaveCount(5);
  expect(destinationCalls()).toBe(before);
});

test('header controls share one 40px height and the header has no assistant entry', async ({ page }) => {
  await mockApi(page);
  await page.goto('/hotels');
  const header = page.locator('header');
  // `.all()` chụp DOM ngay lúc gọi và không chờ: đợi bốn nhóm cùng "Tất cả dịch vụ" có đủ, nếu không runner chậm thấy nav rỗng.
  const serviceButtons = header.getByRole('navigation', { name: 'Dịch vụ' }).getByRole('button');
  await expect(serviceButtons).toHaveCount(5);
  const controls = [
    ...(await serviceButtons.all()),
    header.getByTitle('Thay đổi ngôn ngữ và tiền tệ'),
    header.getByRole('button', { name: 'Đặt chỗ của tôi' }),
    header.getByRole('button', { name: 'Đăng nhập' }),
    header.getByRole('button', { name: 'Đăng ký' }),
  ];
  expect(controls).toHaveLength(9);
  for (const control of controls) {
    const box = await control.boundingBox();
    expect(box?.height).toBeGreaterThanOrEqual(39.5);
    expect(box?.height).toBeLessThanOrEqual(40.5);
  }
  await expect(header.getByRole('link', { name: /Trợ lý/ })).toHaveCount(0);
  await expect(header.getByText('Trợ lý AI')).toHaveCount(0);
});

test('the hotels search sheet goes to /search with the chosen destination, and /search shows no trip-context chip', async ({ page }) => {
  await mockApi(page);
  await page.goto('/hotels');
  await page.getByRole('combobox').click();
  await page.getByRole('option', { name: 'Nha Trang' }).click();
  await page.getByRole('button', { name: 'Tìm kiếm' }).click();

  await expect(page).toHaveURL(/\/search\?/);
  const url = new URL(page.url());
  expect(url.searchParams.get('type')).toBe('hotel');
  expect(url.searchParams.get('destination')).toBe('Nha Trang');
  expect(url.searchParams.get('adults')).toBe('2');
  expect(url.searchParams.get('checkIn')).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  // Spec frontend §4.1a/§4.2: /search chỉ nối ngữ cảnh chuyến đi vào liên kết sản phẩm, không hiện chip ngày/số khách; điểm đến là chip có ✕.
  await expect(page.getByRole('tab', { name: /^Lưu trú/ })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('button', { name: 'Bỏ lọc Nha Trang' })).toBeVisible();
  await expect(page.getByText(/Chuyến đi:/)).toHaveCount(0);
});

for (const path of ['/', '/hotels', '/flights', '/experiences', '/combos']) {
  test(`mobile 375px: ${path} has no horizontal page scroll and shows the category chips`, async ({ page }) => {
    await mockApi(page);
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await expect(page.getByRole('navigation', { name: 'Danh mục dịch vụ' })).toBeVisible();
  });
}
