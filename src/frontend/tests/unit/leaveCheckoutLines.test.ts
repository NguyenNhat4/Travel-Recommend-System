import { describe, expect, it } from 'vitest';
import familyDraft from '../../../shared/mocks/booking/getBookingDraft.200-family.json';
import familyCart from '../../../shared/mocks/booking/getCart.200-family.json';
import { leaveLines } from '../../src/components/checkout/LeaveCheckoutDialog';
import type { ApiCartItem } from '../../src/services/booking';

const draftItems = familyDraft.items as unknown as ApiCartItem[];
const cartItems = familyCart.items as unknown as ApiCartItem[];
const only = (taxonomy: string) => draftItems.filter((item) => item.product.taxonomy === taxonomy);

describe('leaveLines — nội dung hộp cảnh báo rời trang thanh toán (FR-BKG-01, AC-BKG-20)', () => {
  it('giỏ: chỉ mất thông tin đã nhập, các dịch vụ vẫn ở trong giỏ', () => {
    expect(leaveLines(cartItems, 'cart', cartItems)).toEqual({
      lose: ['Họ tên và ngày sinh hành khách đã nhập sẽ bị xoá.'],
      keep: ['1 dịch vụ trong giỏ hàng vẫn được giữ nguyên.'],
    });
  });

  it('đơn nháp chỉ có khách sạn: phòng không được giữ, không có gì còn lại trong giỏ', () => {
    const lines = leaveLines(only('hotel'), 'draft', []);
    expect(lines.lose).toEqual([
      'Lucky Sun Hotel Nha Trang Beach – Phòng Deluxe 3 Người không được giữ lại. Bạn phải chọn lại phòng và giá có thể đã đổi.',
      'Họ tên và ngày sinh hành khách đã nhập sẽ bị xoá.',
    ]);
    expect(lines.keep).toEqual([]);
  });

  it('đơn nháp có vé máy bay: nêu chuyến bay kèm ngày và cả giấy tờ đã nhập', () => {
    const lines = leaveLines(only('flight'), 'draft', []);
    expect(lines.lose[0]).toBe('Chuyến bay VietJet Air VJ601 Nha Trang → TP. Hồ Chí Minh 16:20 ngày 19/10/2026 không được giữ lại. Bạn phải tìm lại chuyến và giá có thể đã đổi.');
    expect(lines.lose[1]).toBe('Họ tên, ngày sinh và giấy tờ hành khách đã nhập sẽ bị xoá.');
  });

  it('đơn nháp có vé tham quan: ghi vẫn trong giỏ khi giỏ có đúng sản phẩm và ngày đó, hoặc khi giỏ chưa tải được', () => {
    const tour = only('attraction');
    expect(leaveLines(tour, 'draft', cartItems).keep).toHaveLength(1);
    expect(leaveLines(tour, 'draft', null).keep).toHaveLength(1);
    expect(leaveLines(tour, 'draft', cartItems).keep[0]).toContain('ngày 18/10/2026 vẫn nằm trong giỏ hàng');
  });

  it('không hứa "vẫn trong giỏ" khi giỏ không còn mục đó (đã xoá ở tab khác)', () => {
    expect(leaveLines(only('attraction'), 'draft', []).keep).toEqual([]);
    const otherDay = cartItems.map((item) => ({ ...item, usingDate: '2026-10-20' }));
    expect(leaveLines(only('attraction'), 'draft', otherDay).keep).toEqual([]);
  });
});
