/**
 * Bộ đếm khách của hộp đặt (trang chi tiết) và của nút [Sửa] ở giỏ (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §6.9).
 *
 * Phản chiếu R-CRT-01…05 (§5.5) để chặn ngay ở nút bấm: có ≥ 1 người lớn, tối đa 9 khách mỗi mục, khách sạn mỗi phòng có ≥ 1
 * người lớn và không vượt sức chứa. Backend vẫn kiểm lại khi thêm/sửa mục giỏ và quyết định. Code thuần để test được.
 *
 * Trạng thái là `CartState`: `guests` = người lớn và trẻ em; `quantity` = số phòng (khách sạn), số gói (combo), hoặc tổng số
 * khách (dịch vụ tính theo người, luôn bằng adults + children).
 */
import type { CartState } from './allocation';
import { MAX_PARTY } from './checkoutRules';

export type GuestMode = 'person' | 'hotel' | 'package';
export type CounterKind = 'adults' | 'children' | 'quantity';

/** Số gói tối đa của combo (giữ như bộ đếm số lượng cũ ở trang chi tiết). */
export const MAX_PACKAGES = 20;

export function guestModeOf(taxonomy: string): GuestMode {
  if (taxonomy === 'hotel') return 'hotel';
  if (taxonomy === 'combo') return 'package';
  return 'person'; // vé máy bay, vé tham quan, golf
}

/** Sức chứa mỗi phòng (`attributes.maxOccupancy`), hoặc null khi khách sạn chưa công bố. */
export function maxOccupancyFromAttributes(attributes: Record<string, unknown> | null | undefined): number | null {
  const value = attributes?.maxOccupancy;
  return typeof value === 'number' && value >= 1 ? value : null;
}

export const totalGuests = (state: CartState): number => state.guests.adults + state.guests.children;

/** Khởi đầu khi khách chưa chọn: 1 người lớn, 1 phòng hoặc 1 gói. */
export function initialCounts(): CartState {
  return { quantity: 1, guests: { adults: 1, children: 0 } };
}

/** Dịch vụ tính theo người: `quantity` luôn bằng số khách. */
export function normalizeCounts(mode: GuestMode, state: CartState): CartState {
  return mode === 'person' ? { ...state, quantity: totalGuests(state) } : state;
}

export function canChange(mode: GuestMode, state: CartState, kind: CounterKind, delta: 1 | -1): boolean {
  const { adults, children } = state.guests;
  const total = adults + children;
  if (kind === 'quantity') {
    if (mode === 'person') return false;
    if (delta < 0) return state.quantity > 1;
    // Khách sạn: mỗi phòng thêm cần một người lớn, tự thêm nếu chưa đủ; nên phải còn chỗ trong 9 khách.
    if (mode === 'hotel') return state.quantity < MAX_PARTY && (adults >= state.quantity + 1 || total < MAX_PARTY);
    return state.quantity < MAX_PACKAGES;
  }
  if (mode === 'package') return false; // combo: khách chỉ để ghi nhận, bộ đếm chỉ chỉnh số gói
  if (kind === 'adults') return delta > 0 ? total < MAX_PARTY : adults > (mode === 'hotel' ? state.quantity : 1);
  return delta > 0 ? total < MAX_PARTY : children > 0;
}

/** Áp một lần bấm − hoặc +; nút bị chặn thì trả nguyên trạng thái. */
export function changeCount(mode: GuestMode, state: CartState, kind: CounterKind, delta: 1 | -1): CartState {
  if (!canChange(mode, state, kind, delta)) return state;
  let { adults, children } = state.guests;
  let { quantity } = state;
  if (kind === 'adults') adults += delta;
  else if (kind === 'children') children += delta;
  else quantity += delta;
  if (mode === 'hotel' && kind === 'quantity' && delta > 0 && adults < quantity) adults = quantity;
  return normalizeCounts(mode, { quantity, guests: { adults, children } });
}

/** Khách sạn có sức chứa: số khách vượt `C × số phòng` thì cần thêm phòng. */
export function capacityIssue(mode: GuestMode, state: CartState, maxOccupancy: number | null): { capacity: number; suggestedRooms: number } | null {
  if (mode !== 'hotel' || !maxOccupancy) return null;
  const total = totalGuests(state);
  if (total <= maxOccupancy * state.quantity) return null;
  return { capacity: maxOccupancy * state.quantity, suggestedRooms: Math.ceil(total / maxOccupancy) };
}

/** Đủ điều kiện gửi lên Backend (khớp R-CRT-01, R-CRT-03). */
export function isValidCounts(mode: GuestMode, state: CartState, maxOccupancy: number | null): boolean {
  const { adults } = state.guests;
  if (adults < 1 || totalGuests(state) > MAX_PARTY || state.quantity < 1) return false;
  if (mode === 'hotel' && (adults < state.quantity || capacityIssue(mode, state, maxOccupancy))) return false;
  return true;
}

/** Phần body gửi `POST`/`PATCH /cart/items`: combo chỉ gửi số gói; còn lại gửi cả `guests`. */
export function cartPayload(mode: GuestMode, state: CartState): { quantity: number; guests?: { adults: number; children: number } } {
  return mode === 'package' ? { quantity: state.quantity } : { quantity: state.quantity, guests: state.guests };
}

/** Câu tóm tắt đoàn: "2 người lớn · 1 trẻ em". */
export function guestsText(guests: { adults: number; children: number }): string {
  return guests.children ? `${guests.adults} người lớn · ${guests.children} trẻ em` : `${guests.adults} người lớn`;
}

/**
 * Trợ lý (spec §6.9): đoàn của lịch trình (`intent.party`) → số lượng và `guests` khi thêm một mục vào giỏ.
 * - Dịch vụ tính theo người: `guests = party`, số lượng bằng tổng số khách.
 * - Khách sạn: `min(người lớn, max(1, ⌈khách / C⌉))` phòng; hạng phòng không có sức chứa C thì 1 phòng. Nếu vẫn vượt sức chứa,
 *   Backend từ chối mục đó và toast tổng kết báo tên mục.
 * - Combo: `guests = party`, 1 gói.
 * Đoàn được kéo về giới hạn của giỏ (≥ 1 người lớn, tối đa 9 khách) để một lịch trình đông người không làm cả nhóm bị từ chối.
 */
export function partyCartRequest(
  taxonomy: string, party: { adults: number; children: number }, maxOccupancy: number | null,
): { quantity: number; guests: { adults: number; children: number } } {
  const adults = Math.min(MAX_PARTY, Math.max(1, Math.trunc(party.adults) || 1));
  const children = Math.max(0, Math.min(MAX_PARTY - adults, Math.trunc(party.children) || 0));
  const guests = { adults, children };
  const total = adults + children;
  switch (guestModeOf(taxonomy)) {
    case 'person': return { quantity: total, guests };
    case 'package': return { quantity: 1, guests };
    default: return { quantity: maxOccupancy ? Math.min(adults, Math.max(1, Math.ceil(total / maxOccupancy))) : 1, guests };
  }
}
