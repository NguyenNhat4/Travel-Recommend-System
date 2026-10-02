/**
 * Đoàn khách và phân bổ theo dịch vụ ở phía Web (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §6.4–§6.6).
 *
 * Code thuần: dựng đoàn mặc định từ giỏ, phân bổ mặc định (§6.5), đếm số người lớn/trẻ em theo loại giá tại ngày của từng
 * dịch vụ và đổi phân bổ thành `guests` để `PATCH /cart/items`. Không có số tiền nào ở đây: tiền luôn từ `CartResponse`.
 */
import type { ApiCartItem } from '../../services/booking';
import {
  MAX_PARTY, fareTypeOn, isInfantOn, isValidNamePart, normalizeName, parseDmy, splitFullName,
  type CartFacts, type ContactInput, type DocType, type ItemInput, type Traveler, type TravelerInput, type TravelerKind,
} from './checkoutRules';
import { maxOccupancyFromAttributes } from './guestCounts';

export interface TravelerDraft {
  ref: string;
  type: TravelerKind;
  surname: string;
  givenNames: string;
  /** Ô ngày sinh người dùng gõ (`dd/mm/yyyy`); trẻ em, và người lớn khi giỏ có vé máy bay. */
  birthText: string;
  /** Thông tin hãng bay yêu cầu (FR-BKG-13); chỉ gửi khi giỏ có vé máy bay. */
  flight: FlightDraft;
}

/** Các ô của khối "Thông tin cho vé máy bay". Ô ngày gõ dạng `dd/mm/yyyy`. */
export interface FlightDraft {
  title: string;
  nationality: string;
  docType: DocType;
  docNumber: string;
  docExpiryText: string;
  /** `travelerRef` của người lớn đi kèm em bé. */
  escortRef: string;
}

export const blankFlight = (): FlightDraft => ({ title: '', nationality: 'VN', docType: 'CCCD', docNumber: '', docExpiryText: '', escortRef: '' });

export interface RoomDraft {
  refs: string[];
  lead: string | null;
}

export interface Allocation {
  /** Dịch vụ tính theo người và combo. */
  refs: string[];
  /** Khách sạn. */
  rooms: RoomDraft[];
  /** Khách đã tự chỉnh: không tính lại mặc định khi đoàn đổi (§6.5). */
  custom: boolean;
}

export const isHotel = (item: ApiCartItem) => item.product.taxonomy === 'hotel';
export const PER_PERSON = ['flight', 'attraction', 'golf'];

export function maxOccupancyOf(item: ApiCartItem): number | null {
  return maxOccupancyFromAttributes(item.product.attributes as Record<string, unknown> | undefined);
}

export function guestsOfItem(item: ApiCartItem): { adults: number; children: number } {
  return item.guests ?? { adults: item.quantity, children: 0 };
}

export function cartFactsOf(item: ApiCartItem): CartFacts {
  return {
    cartItemId: item.cartItemId, name: item.product.name, taxonomy: item.product.taxonomy, usingDate: item.usingDate,
    quantity: item.quantity, guests: guestsOfItem(item), maxOccupancy: maxOccupancyOf(item),
  };
}

// --- đoàn khách ---------------------------------------------------------------------------------------

export function draftToTraveler(d: TravelerDraft): Traveler {
  const surname = normalizeName(d.surname);
  const givenNames = normalizeName(d.givenNames);
  return {
    ref: d.ref, type: d.type, surname, givenNames, fullName: `${surname} ${givenNames}`.trim(),
    birth: d.type === 'CHILD' ? parseDmy(d.birthText) : null,
    escortRef: d.type === 'CHILD' ? (d.flight.escortRef || null) : null,
  };
}

/** Ngày hợp lệ theo lịch thì gửi dạng ISO; người dùng gõ dở thì giữ chuỗi thô để luật báo lỗi của đúng trường. */
const isoOrRaw = (text: string): string | null => parseDmy(text) ?? (text.trim() || null);

/**
 * Đoàn khách dạng request. `withFlight` (giỏ có vé máy bay) thì thêm ngày sinh người lớn và khối `documents` (FR-BKG-13);
 * không có vé bay thì không gửi giấy tờ, dù khách đã nhập trước đó.
 */
