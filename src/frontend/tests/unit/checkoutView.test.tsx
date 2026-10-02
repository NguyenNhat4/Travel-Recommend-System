// @vitest-environment jsdom
import React, { useMemo, useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import familyDraft from '../../../shared/mocks/booking/getBookingDraft.200-family.json';
import familyCart from '../../../shared/mocks/booking/getCart.200-family.json';
import draftExpired from '../../../shared/mocks/booking/createBooking.410-draft-expired.json';
import draftExpiredOnLoad from '../../../shared/mocks/booking/getBookingDraft.410-expired.json';
import draftNotFound from '../../../shared/mocks/booking/getBookingDraft.404-not-found.json';
import createdFamily from '../../../shared/mocks/booking/createBooking.201-family.json';
import partyInvalid from '../../../shared/mocks/booking/createBooking.400-party-invalid.json';
import priceChangedChild from '../../../shared/mocks/booking/createBooking.409-price-changed-child.json';
import pendingError from '../../../shared/mocks/booking/createBooking.409-pending-payment.json';
import providerDown from '../../../shared/mocks/booking/createBooking.503-payment-unavailable.json';
import { estimateFares } from '../../src/components/checkout/fareEstimate';

const api = vi.hoisted(() => ({
  createBooking: vi.fn(),
  getBooking: vi.fn(),
  cancelBooking: vi.fn(),
  removeCartItem: vi.fn(),
  getBookingDraft: vi.fn(),
  updateBookingDraftItem: vi.fn(),
  removeBookingDraftItem: vi.fn(),
  redirectToCheckout: vi.fn(),
}));
const shared = vi.hoisted(() => ({
  Ctx: (require('react') as typeof import('react')).createContext<any>(null),
  navigate: vi.fn(),
  rememberBooking: vi.fn(),
  showToast: vi.fn(),
  openLoginModal: vi.fn(),
  updateCartItem: vi.fn(),
  refreshCart: vi.fn(),
  /** Độ trễ giả lập của PATCH (ms), để dựng "request đang bay". */
  patchDelay: 0,
}));

vi.mock('../../src/services/booking', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/booking')>()),
  ...api,
}));
// Trang đọc `?draft=` bằng useSearchParams của Next; trong test, URL nằm ở window.location.
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(window.location.search) }));
vi.mock('../../src/services/catalog', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/catalog')>()),
  getProduct: vi.fn().mockResolvedValue({ attributes: { policies: { 'Quy định': 'Trẻ em dưới 100 cm miễn phí.' } } }),
}));
vi.mock('../../src/context/TravelContext', async () => {
  const React = await import('react');
  return { useTravel: () => React.useContext(shared.Ctx) };
});

import { CheckoutView } from '../../src/components/checkout/CheckoutView';
import { ApiError } from '../../src/services/http';

const CHILD_PRICES: Record<string, number> = { 'nt-a-vinwonders-buggy': 504000 };

/** Giả lập `PATCH` một mục của đơn nháp hoặc giỏ: ghi số khách và tính lại dòng giá như Backend (chỉ để test giao diện, không phải nguồn giá thật). */
function applyPatch(cart: any, id: string, body: any) {
  const items = cart.items.map((item: any) => {
    if (item.cartItemId !== id) return item;
    const taxonomy = item.product.taxonomy;
    const guests = body.guests ?? item.guests;
    const quantity = body.quantity ?? item.quantity;
    const { lines, total } = estimateFares({
      taxonomy, unitPrice: item.product.unitPrice, attributes: { childPrice: CHILD_PRICES[item.product.productId] },
      quantity, nights: item.nights, adults: guests.adults, children: guests.children,
    });
    return { ...item, guests, quantity, fares: lines, lineTotal: total };
  });
  const total = items.reduce((s: number, i: any) => s + i.lineTotal, 0);
  return { ...cart, items, subtotal: total, total };
}

const DRAFT_ID = familyDraft.draftId;
/** Đơn nháp phía "Backend" của test: GET, PATCH, DELETE của đơn nháp đọc và ghi vào đây. */
const store: { draft: any } = { draft: null };

function mockDraftApi() {
  api.getBookingDraft.mockImplementation(async () => store.draft);
  api.updateBookingDraftItem.mockImplementation(async (_draftId: string, id: string, body: any) => {
    shared.updateCartItem(id, body);
    if (shared.patchDelay) await new Promise((resolve) => setTimeout(resolve, shared.patchDelay));
    store.draft = applyPatch(store.draft, id, body);
    return store.draft;
  });
  api.removeBookingDraftItem.mockImplementation(async (_draftId: string, id: string) => {
    const items = store.draft.items.filter((item: any) => item.cartItemId !== id);
    const total = items.reduce((s: number, i: any) => s + i.lineTotal, 0);
    store.draft = { ...store.draft, items, itemCount: items.length, subtotal: total, total };
    return store.draft;
  });
}

/**
 * Trang thanh toán với context giả. Mặc định là nguồn đơn nháp (`?draft=`, dữ liệu ở `store.draft`); truyền `cart` và mở
 * `/checkout` không có `draft` thì là nguồn giỏ. `signedIn = false` là khách chưa đăng nhập.
 */
function Harness({ accountName = 'Nguyễn Minh Anh', cart = null, signedIn = true }: { accountName?: string; cart?: any; signedIn?: boolean }) {
  const [cartState, setCart] = useState(cart);
  const cartRef = React.useRef(cartState);
  React.useEffect(() => { cartRef.current = cartState; }, [cartState]);
  const value = useMemo(() => ({
    cart: cartState, currentPersona: signedIn ? { id: 'VP0000001', name: accountName, email: 'minhanh@example.vn' } : null, authReady: true,
    navigate: shared.navigate, rememberBooking: shared.rememberBooking, showToast: shared.showToast, openLoginModal: shared.openLoginModal,
    refreshCart: async () => { shared.refreshCart(); return cartRef.current; },
    updateCartItem: async (id: string, body: any, options?: any) => {
      shared.updateCartItem(id, body, options);
      const next = applyPatch(cartRef.current, id, body);
      cartRef.current = next;
      setCart(next);
      return null;
    },
  }), [cartState, accountName, signedIn]);
  return <shared.Ctx.Provider value={value}><CheckoutView /></shared.Ctx.Provider>;
}

