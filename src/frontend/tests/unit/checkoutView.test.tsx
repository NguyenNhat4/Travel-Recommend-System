// @vitest-environment jsdom
import React, { useMemo, useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import familyCart from '../../../shared/mocks/booking/getCart.200-family.json';
import unavailableCart from '../../../shared/mocks/booking/getCart.200-item-unavailable.json';
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

/** Giả lập `PATCH /cart/items`: ghi số khách và tính lại dòng giá như Backend (chỉ để test giao diện, không phải nguồn giá thật). */
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

function Harness({ initial, accountName = 'Nguyễn Minh Anh' }: { initial: any; accountName?: string }) {
  const [cart, setCart] = useState(initial);
  const cartRef = React.useRef(cart);
  React.useEffect(() => { cartRef.current = cart; }, [cart]);
  const value = useMemo(() => ({
    cart, currentPersona: { id: 'VP0000001', name: accountName, email: 'minhanh@example.vn' }, authReady: true,
    navigate: shared.navigate, rememberBooking: shared.rememberBooking, showToast: shared.showToast, openLoginModal: shared.openLoginModal,
    refreshCart: async () => cartRef.current,
    updateCartItem: async (id: string, body: any, options?: any) => {
      shared.updateCartItem(id, body, options);
      if (shared.patchDelay) await new Promise((resolve) => setTimeout(resolve, shared.patchDelay));
      const next = applyPatch(cartRef.current, id, body);
      cartRef.current = next;
      setCart(next);
      return null;
    },
  }), [cart, accountName]);
  return <shared.Ctx.Provider value={value}><CheckoutView /></shared.Ctx.Provider>;
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
    window.history.replaceState(null, '', '/checkout');
    vi.clearAllMocks();
    shared.patchDelay = 0;
  });
  afterEach(() => cleanup());

  it('mở ở bước Hành khách với đoàn mặc định lấy từ giỏ và người lớn 1 điền sẵn từ tài khoản', () => {
    render(<Harness initial={clone(familyCart)} />);
    expect(heading()).toBe('Hành khách');
    expect(screen.getAllByTestId('traveler-card')).toHaveLength(3);          // 2 người lớn + 1 trẻ em, đúng đoàn của giỏ
    expect((screen.getByLabelText('Họ (Người lớn 1)') as HTMLInputElement).value).toBe('Nguyễn');
    expect((screen.getByLabelText('Tên đệm và tên (Người lớn 1)') as HTMLInputElement).value).toBe('Minh Anh');
    expect((screen.getByLabelText('Họ và tên người liên hệ') as HTMLInputElement).value).toBe('Nguyễn Minh Anh');
    expect(screen.getByTestId('party-text').textContent).toContain('2 người lớn · 1 trẻ em');
    expect(screen.getByTestId('summary-total').textContent).toContain('6.960.384');
    expect(screen.getByRole('navigation', { name: 'Các bước thanh toán' })).toBeTruthy();
  });

  it('tên tài khoản không dùng được làm họ tên (có chữ số) thì Người lớn 1 để trống thay vì điền sẵn giá trị sẽ bị báo lỗi', () => {
    render(<Harness initial={clone(familyCart)} accountName="Khách test 01" />);
    expect((screen.getByLabelText('Họ (Người lớn 1)') as HTMLInputElement).value).toBe('');
    expect((screen.getByLabelText('Tên đệm và tên (Người lớn 1)') as HTMLInputElement).value).toBe('');
    expect((screen.getByLabelText('Họ và tên người liên hệ') as HTMLInputElement).value).toBe('');
  });

  it('AC-BKG-07: bấm Tiếp tục khi còn thiếu thì ở lại bước, hiện "Còn n thông tin cần sửa" và đưa con trỏ về trường lỗi đầu tiên', async () => {
    render(<Harness initial={clone(familyCart)} />);
    fireEvent.click(continueButton());
    const box = await screen.findByRole('alert');
    expect(box.textContent).toMatch(/Còn \d+ thông tin cần sửa/);
    expect(box.textContent).toContain('Người lớn 2 · Họ: Vui lòng nhập họ.');
    expect(box.textContent).toContain('Trẻ em 1 · Ngày sinh: Vui lòng nhập ngày sinh.');
    expect(step()).toBeNull();                                                 // không chuyển bước
    expect(shared.updateCartItem).not.toHaveBeenCalled();                      // chưa sửa giỏ
    await waitFor(() => expect(document.activeElement?.id).toBe('sn-t2'));
    expect(screen.getByLabelText('Họ (Người lớn 2)').getAttribute('aria-invalid')).toBe('true');
    expect(document.getElementById('e-sn-t2')?.textContent).toBe('Vui lòng nhập họ.');
  });

  it('chặn trẻ em đã đủ 12 tuổi vào ngày sử dụng sớm nhất và nói rõ ngày tròn 12 tuổi', async () => {
    render(<Harness initial={clone(familyCart)} />);
    fillTravelers();
    fireEvent.change(screen.getByLabelText('Ngày sinh (Trẻ em 1)'), { target: { value: '17102014' } });
    fireEvent.click(continueButton());
    expect((await screen.findByRole('alert')).textContent).toContain('Bé đã đủ 12 tuổi vào 17/10/2026. Vui lòng chọn loại Người lớn.');
    expect(step()).toBeNull();
  });

  it('kiểm ngày sinh và họ tên khi rời trường (blur), không kiểm theo từng phím', () => {
    render(<Harness initial={clone(familyCart)} />);
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

  it('bộ đếm thêm/bớt thẻ hành khách, giữ 1 người lớn tối thiểu và 9 khách tối đa', () => {
    render(<Harness initial={clone(familyCart)} />);
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

  it('hỏi lại trước khi bỏ một thẻ hành khách đã có dữ liệu', () => {
    render(<Harness initial={clone(familyCart)} />);
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

  it('người liên hệ đồng bộ với Người lớn 1 khi bật ô "cũng là Người lớn 1"', () => {
    render(<Harness initial={clone(familyCart)} />);
    fireEvent.change(screen.getByLabelText('Họ và tên người liên hệ'), { target: { value: 'Lê Văn Hùng' } });
    expect((screen.getByLabelText('Họ (Người lớn 1)') as HTMLInputElement).value).toBe('Lê');
    expect((screen.getByLabelText('Tên đệm và tên (Người lớn 1)') as HTMLInputElement).value).toBe('Văn Hùng');
    fireEvent.click(screen.getByLabelText('Người liên hệ cũng là Người lớn 1'));   // tắt: hai ô tách nhau
    fireEvent.change(screen.getByLabelText('Họ và tên người liên hệ'), { target: { value: 'Phạm Thị Lan' } });
    expect((screen.getByLabelText('Họ (Người lớn 1)') as HTMLInputElement).value).toBe('Lê');
  });

  it('hết bước ①: sang bước Dịch vụ, mỗi mục một thẻ với dòng giá theo loại khách lấy từ Backend', async () => {
    render(<Harness initial={clone(familyCart)} />);
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
    render(<Harness initial={clone(familyCart)} />);
    await goToServices();
    const ticket = screen.getAllByTestId('service-card').find((c) => c.textContent?.includes('VinWonders'))!;
    fireEvent.click(within(ticket).getByLabelText('Nguyễn Gia Bảo dùng [Wonder Ngon] Vé VinWonders Nha Trang + Buggy + Fastpass 3 game hot'));
    expect(shared.updateCartItem).not.toHaveBeenCalled();                                   // đang debounce
    await waitFor(() => expect(shared.updateCartItem).toHaveBeenCalledWith(
      'ci-vinwonders', { guests: { adults: 2, children: 0 }, quantity: 2 }, { silent: true }), { timeout: 3000 });
    await waitFor(() => expect(within(ticket).getByTestId('line-total').textContent).toContain('3.000.000'));
    expect(screen.getByTestId('summary-total').textContent).toContain('6.456.384');
    expect(screen.queryByTestId('warnings')).toBeNull();                                    // bé vẫn dùng khách sạn và chuyến bay: không có cảnh báo
  });

  it('đổi ý khi PATCH trước còn đang bay: PATCH sau vẫn được gửi, tới sau PATCH trước, và giá cuối khớp lựa chọn cuối', async () => {
    shared.patchDelay = 700;
    render(<Harness initial={clone(familyCart)} />);
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
    render(<Harness initial={clone(familyCart)} />);
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
    render(<Harness initial={clone(familyCart)} />);
    await goToServices();
    const hotel = screen.getAllByTestId('service-card').find((c) => c.textContent?.includes('Lucky Sun'))!;
    expect((within(hotel).getByLabelText('Thêm phòng') as HTMLButtonElement).disabled).toBe(false);   // Người lớn 2 chưa đứng tên phòng
    fireEvent.click(within(hotel).getByLabelText('Thêm phòng'));
    expect(within(hotel).getAllByTestId('room')).toHaveLength(2);
    expect((within(hotel).getByLabelText('Thêm phòng') as HTMLButtonElement).disabled).toBe(true);
  });

  it('bấm Tiếp tục ở bước ② khi còn lỗi: ở lại, hiện hộp tóm tắt lỗi, không sang bước ③', async () => {
    render(<Harness initial={clone(familyCart)} />);
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
    render(<Harness initial={clone(familyCart)} />);
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
    const soon = clone(familyCart);
    const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date());
    for (const item of soon.items) item.usingDate = today;
    render(<Harness initial={soon} />);
    await goToReview();
    const terms = screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/).closest('label')!;
    expect(terms.textContent).toContain('đã quá hạn hoàn tiền');
    expect(terms.textContent).toContain('không được hoàn tiền nếu huỷ');
    expect(terms.textContent).not.toContain('hoàn 100%');
  });

  it('AC-BKG-05: gửi đoàn khách, họ và tên hai ô, ngày sinh ISO và phân bổ từng mục; không gửi số tiền; rồi chuyển sang Stripe', async () => {
    api.createBooking.mockResolvedValue(createdFamily);
    render(<Harness initial={clone(familyCart)} />);
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalledWith(createdFamily.payment.checkoutUrl));
    const body = api.createBooking.mock.calls[0][0];
    expect(body.contact).toEqual({ fullName: 'Nguyễn Minh Anh', email: 'minhanh@example.vn', phone: '0912345678' });
    expect(body.travelers).toEqual([
      { travelerRef: 't1', type: 'ADULT', surname: 'Nguyễn', givenNames: 'Minh Anh' },
      { travelerRef: 't2', type: 'ADULT', surname: 'Trần', givenNames: 'Thu Hà' },
      { travelerRef: 't3', type: 'CHILD', surname: 'Nguyễn', givenNames: 'Gia Bảo', birthDate: '2019-05-12' }]);
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
    render(<Harness initial={clone(familyCart)} />);
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
    render(<Harness initial={clone(familyCart)} />);
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
    render(<Harness initial={clone(familyCart)} />);
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
    render(<Harness initial={clone(familyCart)} />);
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/Giá vé trẻ em của \[Wonder Ngon\] Vé VinWonders.* đã đổi từ 504\.000.* thành 550\.000/);
    fireEvent.click(screen.getByText('Cập nhật và tiếp tục'));
    await waitFor(() => expect(shared.updateCartItem).toHaveBeenCalledWith('ci-vinwonders', { quantity: 3 }, { silent: true }));
  });

  it('409 BOOKING_PENDING_PAYMENT: hộp thoại tiếp tục hoặc huỷ đơn cũ rồi đặt lại đúng dữ liệu đang có', async () => {
    api.createBooking.mockRejectedValueOnce(apiError(pendingError as any, 409)).mockResolvedValue(createdFamily);
    api.cancelBooking.mockResolvedValue({ ...createdFamily, status: 'CANCELLED' });
    render(<Harness initial={clone(familyCart)} />);
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toContain('VOTA-20260916-8K3F');
    fireEvent.click(screen.getByText('Huỷ đơn đó và đặt lại từ giỏ'));
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalled());
    expect(api.createBooking).toHaveBeenCalledTimes(2);
    expect(api.createBooking.mock.calls[1][0]).toEqual(api.createBooking.mock.calls[0][0]);
  });

  it('503 cổng thanh toán: ở lại bước Xem lại với nút Thử lại, không mất dữ liệu', async () => {
    api.createBooking.mockRejectedValueOnce(apiError(providerDown as any, 503)).mockResolvedValue(createdFamily);
    render(<Harness initial={clone(familyCart)} />);
    await goToReview();
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    fireEvent.click(payButton());
    expect((await screen.findByRole('alert')).textContent).toContain('Cổng thanh toán tạm thời không phản hồi');
    expect(step()).toBe('review');
    fireEvent.click(screen.getByText('Thử lại'));
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalled());
  });

  it('tải lại trang ở ?step=review khi chưa có dữ liệu: về bước Hành khách kèm lời nhắc nhập lại', async () => {
    window.history.replaceState(null, '', '/checkout?step=review');
    render(<Harness initial={clone(familyCart)} />);
    await waitFor(() => expect(step()).toBe('travelers'));
    expect(heading()).toBe('Hành khách');
    expect(screen.getByText(/họ tên và ngày sinh không được lưu khi tải lại trang/)).toBeTruthy();
  });

  it('nút Back của trình duyệt về bước trước mà không mất dữ liệu đã nhập', async () => {
    render(<Harness initial={clone(familyCart)} />);
    await goToServices();
    await act(async () => { window.history.back(); await new Promise((r) => setTimeout(r, 50)); });
    await waitFor(() => expect(heading()).toBe('Hành khách'));
    expect((screen.getByLabelText('Họ (Người lớn 2)') as HTMLInputElement).value).toBe('Trần');
    expect((screen.getByLabelText('Ngày sinh (Trẻ em 1)') as HTMLInputElement).value).toBe('12/05/2019');
  });

  it('giỏ có mục hết chỗ: khoá nút Thanh toán', async () => {
    const cart = clone(unavailableCart);
    render(<Harness initial={cart} />);
    fireEvent.change(screen.getByLabelText('Họ (Người lớn 2)'), { target: { value: 'Trần' } });
    fireEvent.change(screen.getByLabelText('Tên đệm và tên (Người lớn 2)'), { target: { value: 'Thu Hà' } });
    fireEvent.change(screen.getByLabelText('Số điện thoại'), { target: { value: '0912345678' } });
    fireEvent.click(continueButton());
    await waitFor(() => expect(step()).toBe('services'));
    fireEvent.click(continueButton());
    await waitFor(() => expect(step()).toBe('review'));
    fireEvent.click(screen.getByLabelText(/Tôi đã kiểm tra họ tên hành khách/));
    expect(payButton().disabled).toBe(true);
  });

  it('giỏ rỗng thì về /cart', () => {
    render(<Harness initial={{ ...clone(familyCart), items: [], itemCount: 0, subtotal: 0, total: 0 }} />);
    expect(shared.navigate).toHaveBeenCalledWith('/cart');
  });
});