export function toTravelerInputs(drafts: TravelerDraft[], withFlight = false): TravelerInput[] {
  return drafts.map((d) => {
    const base: TravelerInput = {
      travelerRef: d.ref, type: d.type, surname: d.surname, givenNames: d.givenNames,
      birthDate: d.type === 'CHILD' || withFlight ? isoOrRaw(d.birthText) : null,
    };
    if (!withFlight) return base;
    const f = d.flight;
    const adult = d.type === 'ADULT';
    return {
      ...base,
      // Trường trống thì bỏ khỏi request: Backend báo REQUIRED đúng trường, không gửi `null` cho kiểu enum của contract.
      documents: {
        ...(f.title ? { title: f.title } : {}),
        ...(f.nationality ? { nationality: f.nationality } : {}),
        ...(adult ? {
          docType: f.docType,
          ...(f.docNumber.trim() ? { docNumber: f.docNumber.trim() } : {}),
          ...(f.docType === 'PASSPORT' && f.docExpiryText.trim() ? { docExpiry: isoOrRaw(f.docExpiryText) } : {}),
        } : {}),
        ...(!adult && f.escortRef ? { escortTravelerRef: f.escortRef } : {}),
      },
    };
  });
}

/** Tên in trên vé: họ / tên đệm và tên, không dấu, viết hoa (ví dụ `NGUYEN / MINH ANH`). */
export function ticketName(d: Pick<TravelerDraft, 'surname' | 'givenNames'>): string {
  const ascii = (v: string) => normalizeName(v).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toUpperCase();
  return `${ascii(d.surname) || '—'} / ${ascii(d.givenNames) || '—'}`;
}

/** Tên hiển thị: họ và tên đã nối; chưa nhập thì nhãn "Người lớn 1". */
export function travelerLabel(d: TravelerDraft, drafts: TravelerDraft[]): string {
  const same = drafts.filter((x) => x.type === d.type);
  return `${d.type === 'ADULT' ? 'Người lớn' : 'Trẻ em'} ${same.indexOf(d) + 1}`;
}

export function displayName(d: TravelerDraft, drafts: TravelerDraft[]): string {
  return normalizeName(`${d.surname} ${d.givenNames}`) || travelerLabel(d, drafts);
}

/** Tên ngắn cho chip: hai từ cuối của họ tên (tránh chip dài). */
export function shortName(d: TravelerDraft, drafts: TravelerDraft[]): string {
  const words = normalizeName(`${d.surname} ${d.givenNames}`).split(' ').filter(Boolean);
  if (!words.length) return travelerLabel(d, drafts);
  return words.length >= 3 ? words.slice(-2).join(' ') : words.join(' ');
}

export function partyCounts(drafts: TravelerDraft[]): { adults: number; children: number } {
  const adults = drafts.filter((d) => d.type === 'ADULT').length;
  return { adults, children: drafts.length - adults };
}

export function partyText(drafts: TravelerDraft[]): string {
  const { adults, children } = partyCounts(drafts);
  return `${adults} người lớn${children ? ` · ${children} trẻ em` : ''}`;
}

/** Đoàn mặc định khi mở `/checkout` (§6.5): lớn nhất của `guests` theo từng loại trong mọi mục giỏ, ít nhất 1 người lớn. */
export function defaultParty(items: ApiCartItem[]): { adults: number; children: number } {
  let adults = 1;
  let children = 0;
  for (const item of items) {
    const g = guestsOfItem(item);
    adults = Math.max(adults, g.adults);
    children = Math.max(children, g.children);
  }
  adults = Math.min(adults, MAX_PARTY);
  return { adults, children: Math.min(children, MAX_PARTY - adults) };
}

/**
 * Đoàn mặc định (spec §6.5): họ tên Người lớn 1 lấy từ tài khoản, các ô khác để trống. Tên tài khoản không dùng được làm họ tên
 * trên giấy tờ (có chữ số, ký hiệu, quá dài, hoặc chỉ một từ) thì để trống cả hai ô, thay vì điền sẵn một giá trị sẽ bị báo lỗi.
 */