/** Mở trang thanh toán của một đơn nháp và chờ đơn nháp tải xong (bước đầu hiện ra). */
async function open(draft: any, accountName?: string, signedIn = true) {
  store.draft = draft;
  const view = render(<Harness accountName={accountName} signedIn={signedIn} />);
  await screen.findByRole('heading', { level: 2 });
  return view;
}

const clone = (x: unknown) => JSON.parse(JSON.stringify(x));
const heading = () => screen.getByRole('heading', { level: 2 }).textContent;
const step = () => new URLSearchParams(window.location.search).get('step');
const continueButton = () => screen.getAllByRole('button', { name: /^Tiếp tục/ })[0] as HTMLButtonElement;
const payButton = () => screen.getAllByRole('button', { name: /^Thanh toán/ })[0] as HTMLButtonElement;

function fillTravelers() {
  fireEvent.change(screen.getByLabelText('Họ (Người lớn 2)'), { target: { value: 'Trần' } });
  fireEvent.change(screen.getByLabelText('Tên đệm và tên (Người lớn 2)'), { target: { value: 'Thu Hà' } });
  fireEvent.change(screen.getByLabelText('Họ (Trẻ em 1)'), { target: { value: 'Nguyễn' } });
  fireEvent.change(screen.getByLabelText('Tên đệm và tên (Trẻ em 1)'), { target: { value: 'Gia Bảo' } });
  fireEvent.change(screen.getByLabelText('Ngày sinh (Trẻ em 1)'), { target: { value: '12052019' } });
  fireEvent.change(screen.getByLabelText('Số điện thoại'), { target: { value: '0912345678' } });
  fillFlightInfo();
}

/** Giỏ gia đình có vé máy bay nên mỗi hành khách khai thêm thông tin cho hãng bay (FR-BKG-13). */
function fillFlightInfo() {
  const pick = (id: string) => fireEvent.click(document.getElementById(id) as HTMLElement);
  pick('x-title-t1-MS');
  fireEvent.change(screen.getByLabelText('Ngày sinh (Người lớn 1)'), { target: { value: '14031988' } });
  fireEvent.change(screen.getByLabelText('Số giấy tờ (Người lớn 1)'), { target: { value: '079188001234' } });
  pick('x-title-t2-MRS');
  fireEvent.change(screen.getByLabelText('Ngày sinh (Người lớn 2)'), { target: { value: '02091990' } });
  fireEvent.change(screen.getByLabelText('Số giấy tờ (Người lớn 2)'), { target: { value: '079190004567' } });
  pick('x-title-t3-MSTR');
}

async function goToServices() {
  fillTravelers();
  fireEvent.click(continueButton());
  await waitFor(() => expect(step()).toBe('services'));
}

async function goToReview() {
  await goToServices();
  fireEvent.click(continueButton());
  await waitFor(() => expect(step()).toBe('review'));
}

function apiError(body: { error: { code: string; message: string; retryable: boolean; details?: any } }, status: number) {
  const e = body.error;
  return new ApiError(e.message, e.code, status, e.retryable, 'req-1', e.details ?? null);
}

