/**
 * Bộ đếm khách của hộp đặt (trang chi tiết) và của nút [Sửa] ở giỏ (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §6.9).
 *
 * Phản chiếu R-CRT-01…05 (§5.5) để chặn ngay ở nút bấm: có ≥ 1 người lớn, tối đa 9 khách mỗi mục (khách sạn: 9 khách mỗi phòng,
 * tối đa 9 phòng), khách sạn mỗi phòng có ≥ 1 người lớn và không vượt sức chứa. Backend vẫn kiểm lại khi thêm/sửa mục giỏ và quyết định. Code thuần để test được.
 *
 * Trạng thái là `CartState`: `guests` = người lớn và trẻ em; `quantity` = số phòng (khách sạn), số gói (combo), hoặc tổng số
 * khách (dịch vụ tính theo người, luôn bằng adults + children).
 */
import type { CartState } from './allocation';
import { MAX_PARTY, MAX_ROOMS, itemPartyCap, roomCapacity } from './checkoutRules';

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
    // Bớt phòng khi số khách còn vượt trần của số phòng sau khi bớt thì bị chặn (khách sạn: 9 khách mỗi phòng).
    if (delta < 0) return state.quantity > 1 && (mode !== 'hotel' || total <= itemPartyCap('hotel', state.quantity - 1));
    // Khách sạn: mỗi phòng thêm cần một người lớn, tự thêm nếu chưa đủ; nên phải còn chỗ trong trần của số phòng mới.
    if (mode === 'hotel') {
      return state.quantity < MAX_ROOMS && (adults >= state.quantity + 1 || total < itemPartyCap('hotel', state.quantity + 1));
    }
    return state.quantity < MAX_PACKAGES;
  }
  if (mode === 'package') return false; // combo: khách chỉ để ghi nhận, bộ đếm chỉ chỉnh số gói
  const cap = itemPartyCap(mode === 'hotel' ? 'hotel' : 'person', state.quantity);
  if (kind === 'adults') return delta > 0 ? total < cap : adults > (mode === 'hotel' ? state.quantity : 1);
  return delta > 0 ? total < cap : children > 0;
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

/** Khách sạn có sức chứa: số khách vượt `C × số phòng` thì cần thêm phòng (C không quá 9, FR-BKG-08). */
export function capacityIssue(mode: GuestMode, state: CartState, maxOccupancy: number | null): { capacity: number; suggestedRooms: number } | null {
  if (mode !== 'hotel' || !maxOccupancy) return null;
  const perRoom = roomCapacity(maxOccupancy);
  const total = totalGuests(state);
  if (total <= perRoom * state.quantity) return null;
  return { capacity: perRoom * state.quantity, suggestedRooms: Math.ceil(total / perRoom) };
}

/** Đủ điều kiện gửi lên Backend (khớp R-CRT-01, R-CRT-03). */
export function isValidCounts(mode: GuestMode, state: CartState, maxOccupancy: number | null): boolean {
  const { adults } = state.guests;
  if (adults < 1 || totalGuests(state) > itemPartyCap(mode === 'hotel' ? 'hotel' : 'person', state.quantity) || state.quantity < 1) return false;
  if (mode === 'hotel' && (state.quantity > MAX_ROOMS || adults < state.quantity || capacityIssue(mode, state, maxOccupancy))) return false;
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
 * Trợ lý (spec §6.9): đoàn của lịch trình (`intent.party`) → số lượng và `guests` khi thêm một mục vào giỏ hoặc Đặt ngay.
 * - Dịch vụ tính theo người: `guests = party`, số lượng bằng tổng số khách.
 * - Khách sạn: `min(người lớn, 9, ⌈khách / C⌉)` phòng (ít nhất 1), C là sức chứa mỗi phòng và không quá 9, hạng phòng không có
 *   sức chứa thì C = 9. Nếu vẫn vượt sức chứa, Backend từ chối mục đó và toast tổng kết báo tên mục.
 * - Combo: `guests = party`, 1 gói.
 * Đoàn được kéo về giới hạn (≥ 1 người lớn, tối đa 9 khách; khách sạn 9 khách mỗi phòng) để một lịch trình đông người không làm
 * cả nhóm bị từ chối.
 */
export function partyCartRequest(
  taxonomy: string, party: { adults: number; children: number }, maxOccupancy: number | null,
): { quantity: number; guests: { adults: number; children: number } } {
  const clamp = (cap: number) => {
    const adults = Math.min(cap, Math.max(1, Math.trunc(party.adults) || 1));
    return { adults, children: Math.max(0, Math.min(cap - adults, Math.trunc(party.children) || 0)) };
  };
  const mode = guestModeOf(taxonomy);
  if (mode === 'hotel') {
    const wanted = clamp(MAX_PARTY * MAX_ROOMS);
    const rooms = Math.min(wanted.adults, MAX_ROOMS, Math.max(1, Math.ceil((wanted.adults + wanted.children) / roomCapacity(maxOccupancy))));
    return { quantity: rooms, guests: clamp(itemPartyCap('hotel', rooms)) };
  }
  const guests = clamp(MAX_PARTY);
  return { quantity: mode === 'package' ? 1 : guests.adults + guests.children, guests };
}