export function newDrafts(party: { adults: number; children: number }, accountName: string): { drafts: TravelerDraft[]; seq: number } {
  const [accountSurname, accountGiven] = splitFullName(accountName);
  const usable = isValidNamePart(accountSurname) && isValidNamePart(accountGiven);
  const [surname, givenNames] = usable ? [accountSurname, accountGiven] : ['', ''];
  const drafts: TravelerDraft[] = [];
  let seq = 0;
  for (let i = 0; i < party.adults; i += 1) {
    seq += 1;
    drafts.push({ ref: `t${seq}`, type: 'ADULT', surname: i === 0 ? surname : '', givenNames: i === 0 ? givenNames : '', birthText: '', flight: blankFlight() });
  }
  for (let i = 0; i < party.children; i += 1) {
    seq += 1;
    drafts.push({ ref: `t${seq}`, type: 'CHILD', surname: '', givenNames: '', birthText: '', flight: blankFlight() });
  }
  return { drafts, seq };
}

// --- phân bổ ----------------------------------------------------------------------------------------------

function isAdultOn(d: TravelerDraft, day: string): boolean {
  return fareTypeOn(draftToTraveler(d), day) === 'ADULT';
}

/** Người lớn đầu tiên trong phòng (theo loại giá tại ngày nhận phòng) làm người đại diện. */
function firstAdult(refs: string[], drafts: TravelerDraft[], day: string): string | null {
  return refs.find((ref) => { const d = drafts.find((x) => x.ref === ref); return d && isAdultOn(d, day); }) ?? null;
}

export function fixLead(room: RoomDraft, drafts: TravelerDraft[], day: string): RoomDraft {
  const ok = room.lead && room.refs.includes(room.lead) && (() => {
    const d = drafts.find((x) => x.ref === room.lead);
    return d ? isAdultOn(d, day) : false;
  })();
  return ok ? room : { ...room, lead: firstAdult(room.refs, drafts, day) };
}

/**
 * Phân phòng mặc định (§6.5): (1) mỗi phòng một người lớn theo thứ tự trong đoàn; (2) người lớn còn lại rồi trẻ em xếp xoay
 * vòng vào các phòng còn chỗ; (3) người đại diện là người lớn đầu tiên trong phòng. Hạng phòng không có sức chứa thì không
 * giới hạn. Ít người lớn hơn số phòng thì có phòng trống (thẻ báo R-HTL-02).
 */
export function defaultRooms(drafts: TravelerDraft[], rooms: number, capacity: number | null, day: string): RoomDraft[] {
  const limit = capacity ?? Number.POSITIVE_INFINITY;
  const out: RoomDraft[] = Array.from({ length: rooms }, () => ({ refs: [], lead: null }));
  const adults = drafts.filter((d) => isAdultOn(d, day)).map((d) => d.ref);
  const rest = drafts.filter((d) => !isAdultOn(d, day)).map((d) => d.ref);
  const queue: string[] = [];
  adults.forEach((ref, i) => { if (i < rooms) out[i].refs.push(ref); else queue.push(ref); });
  queue.push(...rest);
  let next = 0;
  for (const ref of queue) {
    for (let n = 0; n < rooms; n += 1) {
      const index = (next + n) % rooms;
      if (out[index].refs.length < limit) {
        out[index].refs.push(ref);
        next = (index + 1) % rooms;
        break;
      }
    }
  }
  return out.map((room) => fixLead(room, drafts, day));
}

export function defaultAllocation(item: ApiCartItem, drafts: TravelerDraft[]): Allocation {
  if (!isHotel(item)) return { refs: drafts.map((d) => d.ref), rooms: [], custom: false };
  return { refs: [], rooms: defaultRooms(drafts, Math.max(1, item.quantity), maxOccupancyOf(item), item.usingDate), custom: false };
}

/** Sau khi đoàn đổi: mục chưa chỉnh tính lại mặc định; mục đã chỉnh chỉ bỏ những người đã rời đoàn (§6.5). */
export function reconcileAllocation(item: ApiCartItem, alloc: Allocation, drafts: TravelerDraft[]): Allocation {
  if (!alloc.custom) {
    const rooms = isHotel(item) ? Math.max(1, alloc.rooms.length || item.quantity) : 0;
    return isHotel(item)
      ? { refs: [], rooms: defaultRooms(drafts, rooms, maxOccupancyOf(item), item.usingDate), custom: false }
      : { refs: drafts.map((d) => d.ref), rooms: [], custom: false };
  }
  const alive = new Set(drafts.map((d) => d.ref));
  return {
    custom: true,
    refs: alloc.refs.filter((ref) => alive.has(ref)),
    rooms: alloc.rooms.map((room) => fixLead({ ...room, refs: room.refs.filter((ref) => alive.has(ref)) }, drafts, item.usingDate)),
  };
}