describe('CheckoutView — ba bước', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', `/checkout?draft=${DRAFT_ID}`);
    vi.clearAllMocks();
    shared.patchDelay = 0;
    mockDraftApi();
  });
  afterEach(() => cleanup());

  it('mở ở bước Hành khách với đoàn mặc định lấy từ giỏ và người lớn 1 điền sẵn từ tài khoản', async () => {
    await open(clone(familyDraft));
    expect(heading()).toBe('Hành khách');
    expect(screen.getAllByTestId('traveler-card')).toHaveLength(3);          // 2 người lớn + 1 trẻ em, đúng đoàn của giỏ
    expect((screen.getByLabelText('Họ (Người lớn 1)') as HTMLInputElement).value).toBe('Nguyễn');
    expect((screen.getByLabelText('Tên đệm và tên (Người lớn 1)') as HTMLInputElement).value).toBe('Minh Anh');
    expect((screen.getByLabelText('Họ và tên người liên hệ') as HTMLInputElement).value).toBe('Nguyễn Minh Anh');
    expect(screen.getByTestId('party-text').textContent).toContain('2 người lớn · 1 trẻ em');
    expect(screen.getByTestId('summary-total').textContent).toContain('6.960.384');
    expect(screen.getByRole('navigation', { name: 'Các bước thanh toán' })).toBeTruthy();
  });

  it('tên tài khoản không dùng được làm họ tên (có chữ số) thì Người lớn 1 để trống thay vì điền sẵn giá trị sẽ bị báo lỗi', async () => {
    await open(clone(familyDraft), 'Khách test 01');
    expect((screen.getByLabelText('Họ (Người lớn 1)') as HTMLInputElement).value).toBe('');
    expect((screen.getByLabelText('Tên đệm và tên (Người lớn 1)') as HTMLInputElement).value).toBe('');
    expect((screen.getByLabelText('Họ và tên người liên hệ') as HTMLInputElement).value).toBe('');
  });

  it('AC-BKG-07: bấm Tiếp tục khi còn thiếu thì ở lại bước, hiện "Còn n thông tin cần sửa" và đưa con trỏ về trường lỗi đầu tiên', async () => {
    await open(clone(familyDraft));
    fireEvent.click(continueButton());
    const box = await screen.findByRole('alert');
    expect(box.textContent).toMatch(/Còn \d+ thông tin cần sửa/);
    expect(box.textContent).toContain('Người lớn 2 · Họ: Vui lòng nhập họ.');
    expect(box.textContent).toContain('Trẻ em 1 · Ngày sinh: Vui lòng nhập ngày sinh.');
    expect(step()).toBeNull();                                                 // không chuyển bước
    expect(shared.updateCartItem).not.toHaveBeenCalled();                      // chưa sửa giỏ
    // Lỗi đầu tiên theo thứ tự trên màn hình: khối thông tin bay của Người lớn 1 nằm trước ô Họ của Người lớn 2.
    await waitFor(() => expect(document.activeElement?.id).toBe('dob-t1'));
    expect(box.textContent).toContain('Người lớn 1 · Danh xưng: Chọn danh xưng.');
    expect(box.textContent).toContain('Người lớn 1 · Số giấy tờ: Nhập số giấy tờ.');
    expect(screen.getByLabelText('Họ (Người lớn 2)').getAttribute('aria-invalid')).toBe('true');
    expect(document.getElementById('e-sn-t2')?.textContent).toBe('Vui lòng nhập họ.');
  });

  it('chặn trẻ em đã đủ 12 tuổi vào ngày sử dụng sớm nhất và nói rõ ngày tròn 12 tuổi', async () => {
    await open(clone(familyDraft));
    fillTravelers();
    fireEvent.change(screen.getByLabelText('Ngày sinh (Trẻ em 1)'), { target: { value: '17102014' } });
    fireEvent.click(continueButton());
    expect((await screen.findByRole('alert')).textContent).toContain('Bé đã đủ 12 tuổi vào 17/10/2026. Vui lòng chọn loại Người lớn.');
    expect(step()).toBeNull();
  });

  it('kiểm ngày sinh và họ tên khi rời trường (blur), không kiểm theo từng phím', async () => {
    await open(clone(familyDraft));
    const input = screen.getByLabelText('Ngày sinh (Trẻ em 1)');
    fireEvent.change(input, { target: { value: '3103' } });
    expect(document.getElementById('e-dob-t3')?.textContent).toBe('');       // đang gõ: chưa báo lỗi
    fireEvent.blur(input);
    expect(document.getElementById('e-dob-t3')?.textContent).toBe('Ngày sinh không hợp lệ.');
    fireEvent.change(screen.getByLabelText('Ngày sinh (Trẻ em 1)'), { target: { value: '12052019' } });
    expect((screen.getByLabelText('Ngày sinh (Trẻ em 1)') as HTMLInputElement).value).toBe('12/05/2019');
    fireEvent.blur(screen.getByLabelText('Ngày sinh (Trẻ em 1)'));
    expect(document.getElementById('h-dob-t3')?.textContent).toBe('7 tuổi vào 17/10/2026 (ngày sử dụng sớm nhất)');
  });

  it('bộ đếm thêm/bớt thẻ hành khách, giữ 1 người lớn tối thiểu và 9 khách tối đa', async () => {
    await open(clone(familyDraft));
    fireEvent.click(screen.getByRole('button', { name: 'Thêm trẻ em' }));
    expect(screen.getAllByTestId('traveler-card')).toHaveLength(4);
    expect(screen.getByLabelText('Họ (Trẻ em 2)')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Bớt trẻ em' }));      // thẻ trẻ em 2 còn trống: bỏ ngay, không hỏi lại
    expect(screen.getAllByTestId('traveler-card')).toHaveLength(3);
    fireEvent.click(screen.getByRole('button', { name: 'Bớt người lớn' }));
    fireEvent.click(screen.getByRole('button', { name: 'Bớt người lớn' }));
    expect((screen.getByRole('button', { name: 'Bớt người lớn' }) as HTMLButtonElement).disabled).toBe(true);
    for (let i = 0; i < 10; i += 1) fireEvent.click(screen.getByRole('button', { name: 'Thêm người lớn' }));
    expect(screen.getAllByTestId('traveler-card')).toHaveLength(9);
    expect((screen.getByRole('button', { name: 'Thêm người lớn' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Thêm trẻ em' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('hỏi lại trước khi bỏ một thẻ hành khách đã có dữ liệu', async () => {
    await open(clone(familyDraft));
    fireEvent.change(screen.getByLabelText('Họ (Trẻ em 1)'), { target: { value: 'Nguyễn' } });
    fireEvent.click(screen.getByRole('button', { name: 'Bớt trẻ em' }));
    const dialog = screen.getByRole('dialog', { name: 'Xác nhận bỏ khách' });
    expect(dialog.textContent).toContain('Thông tin đã nhập');
    fireEvent.click(within(dialog).getByText('Giữ lại'));
    expect(screen.getAllByTestId('traveler-card')).toHaveLength(3);
    fireEvent.click(screen.getByRole('button', { name: 'Bớt trẻ em' }));
    fireEvent.click(screen.getByText('Bỏ khách'));
    expect(screen.getAllByTestId('traveler-card')).toHaveLength(2);
  });

  it('người liên hệ đồng bộ với Người lớn 1 khi bật ô "cũng là Người lớn 1"', async () => {
    await open(clone(familyDraft));
    fireEvent.change(screen.getByLabelText('Họ và tên người liên hệ'), { target: { value: 'Lê Văn Hùng' } });
    expect((screen.getByLabelText('Họ (Người lớn 1)') as HTMLInputElement).value).toBe('Lê');
    expect((screen.getByLabelText('Tên đệm và tên (Người lớn 1)') as HTMLInputElement).value).toBe('Văn Hùng');
    fireEvent.click(screen.getByLabelText('Người liên hệ cũng là Người lớn 1'));   // tắt: hai ô tách nhau
    fireEvent.change(screen.getByLabelText('Họ và tên người liên hệ'), { target: { value: 'Phạm Thị Lan' } });
    expect((screen.getByLabelText('Họ (Người lớn 1)') as HTMLInputElement).value).toBe('Lê');
  });

  it('hết bước ①: sang bước Dịch vụ, mỗi mục một thẻ với dòng giá theo loại khách lấy từ Backend', async () => {
    await open(clone(familyDraft));
    await goToServices();
    expect(heading()).toBe('Dịch vụ');
    const cards = screen.getAllByTestId('service-card');
    expect(cards).toHaveLength(3);
    const ticket = cards.find((c) => c.textContent?.includes('VinWonders'))!;
    expect(within(ticket).getByTestId('fare-lines').textContent).toContain('2 × 1.500.000');
    expect(within(ticket).getByTestId('fare-lines').textContent).toContain('1 × 504.000');
    expect(within(ticket).getByTestId('line-total').textContent).toContain('3.504.000');
    expect(screen.getByTestId('summary-total').textContent).toContain('6.960.384');       // = tổng ở ví dụ spec §4.5
    const flight = cards.find((c) => c.textContent?.includes('VJ601'))!;
    expect(flight.textContent).toContain('Chưa có giá vé trẻ em riêng');
  });

  it('bỏ chọn trẻ em ở vé tham quan: đợi 400 ms rồi PATCH số khách của đúng mục đó và giá cập nhật', async () => {
    await open(clone(familyDraft));
    await goToServices();
    const ticket = screen.getAllByTestId('service-card').find((c) => c.textContent?.includes('VinWonders'))!;
    fireEvent.click(within(ticket).getByLabelText('Nguyễn Gia Bảo dùng [Wonder Ngon] Vé VinWonders Nha Trang + Buggy + Fastpass 3 game hot'));
    expect(shared.updateCartItem).not.toHaveBeenCalled();                                   // đang debounce
    await waitFor(() => expect(shared.updateCartItem).toHaveBeenCalledWith(
      'ci-vinwonders', { guests: { adults: 2, children: 0 }, quantity: 2 }), { timeout: 3000 });
    await waitFor(() => expect(within(ticket).getByTestId('line-total').textContent).toContain('3.000.000'));
    expect(screen.getByTestId('summary-total').textContent).toContain('6.456.384');
    expect(screen.queryByTestId('warnings')).toBeNull();                                    // bé vẫn dùng khách sạn và chuyến bay: không có cảnh báo
  });

  it('đổi ý khi PATCH trước còn đang bay: PATCH sau vẫn được gửi, tới sau PATCH trước, và giá cuối khớp lựa chọn cuối', async () => {
    shared.patchDelay = 700;
    await open(clone(familyDraft));
    await goToServices();
    const ticket = screen.getAllByTestId('service-card').find((c) => c.textContent?.includes('VinWonders'))!;
    const child = () => within(ticket).getByLabelText('Nguyễn Gia Bảo dùng [Wonder Ngon] Vé VinWonders Nha Trang + Buggy + Fastpass 3 game hot');
    fireEvent.click(child());                                                                // bỏ bé khỏi vé
    await waitFor(() => expect(shared.updateCartItem).toHaveBeenCalledTimes(1), { timeout: 2000 });   // PATCH 1 bắt đầu bay
    fireEvent.click(child());                                                                // đổi ý: chọn lại bé
    await waitFor(() => expect(shared.updateCartItem).toHaveBeenCalledTimes(2), { timeout: 4000 });
    expect(shared.updateCartItem.mock.calls.map((c) => c[1])).toEqual([
      { guests: { adults: 2, children: 0 }, quantity: 2 },
      { guests: { adults: 2, children: 1 }, quantity: 3 }]);
    await waitFor(() => expect(within(ticket).getByTestId('line-total').textContent).toContain('3.504.000'), { timeout: 4000 });
    expect(screen.getByTestId('summary-total').textContent).toContain('6.960.384');
  }, 15000);

  it('khách sạn: chip khách theo phòng, người đại diện, số khách/sức chứa; xếp hết người lớn ra khỏi phòng thì báo mỗi phòng cần người lớn', async () => {
    await open(clone(familyDraft));
    await goToServices();
    const hotel = screen.getAllByTestId('service-card').find((c) => c.textContent?.includes('Lucky Sun'))!;
    expect(hotel.textContent).toContain('Tối đa 3 khách/phòng');
    expect(within(hotel).getByTestId('room').textContent).toContain('3/3 khách');
    expect((within(hotel).getByLabelText('Người đại diện nhận phòng (Phòng 1)') as HTMLSelectElement).value).toBe('t1');
    fireEvent.click(within(hotel).getByLabelText('Bỏ Nguyễn Minh Anh khỏi phòng 1'));
    fireEvent.click(within(hotel).getByLabelText('Bỏ Trần Thu Hà khỏi phòng 1'));
    expect(hotel.textContent).toContain('Mỗi phòng cần ít nhất 1 người lớn.');
    expect(hotel.textContent).toContain('Còn 2 khách chưa có phòng');
    expect(within(hotel).getByText('Cần sửa')).toBeTruthy();
  });

  it('khách sạn: không thêm phòng được khi không còn người lớn nào chưa đứng tên phòng', async () => {
    await open(clone(familyDraft));
    await goToServices();
    const hotel = screen.getAllByTestId('service-card').find((c) => c.textContent?.includes('Lucky Sun'))!;
    expect((within(hotel).getByLabelText('Thêm phòng') as HTMLButtonElement).disabled).toBe(false);   // Người lớn 2 chưa đứng tên phòng
    fireEvent.click(within(hotel).getByLabelText('Thêm phòng'));
    expect(within(hotel).getAllByTestId('room')).toHaveLength(2);
    expect((within(hotel).getByLabelText('Thêm phòng') as HTMLButtonElement).disabled).toBe(true);
  });

  it('bấm Tiếp tục ở bước ② khi còn lỗi: ở lại, hiện hộp tóm tắt lỗi, không sang bước ③', async () => {
    await open(clone(familyDraft));
    await goToServices();
    const ticket = screen.getAllByTestId('service-card').find((c) => c.textContent?.includes('VinWonders'))!;
    for (const name of ['Nguyễn Minh Anh', 'Trần Thu Hà', 'Nguyễn Gia Bảo']) {
      fireEvent.click(within(ticket).getByLabelText(`${name} dùng [Wonder Ngon] Vé VinWonders Nha Trang + Buggy + Fastpass 3 game hot`));
    }
    fireEvent.click(continueButton());
    const box = await screen.findByRole('alert');
    expect(box.textContent).toContain('Chọn ít nhất 1 khách dùng [Wonder Ngon] Vé VinWonders');
    expect(step()).toBe('services');
  });

  it('bước Xem lại: hiện hành khách, dịch vụ, tổng bằng CartResponse; nút Thanh toán khoá tới khi đồng ý điều khoản', async () => {
    await open(clone(familyDraft));
    await goToReview();
    expect(heading()).toBe('Xem lại và thanh toán');
    expect(screen.getAllByTestId('review-item')).toHaveLength(3);
    expect(screen.getByTestId('review-total').textContent).toContain('6.960.384');
    expect(screen.getByText(/hoàn 100% nếu huỷ trước/).textContent).toContain('00:00 ngày 16/10/2026');
    const radios = screen.getAllByRole('radio') as HTMLInputElement[];
    expect(radios.map((r) => [r.value, r.checked, r.disabled])).toEqual([
      ['stripe', true, false], ['ewallet', false, true], ['bank_transfer', false, true]]);
    expect(screen.getAllByText('Sắp có')).toHaveLength(2);
    expect(payButton().disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    expect(payButton().disabled).toBe(false);
    expect(payButton().textContent).toContain('6.960.384');
  });

  it('hạn hoàn tiền đã qua ngay từ lúc đặt (dùng dịch vụ hôm nay hoặc ngày mai): nói rõ đơn không được hoàn tiền thay vì hứa hoàn 100%', async () => {
    const soon = clone(familyDraft);
    const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date());
    for (const item of soon.items) item.usingDate = today;
    await open(soon);
    await goToReview();
    const terms = screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/).closest('label')!;
    expect(terms.textContent).toContain('đã quá hạn hoàn tiền');
    expect(terms.textContent).toContain('không được hoàn tiền nếu huỷ');
    expect(terms.textContent).not.toContain('hoàn 100%');
  });

  it('FR-BKG-13: giỏ có vé máy bay thì mỗi thẻ hành khách có khối thông tin bay; giỏ không có vé bay thì không có', async () => {
    const { unmount } = await open(clone(familyDraft));
    expect(screen.getAllByTestId('flight-fields')).toHaveLength(3);
    expect(screen.getByText(/Đơn có vé máy bay nên mỗi khách cần thêm vài thông tin/)).toBeTruthy();
    unmount();
    const hotelOnly = clone(familyDraft);
    hotelOnly.items = hotelOnly.items.filter((i: any) => i.product.taxonomy !== 'flight');
    await open(hotelOnly);
    expect(screen.queryAllByTestId('flight-fields')).toHaveLength(0);
  });

  it('AC-BKG-12: đổi quốc tịch khác Việt Nam khi đang chọn CCCD thì tự chuyển sang hộ chiếu và xoá số giấy tờ', async () => {
    await open(clone(familyDraft));
    fireEvent.change(screen.getByLabelText('Số giấy tờ (Người lớn 1)'), { target: { value: '079188001234' } });
    expect((document.getElementById('x-doc-t1-CCCD') as HTMLInputElement).checked).toBe(true);
    fireEvent.change(document.getElementById('x-nat-t1') as HTMLElement, { target: { value: 'KR' } });
    expect((document.getElementById('x-doc-t1-PASSPORT') as HTMLInputElement).checked).toBe(true);
    expect((document.getElementById('x-doc-t1-CCCD') as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText('Số giấy tờ (Người lớn 1)') as HTMLInputElement).value).toBe('');
    expect(screen.getByLabelText('Ngày hết hạn hộ chiếu (Người lớn 1)')).toBeTruthy();
  });

  it('AC-BKG-11: hộ chiếu hết hạn không sau ngày bay cuối cùng bị chặn tại ô ngày hết hạn', async () => {
    await open(clone(familyDraft));
    fillTravelers();
    fireEvent.change(document.getElementById('x-nat-t1') as HTMLElement, { target: { value: 'KR' } });
    fireEvent.change(screen.getByLabelText('Số giấy tờ (Người lớn 1)'), { target: { value: 'C1234567' } });
    fireEvent.change(screen.getByLabelText('Ngày hết hạn hộ chiếu (Người lớn 1)'), { target: { value: '19102026' } });
    fireEvent.click(continueButton());
    expect((await screen.findByRole('alert')).textContent).toContain('Hộ chiếu hết hạn trước ngày bay cuối cùng (19/10/2026).');
    expect(step()).toBeNull();
    fireEvent.change(screen.getByLabelText('Ngày hết hạn hộ chiếu (Người lớn 1)'), { target: { value: '20102026' } });
    fireEvent.click(continueButton());
    await waitFor(() => expect(step()).toBe('services'));
  });

  it('ô Tên in trên vé hiện họ / tên không dấu viết hoa', async () => {
    await open(clone(familyDraft));
    expect(screen.getAllByText('NGUYEN / MINH ANH').length).toBeGreaterThan(0);
  });

  it('AC-BKG-05: gửi đoàn khách, họ và tên hai ô, ngày sinh ISO và phân bổ từng mục; không gửi số tiền; rồi chuyển sang Stripe', async () => {
    api.createBooking.mockResolvedValue(createdFamily);
    await open(clone(familyDraft));
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalledWith(createdFamily.payment.checkoutUrl));
    const body = api.createBooking.mock.calls[0][0];
    expect(body.contact).toEqual({ fullName: 'Nguyễn Minh Anh', email: 'minhanh@example.vn', phone: '0912345678' });
    // Giỏ có vé máy bay: thêm ngày sinh người lớn và khối `documents` (FR-BKG-13); trẻ em không có số giấy tờ.
    expect(body.travelers).toEqual([
      { travelerRef: 't1', type: 'ADULT', surname: 'Nguyễn', givenNames: 'Minh Anh', birthDate: '1988-03-14',
        documents: { title: 'MS', nationality: 'VN', docType: 'CCCD', docNumber: '079188001234' } },
      { travelerRef: 't2', type: 'ADULT', surname: 'Trần', givenNames: 'Thu Hà', birthDate: '1990-09-02',
        documents: { title: 'MRS', nationality: 'VN', docType: 'CCCD', docNumber: '079190004567' } },
      { travelerRef: 't3', type: 'CHILD', surname: 'Nguyễn', givenNames: 'Gia Bảo', birthDate: '2019-05-12',
        documents: { title: 'MSTR', nationality: 'VN' } }]);
    expect(body.itemDetails).toEqual([
      { cartItemId: 'ci-hotel', rooms: [{ travelerRefs: ['t1', 't2', 't3'], leadTravelerRef: 't1' }] },
      { cartItemId: 'ci-vinwonders', travelerRefs: ['t1', 't2', 't3'] },
      { cartItemId: 'ci-vj601', travelerRefs: ['t1', 't2', 't3'] }]);
    expect(JSON.stringify(body)).not.toMatch(/total|amount|price/i);
    expect(shared.rememberBooking).toHaveBeenCalledWith(createdFamily);
  });

  it('400 VALIDATION_ERROR ở travelers: về bước Hành khách, gắn lỗi vào đúng trường và đưa con trỏ tới trường lỗi đầu tiên', async () => {
    api.createBooking.mockRejectedValue(apiError({ error: { code: 'VALIDATION_ERROR', message: 'Thông tin đặt chỗ chưa hợp lệ.', retryable: false, details: { fields: [
      { field: 'travelers[2].birthDate', reason: 'CHILD_AGE_INVALID', message: 'Bé đã đủ 12 tuổi vào 17/10/2026. Vui lòng chọn loại Người lớn.' }] } } }, 400));
    await open(clone(familyDraft));
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    await waitFor(() => expect(step()).toBe('travelers'));
    expect(document.getElementById('e-dob-t3')?.textContent).toBe('Bé đã đủ 12 tuổi vào 17/10/2026. Vui lòng chọn loại Người lớn.');
    expect((await screen.findByRole('alert')).textContent).toContain('Còn 1 thông tin cần sửa');
    await waitFor(() => expect(document.activeElement?.id).toBe('dob-t3'));
  });

  it('400 lỗi ở cả hai bước (fixture party-invalid): về bước Hành khách trước và chỉ đếm lỗi của bước đó', async () => {
    api.createBooking.mockRejectedValue(apiError(partyInvalid as any, 400));
    await open(clone(familyDraft));
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    await waitFor(() => expect(step()).toBe('travelers'));
    expect((await screen.findByRole('alert')).textContent).toContain('Còn 1 thông tin cần sửa');
    expect(document.getElementById('e-dob-t3')?.textContent).toContain('Bé đã đủ 12 tuổi');
  });

  it('400 lỗi ở itemDetails: về bước Dịch vụ, báo lỗi ngay trong phòng và thẻ; sửa phân bổ thì lỗi của thẻ đó mất', async () => {
    api.createBooking.mockRejectedValue(apiError({ error: { code: 'VALIDATION_ERROR', message: 'Thông tin đặt chỗ chưa hợp lệ.', retryable: false, details: { fields: [
      { field: 'itemDetails[0].rooms[0]', reason: 'OCCUPANCY_EXCEEDED', message: 'Phòng 1 chứa tối đa 3 khách.', cartItemId: 'ci-hotel' },
      { field: 'itemDetails[1]', reason: 'ITEM_WITHOUT_TRAVELER', message: 'Chọn ít nhất 1 khách dùng vé.', cartItemId: 'ci-vinwonders' }] } } }, 400));
    await open(clone(familyDraft));
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    await waitFor(() => expect(step()).toBe('services'));
    expect((await screen.findByRole('alert')).textContent).toContain('Còn 2 thông tin cần sửa');
    const hotel = screen.getAllByTestId('service-card').find((c) => c.textContent?.includes('Lucky Sun'))!;
    expect(within(hotel).getByTestId('room').textContent).toContain('Phòng 1 chứa tối đa 3 khách.');
    await waitFor(() => expect(document.activeElement?.id).toBe('room-ci-hotel-0'));
    const ticket = screen.getAllByTestId('service-card').find((c) => c.textContent?.includes('VinWonders'))!;
    expect(ticket.textContent).toContain('Chọn ít nhất 1 khách dùng vé.');
    fireEvent.click(within(ticket).getByLabelText('Nguyễn Gia Bảo dùng [Wonder Ngon] Vé VinWonders Nha Trang + Buggy + Fastpass 3 game hot'));
    expect(ticket.textContent).not.toContain('Chọn ít nhất 1 khách dùng vé.');
  });

  it('409 PRICE_CHANGED của giá vé trẻ em: banner nêu rõ loại giá; "Cập nhật và tiếp tục" PATCH lại số lượng hiện tại', async () => {
    api.createBooking.mockRejectedValue(apiError(priceChangedChild as any, 409));
    await open(clone(familyDraft));
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/Giá vé trẻ em của \[Wonder Ngon\] Vé VinWonders.* đã đổi từ 504\.000.* thành 550\.000/);
    fireEvent.click(screen.getByText('Cập nhật và tiếp tục'));
    await waitFor(() => expect(shared.updateCartItem).toHaveBeenCalledWith('ci-vinwonders', { quantity: 3 }));
  });

  it('409 BOOKING_PENDING_PAYMENT: hộp thoại tiếp tục hoặc huỷ đơn cũ rồi đặt lại đúng dữ liệu đang có', async () => {
    api.createBooking.mockRejectedValueOnce(apiError(pendingError as any, 409)).mockResolvedValue(createdFamily);
    api.cancelBooking.mockResolvedValue({ ...createdFamily, status: 'CANCELLED' });
    await open(clone(familyDraft));
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toContain('VOTA-20260916-8K3F');
    fireEvent.click(screen.getByText('Huỷ đơn đó và đặt lại'));
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalled());
    expect(api.createBooking).toHaveBeenCalledTimes(2);
    expect(api.createBooking.mock.calls[1][0]).toEqual(api.createBooking.mock.calls[0][0]);
  });

  it('503 cổng thanh toán: ở lại bước Xem lại với nút Thử lại, không mất dữ liệu', async () => {
    api.createBooking.mockRejectedValueOnce(apiError(providerDown as any, 503)).mockResolvedValue(createdFamily);
    await open(clone(familyDraft));
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    expect((await screen.findByRole('alert')).textContent).toContain('Cổng thanh toán tạm thời không phản hồi');
    expect(step()).toBe('review');
    fireEvent.click(screen.getByText('Thử lại'));
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalled());
  });

  it('tải lại trang ở ?step=review khi chưa có dữ liệu: về bước Hành khách kèm lời nhắc nhập lại', async () => {
    window.history.replaceState(null, '', `/checkout?draft=${DRAFT_ID}&step=review`);
    await open(clone(familyDraft));
    await waitFor(() => expect(step()).toBe('travelers'));
    expect(heading()).toBe('Hành khách');
    expect(screen.getByText(/họ tên và ngày sinh không được lưu khi tải lại trang/)).toBeTruthy();
  });

  it('nút Back của trình duyệt về bước trước mà không mất dữ liệu đã nhập', async () => {
    await open(clone(familyDraft));
    await goToServices();
    await act(async () => { window.history.back(); await new Promise((r) => setTimeout(r, 50)); });
    await waitFor(() => expect(heading()).toBe('Hành khách'));
    expect((screen.getByLabelText('Họ (Người lớn 2)') as HTMLInputElement).value).toBe('Trần');
    expect((screen.getByLabelText('Ngày sinh (Trẻ em 1)') as HTMLInputElement).value).toBe('12/05/2019');
  });

  it('có mục hết chỗ: khoá nút Thanh toán', async () => {
    const draft = clone(familyDraft);
    draft.items.find((i: any) => i.cartItemId === 'ci-vinwonders').product.available = false;
    await open(draft);
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    expect(payButton().disabled).toBe(true);
  });

  it('đơn nháp không còn mục nào thì về trang chủ, không về giỏ', async () => {
    store.draft = { ...clone(familyDraft), items: [], itemCount: 0, subtotal: 0, total: 0 };
    render(<Harness />);
    await waitFor(() => expect(shared.navigate).toHaveBeenCalledWith('/'));
  });
});

