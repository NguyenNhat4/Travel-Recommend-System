/**
 * Ước tính dòng giá để HIỂN THỊ trước khi có `CartResponse` (hộp đặt ở trang chi tiết). Giá chính thức luôn là `fares` và
 * `lineTotal` do Backend trả về; Web không bao giờ gửi số tiền đi (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §4.3, §4.4).
 *
 * Phản chiếu `domain/booking/fares.py`; hai phía chạy chung mục `fares` của
 * `src/shared/contracts/tests/booking-rules-cases.json`.
 */
import type { components } from '../../types/api.gen';

export type FareLine = components['schemas']['FareLine'];

/** Chỉ vé tham quan và golf có giá trẻ em riêng trong catalog (D2). Bay: mọi khách một giá (D3); combo: theo gói (D4). */
const CHILD_PRICED = ['attraction', 'golf'];

/**
 * Giá vé trẻ em hợp lệ, hoặc null khi trẻ em trả giá người lớn. Hợp lệ khi `attributes.childPrice` là số và
 * 0 < childPrice ≤ unitPrice: giá 0 nghĩa là nguồn không có giá riêng (không phải miễn phí); giá cao hơn người lớn nhiều khả
 * năng là lỗi dữ liệu.
 */
export function childUnitPrice(taxonomy: string, unitPrice: number, attributes?: Record<string, unknown> | null): number | null {
  if (!CHILD_PRICED.includes(taxonomy)) return null;
  const raw = attributes?.childPrice;
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return null;
  const price = Math.round(raw);
  return price > 0 && price <= unitPrice ? price : null;
}

const line = (fareType: FareLine['fareType'], unitPrice: number, count: number, nights: number | null = null): FareLine => ({
  fareType, unitPrice, count, nights, amount: unitPrice * count * (nights ?? 1),
});

export function estimateFares(input: {
  taxonomy: string; unitPrice: number; attributes?: Record<string, unknown> | null;
  quantity: number; nights: number | null; adults: number; children: number;
}): { lines: FareLine[]; total: number } {
  const { taxonomy, unitPrice } = input;
  let lines: FareLine[];
  if (taxonomy === 'hotel') lines = [line('ROOM', unitPrice, input.quantity, Math.max(1, input.nights ?? 1))];
  else if (taxonomy === 'combo') lines = [line('PACKAGE', unitPrice, input.quantity)];
  else {
    lines = [line('ADULT', unitPrice, input.adults)];
    if (input.children) lines.push(line('CHILD', childUnitPrice(taxonomy, unitPrice, input.attributes) ?? unitPrice, input.children));
  }
  return { lines, total: lines.reduce((sum, l) => sum + l.amount, 0) };
}