export function refsOf(item: ApiCartItem, alloc: Allocation): string[] {
  return isHotel(item) ? alloc.rooms.flatMap((r) => r.refs) : alloc.refs;
}

/** Người trong đoàn chưa có phòng nào (khách sạn). */
export function unassignedRefs(item: ApiCartItem, alloc: Allocation, drafts: TravelerDraft[]): string[] {
  const inRoom = new Set(refsOf(item, alloc));
  return drafts.filter((d) => !inRoom.has(d.ref)).map((d) => d.ref);
}

/** Số người lớn và trẻ em của một mục theo loại giá tại ngày sử dụng của mục. */
export function guestsFromAllocation(item: ApiCartItem, alloc: Allocation, drafts: TravelerDraft[]): { adults: number; children: number } {
  const refs = new Set(refsOf(item, alloc));
  let adults = 0;
  let children = 0;
  for (const d of drafts) {
    if (!refs.has(d.ref)) continue;
    if (isAdultOn(d, item.usingDate)) adults += 1; else children += 1;
  }
  return { adults, children };
}

export function isInfantForItem(d: TravelerDraft, item: ApiCartItem): boolean {
  return isInfantOn(draftToTraveler(d), item.usingDate);
}

/** Số lượng và số khách của một mục giỏ: phần mà bước ② ghi vào giỏ qua `PATCH /cart/items/{id}`. */
export interface CartState {
  quantity: number;
  guests: { adults: number; children: number };
}

/**
 * Trạng thái giỏ mong muốn của một mục sau khi phân bổ, hoặc null khi phân bổ chưa đủ điều kiện để ghi vào giỏ (chưa có người
 * lớn, mỗi phòng chưa có một người lớn, vượt sức chứa): thẻ dịch vụ báo lỗi và nút Tiếp tục chặn, chưa cần gọi PATCH.
 */
export function desiredCartState(item: ApiCartItem, alloc: Allocation, drafts: TravelerDraft[]): CartState | null {
  const guests = guestsFromAllocation(item, alloc, drafts);
  if (guests.adults < 1 || guests.adults + guests.children > MAX_PARTY) return null;
  if (isHotel(item)) {
    const rooms = alloc.rooms.length;
    const cap = maxOccupancyOf(item);
    if (rooms < 1 || guests.adults < rooms || (cap && guests.adults + guests.children > cap * rooms)) return null;
    return { quantity: rooms, guests };
  }
  if (PER_PERSON.includes(item.product.taxonomy)) return { quantity: guests.adults + guests.children, guests };
  return { quantity: item.quantity, guests }; // combo: số gói giữ như trong giỏ
}

export function cartStateOf(item: ApiCartItem): CartState {
  return { quantity: item.quantity, guests: guestsOfItem(item) };
}

export function sameCartState(a: CartState, b: CartState): boolean {
  return a.quantity === b.quantity && a.guests.adults === b.guests.adults && a.guests.children === b.guests.children;
}

// --- payload -------------------------------------------------------------------------------------------------

export function itemInputsOf(
  items: ApiCartItem[], allocs: Record<string, Allocation>, drafts: TravelerDraft[],
): ItemInput[] {
  const order = new Map(drafts.map((d, i) => [d.ref, i]));
  const inPartyOrder = (refs: string[]) => [...refs].sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0));
  return items.map((item) => {
    const alloc = allocs[item.cartItemId];
    if (!alloc) return { cartItemId: item.cartItemId };
    if (isHotel(item)) {
      return { cartItemId: item.cartItemId, rooms: alloc.rooms.map((r) => ({ travelerRefs: inPartyOrder(r.refs), leadTravelerRef: r.lead })) };
    }
    return { cartItemId: item.cartItemId, travelerRefs: inPartyOrder(alloc.refs) };
  });
}

export function contactInputOf(fullName: string, phone: string, email: string): ContactInput {
  return { fullName, phone, email };
}