describe('CheckoutView — hai nguồn: đơn nháp của Đặt ngay và giỏ hàng (AC-BKG-13 … AC-BKG-17)', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', `/checkout?draft=${DRAFT_ID}`);
    vi.clearAllMocks();
    shared.patchDelay = 0;
    mockDraftApi();
    api.createBooking.mockResolvedValue(createdFamily);
  });
  afterEach(() => cleanup());

  it('đơn nháp: đọc đúng đơn nháp trên URL, hiện đồng hồ 30 phút, không có lối sửa giỏ; chuyển bước vẫn giữ draft trên URL', async () => {
    store.draft = { ...clone(familyDraft), expiresAt: new Date(Date.now() + 29 * 60_000 + 30_000).toISOString() };
    await open(store.draft);
    expect(api.getBookingDraft).toHaveBeenCalledWith(DRAFT_ID);
    expect(screen.getByTestId('draft-countdown').textContent).toMatch(/Phiên thanh toán còn 29:\d\d/);
    expect(screen.queryByText('Sửa giỏ hàng')).toBeNull();
    // Đơn nháp có vé tham quan: báo trước là vé đã nằm trong giỏ, khách sạn và vé máy bay thì không được giữ.
    expect(screen.getAllByTestId('draft-cart-note')[0].textContent).toContain('đã được lưu vào giỏ hàng');
    await goToServices();
    expect(new URLSearchParams(window.location.search).get('draft')).toBe(DRAFT_ID);   // tải lại trang vẫn là đơn nháp này
  });

  it('đơn nháp: POST /bookings gửi draftId, chỉ các mục của đơn nháp, không đụng tới giỏ', async () => {
    store.draft = clone(familyDraft);
    render(<Harness cart={clone(familyCart)} />);                                    // giỏ đang có vé VinWonders
    await screen.findByRole('heading', { level: 2 });
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalled());
    const body = api.createBooking.mock.calls[0][0];
    expect(body.draftId).toBe(DRAFT_ID);
    expect(body.itemDetails.map((d: any) => d.cartItemId).sort()).toEqual(['ci-hotel', 'ci-vinwonders', 'ci-vj601']);
    expect(shared.updateCartItem.mock.calls.every((call) => call.length === 2)).toBe(true);   // mọi PATCH đi vào đơn nháp
  });

  it('khách chưa đăng nhập: điền đủ ba bước được; bấm Thanh toán mới mở hộp đăng nhập, chưa tạo đơn', async () => {
    await open(clone(familyDraft), undefined, false);
    fireEvent.change(screen.getByLabelText('Họ (Người lớn 1)'), { target: { value: 'Nguyễn' } });
    fireEvent.change(screen.getByLabelText('Tên đệm và tên (Người lớn 1)'), { target: { value: 'Minh Anh' } });
    fireEvent.change(screen.getByLabelText('Họ và tên người liên hệ'), { target: { value: 'Nguyễn Minh Anh' } });
    expect(screen.getByTestId('guest-email-note').textContent).toContain('khi bấm Thanh toán, bạn sẽ đăng nhập');
    await goToReview();                                                              // không bị chặn vì chưa có email tài khoản
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    expect(shared.openLoginModal).toHaveBeenCalledTimes(1);
    expect(api.createBooking).not.toHaveBeenCalled();
  });

  it('410 khi tải đơn nháp: màn hình hết hạn nói rõ khách sạn, vé máy bay phải chọn lại còn tour vẫn trong giỏ', async () => {
    api.getBookingDraft.mockRejectedValue(apiError(draftExpiredOnLoad as any, 410));
    render(<Harness />);
    const expired = await screen.findByTestId('draft-expired');
    expect(expired.textContent).toContain('Phiên thanh toán đã hết hạn');
    expect(expired.textContent).toContain('khách sạn, vé máy bay có thể đã đổi');
    expect(expired.textContent).toContain('vẫn nằm trong giỏ hàng');
    fireEvent.click(screen.getByRole('button', { name: 'Về giỏ hàng' }));
    expect(shared.navigate).toHaveBeenCalledWith('/cart');
    expect(screen.getByRole('button', { name: 'Chọn lại phòng' })).toBeTruthy();
  });

  it('410 khi bấm Thanh toán (đơn nháp hết hạn giữa chừng): chuyển sang màn hình hết hạn, không báo lỗi chung', async () => {
    api.createBooking.mockRejectedValue(apiError(draftExpired as any, 410));
    await open(clone(familyDraft));
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    const expired = await screen.findByTestId('draft-expired');
    expect(api.redirectToCheckout).not.toHaveBeenCalled();
    // Response không kèm danh sách mục: màn hình suy từ đơn nháp đang mở (khách sạn, vé máy bay chọn lại; vé tham quan còn trong giỏ).
    expect(expired.textContent).toContain('khách sạn, vé máy bay có thể đã đổi');
    expect(expired.textContent).toContain('vẫn nằm trong giỏ hàng');
    expect(screen.getByRole('button', { name: 'Tìm lại chuyến bay' })).toBeTruthy();
  });

  it('404: đơn nháp không tồn tại hoặc của người khác thì báo không tìm thấy', async () => {
    api.getBookingDraft.mockRejectedValue(apiError(draftNotFound as any, 404));
    render(<Harness />);
    expect((await screen.findByTestId('draft-not-found')).textContent).toContain('Không tìm thấy phiên thanh toán này');
  });

  it('giỏ (/checkout không có draft): thanh toán các mục của giỏ, không gửi draftId, có lối Sửa giỏ hàng, không có đồng hồ', async () => {
    window.history.replaceState(null, '', '/checkout');
    render(<Harness cart={clone(familyCart)} />);
    expect(heading()).toBe('Hành khách');
    expect(api.getBookingDraft).not.toHaveBeenCalled();
    expect(screen.queryByTestId('draft-countdown')).toBeNull();
    expect(screen.getAllByText('Sửa giỏ hàng').length).toBeGreaterThan(0);
    expect(screen.queryByTestId('draft-cart-note')).toBeNull();
    expect(screen.queryAllByTestId('flight-fields')).toHaveLength(0);                 // giỏ không bao giờ có vé máy bay
    fireEvent.change(screen.getByLabelText('Họ (Người lớn 2)'), { target: { value: 'Trần' } });
    fireEvent.change(screen.getByLabelText('Tên đệm và tên (Người lớn 2)'), { target: { value: 'Thu Hà' } });
    fireEvent.change(screen.getByLabelText('Họ (Trẻ em 1)'), { target: { value: 'Nguyễn' } });
    fireEvent.change(screen.getByLabelText('Tên đệm và tên (Trẻ em 1)'), { target: { value: 'Gia Bảo' } });
    fireEvent.change(screen.getByLabelText('Ngày sinh (Trẻ em 1)'), { target: { value: '12052019' } });
    fireEvent.change(screen.getByLabelText('Số điện thoại'), { target: { value: '0912345678' } });
    fireEvent.click(continueButton());
    await waitFor(() => expect(step()).toBe('services'));
    fireEvent.click(continueButton());
    await waitFor(() => expect(step()).toBe('review'));
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalled());
    const body = api.createBooking.mock.calls[0][0];
    expect(body.draftId).toBeUndefined();
    expect(body.itemDetails.map((d: any) => d.cartItemId)).toEqual(['ci-vinwonders']);
  });

  it('giỏ rỗng thì về /cart', () => {
    window.history.replaceState(null, '', '/checkout');
    render(<Harness cart={{ ...clone(familyCart), items: [], itemCount: 0, subtotal: 0, total: 0 }} />);
    expect(shared.navigate).toHaveBeenCalledWith('/cart');
  });
});
