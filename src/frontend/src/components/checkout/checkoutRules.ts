/**
 * Bộ luật kiểm đoàn khách, phân bổ theo dịch vụ và số khách của giỏ (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §5).
 *
 * Web kiểm để báo lỗi sớm, ngay tại trường; Backend (`domain/booking/party_rules.py`) kiểm lại toàn bộ và có quyết định cuối
 * cùng. Hai phía chạy CÙNG MỘT bộ ca kiểm thử (`src/shared/contracts/tests/booking-rules-cases.json`): mã luật, `reason`,
 * đường dẫn trường và câu thông báo phải giống hệt nhau. Sửa luật ở đây thì phải sửa cả bên Python.
 *
 * Code thuần, không import React. Ngày là chuỗi `YYYY-MM-DD` (theo lịch Việt Nam), không đi qua `Date` để tránh lệch múi giờ.
 */

export const MAX_PARTY = 9; // tối đa mỗi mục (vé, golf, combo, chuyến bay) và mỗi phòng khách sạn (FR-BKG-08)
export const MAX_ROOMS = 9; // số phòng tối đa của một mục khách sạn

/** Số khách tối đa của một phòng: sức chứa của hạng phòng nếu có, và không quá `MAX_PARTY`. */
export function roomCapacity(maxOccupancy: number | null): number {
  return maxOccupancy ? Math.min(maxOccupancy, MAX_PARTY) : MAX_PARTY;
}

/** Số khách tối đa của một mục: khách sạn 9 khách mỗi phòng, loại khác 9 khách. */
export function itemPartyCap(taxonomy: string, quantity: number): number {
  return taxonomy === 'hotel' ? MAX_PARTY * Math.max(quantity, 1) : MAX_PARTY;
}

/**
 * Trần của đoàn khai ở checkout, từ `taxonomy` và `quantity` của các mục trong đơn: đơn chỉ có khách sạn thì theo mục lớn nhất,
 * đơn có mục khác thì `MAX_PARTY`. Phản chiếu `order_party_cap` ở Backend.
 */
export function orderPartyCap(items: Array<{ taxonomy: string; quantity: number }>): number {
  if (!items.length || items.some((i) => i.taxonomy !== 'hotel')) return MAX_PARTY;
  return Math.max(...items.map((i) => itemPartyCap(i.taxonomy, i.quantity)));
}
export const ADULT_MIN_AGE = 12;
export const INFANT_MAX_AGE = 2; // dưới 2 tuổi
const NAME_PART_MAX = 50;
const CONTACT_NAME_MAX = 100;
const PHONE_PATTERN = /^0[0-9]{9}$/;
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const ISO_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const LETTERS_ONLY = /^[\p{L}\p{M} '-]+$/u;
const CCCD_PATTERN = /^[0-9]{12}$/;
const PASSPORT_PATTERN = /^[A-Za-z0-9]{6,9}$/;
export const TITLES: Record<TravelerKind, readonly string[]> = { ADULT: ['MR', 'MRS', 'MS'], CHILD: ['MSTR', 'MISS'] };
export const NATIONALITIES = ['VN', 'KR', 'CN', 'JP', 'US', 'AU', 'FR', 'OTHER'] as const;
export const DOC_TYPES = ['CCCD', 'PASSPORT'] as const;

export type TravelerKind = 'ADULT' | 'CHILD';
export type DocType = (typeof DOC_TYPES)[number];
export type FareKind = 'ADULT' | 'CHILD';

export interface Violation {
  field: string;
  reason: string;
  /** Có khi vi phạm thuộc một mục giỏ, để gắn lỗi vào đúng thẻ dịch vụ. */
  cartItemId?: string;
  params?: Record<string, string | number>;
}

export interface ContactInput {
  fullName: string;
  email: string;
  phone: string;
}

/** `travelers[i].documents` (FR-BKG-13): chuỗi thô, giá trị sai là vi phạm chứ không phải lỗi kiểu dữ liệu. */
export interface DocumentsInput {
  title?: string | null;
  nationality?: string | null;
  docType?: string | null;
  docNumber?: string | null;
  /** `YYYY-MM-DD`; chỉ hộ chiếu. */
  docExpiry?: string | null;
  /** Chỉ em bé: `travelerRef` của người lớn đi kèm. */
  escortTravelerRef?: string | null;
}

export interface TravelerInput {
  travelerRef: string;
  type: TravelerKind;
  surname: string;
  givenNames: string;
  /** `YYYY-MM-DD`; chuỗi khác (người dùng gõ dở) là BIRTH_DATE_INVALID. Người lớn không cần. */
  birthDate?: string | null;
  /** Bắt buộc khi giỏ có vé máy bay. */
  documents?: DocumentsInput | null;
}

export interface Traveler {
  ref: string;
  type: TravelerKind;
  surname: string;
  givenNames: string;
  /** Ngày sinh hợp lệ (trẻ em; người lớn khi giỏ có vé bay), hoặc null. */
  birth: string | null;
  fullName: string;
  /** `travelerRef` của người lớn đi kèm em bé (FR-BKG-13), hoặc null. */
  escortRef: string | null;
}

export interface RoomInput {
  travelerRefs: string[];
  leadTravelerRef: string | null;
}

export interface ItemInput {
  cartItemId: string;
  travelerRefs?: string[] | null;
  rooms?: RoomInput[] | null;
}

export interface CartFacts {
  cartItemId: string;
  name: string;
  taxonomy: string;
  usingDate: string;
  quantity: number;
  guests: { adults: number; children: number };
  maxOccupancy: number | null;
}

// --- ngày ------------------------------------------------------------------------------------------

type Ymd = [number, number, number];

const isLeap = (y: number) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;

function ymd(iso: string): Ymd {
  return [Number(iso.slice(0, 4)), Number(iso.slice(5, 7)), Number(iso.slice(8, 10))];
}

function cmp(a: Ymd, b: Ymd): number {
  return a[0] - b[0] || a[1] - b[1] || a[2] - b[2];
}

function toIso([y, m, d]: Ymd): string {
  return `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

/** `YYYY-MM-DD` hợp lệ theo lịch (không nhận 2019-02-30). */
export function isValidIso(value: string | null | undefined): value is string {
  if (!value || !ISO_PATTERN.test(value)) return false;
  const [y, m, d] = ymd(value);
  if (m < 1 || m > 12 || d < 1) return false;
  const days = [31, isLeap(y) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1];
  return d <= days;
}

/** Sinh nhật của năm `year`; 29/02 ở năm không nhuận coi là 01/03. */
function birthdayIn(birth: Ymd, year: number): Ymd {
  return birth[1] === 2 && birth[2] === 29 && !isLeap(year) ? [year, 3, 1] : [year, birth[1], birth[2]];
}

/** Số năm tròn của người sinh ngày `birth` vào ngày `day`. */
export function ageOn(birth: string, day: string): number {
  const b = ymd(birth);
  const d = ymd(day);
  const years = d[0] - b[0];
  return cmp(d, birthdayIn(b, d[0])) < 0 ? years - 1 : years;
}

/** Ngày trẻ tròn 12 tuổi và bắt đầu tính giá người lớn. */
export function adultFrom(birth: string): string {
  return toIso(birthdayIn(ymd(birth), ymd(birth)[0] + ADULT_MIN_AGE));
}

/** Loại giá của một người ở dịch vụ dùng vào ngày `day`. Trẻ em chưa có ngày sinh hợp lệ tính là trẻ em. */
export function fareTypeOn(traveler: Pick<Traveler, 'type' | 'birth'>, day: string): FareKind {
  if (traveler.type === 'ADULT') return 'ADULT';
  if (!traveler.birth) return 'CHILD';
  return ageOn(traveler.birth, day) >= ADULT_MIN_AGE ? 'ADULT' : 'CHILD';
}

export function isInfantOn(traveler: Pick<Traveler, 'type' | 'birth'>, day: string): boolean {
  return traveler.type === 'CHILD' && traveler.birth !== null && ageOn(traveler.birth, day) < INFANT_MAX_AGE;
}

export function formatDmy(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
}

/** `dd/mm/yyyy` do người dùng gõ → `YYYY-MM-DD` nếu hợp lệ theo lịch, ngược lại null. */
export function parseDmy(text: string): string | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text.trim());
  if (!m) return null;
  const iso = `${m[3]}-${m[2]}-${m[1]}`;
  return isValidIso(iso) && Number(m[3]) >= 1900 ? iso : null;
}

/** Ô ngày sinh tự chèn dấu `/` khi gõ số (bàn phím số); xoá thì để nguyên. */
export function maskDmy(previous: string, next: string): string {
  // Bấm xoá lùi từ cuối: giữ nguyên để không tự thêm lại dấu "/" vừa xoá. Dán đè một giá trị khác thì định dạng lại từ các chữ số.
  if (next.length < previous.length && previous.startsWith(next)) return next.replace(/[^\d/]/g, '');
  const digits = next.replace(/\D/g, '').slice(0, 8);
  if (digits.length > 4) return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
  if (digits.length > 2) return `${digits.slice(0, 2)}/${digits.slice(2)}${digits.length === 4 ? '/' : ''}`;
  return digits.length === 2 ? `${digits}/` : digits;
}

// --- tên ----------------------------------------------------------------------------------------------

/** Bỏ khoảng trắng thừa và chuẩn hoá Unicode về NFC. */
export function normalizeName(value: string | null | undefined): string {
  return (value ?? '').normalize('NFC').split(/\s+/).filter(Boolean).join(' ');
}

const codepoints = (value: string) => [...value].length;

/** Một phần họ tên hợp lệ: chỉ chữ cái (kể cả dấu), khoảng trắng, dấu nháy và gạch nối; tối đa 50 ký tự. Đã chuẩn hoá khoảng trắng. */
export function isValidNamePart(value: string): boolean {
  return codepoints(value) <= NAME_PART_MAX && LETTERS_ONLY.test(value);
}

export function splitFullName(full: string): [string, string] {
  const words = normalizeName(full).split(' ').filter(Boolean);
  return [words[0] ?? '', words.slice(1).join(' ')];
}

// --- bước ①: người liên hệ và đoàn khách ------------------------------------------------------------

/** R-CON-01. */
export function checkContact(contact: ContactInput): Violation[] {
  const out: Violation[] = [];
  const name = normalizeName(contact.fullName);
  if (!name) out.push({ field: 'contact.fullName', reason: 'REQUIRED' });
  else if (codepoints(name) > CONTACT_NAME_MAX) out.push({ field: 'contact.fullName', reason: 'NAME_INVALID' });
  const email = (contact.email ?? '').trim();
  if (!email) out.push({ field: 'contact.email', reason: 'REQUIRED' });
  else if (email.length > 254 || !EMAIL_PATTERN.test(email)) out.push({ field: 'contact.email', reason: 'EMAIL_INVALID' });
  const phone = (contact.phone ?? '').trim();
  if (!phone) out.push({ field: 'contact.phone', reason: 'REQUIRED' });
  else if (!PHONE_PATTERN.test(phone)) out.push({ field: 'contact.phone', reason: 'PHONE_INVALID' });
  return out;
}

/**
 * R-TRV-01…06, R-DOC-01…08. Trả về đoàn đã chuẩn hoá (để luật theo dịch vụ dùng tiếp) cùng danh sách vi phạm.
 * `flightDates` là ngày bay của các mục vé máy bay trong giỏ; rỗng thì không áp luật giấy tờ (FR-BKG-13). `maxParty` là trần
 * của đoàn (`orderPartyCap`), mặc định `MAX_PARTY`.
 */
export function checkParty(
  inputs: TravelerInput[], opts: { earliest: string | null; today: string; flightDates?: string[]; maxParty?: number },
): { travelers: Traveler[]; violations: Violation[] } {
  const flightDates = opts.flightDates ?? [];
  const maxParty = opts.maxParty ?? MAX_PARTY;
  const out: Violation[] = [];
  const travelers: Traveler[] = [];
  if (inputs.length > maxParty) out.push({ field: 'travelers', reason: 'PARTY_TOO_LARGE', params: { maxParty } });
  if (!inputs.some((t) => t.type === 'ADULT')) out.push({ field: 'travelers', reason: 'ADULT_REQUIRED', params: { scope: 'party' } });
  const seen = new Set<string>();
  inputs.forEach((item, index) => {
    const base = `travelers[${index}]`;
    if (seen.has(item.travelerRef)) out.push({ field: `${base}.travelerRef`, reason: 'TRAVELER_DUPLICATED' });
    seen.add(item.travelerRef);
    const surname = normalizeName(item.surname);
    const givenNames = normalizeName(item.givenNames);
    for (const [part, value] of [['surname', surname], ['givenNames', givenNames]] as const) {
      if (!value) out.push({ field: `${base}.${part}`, reason: 'REQUIRED', params: { part } });
      else if (!isValidNamePart(value)) out.push({ field: `${base}.${part}`, reason: 'NAME_INVALID' });
    }
    let birth: string | null = null;
    if (item.type === 'CHILD') {
      const raw = (item.birthDate ?? '').trim();
      if (!raw) out.push({ field: `${base}.birthDate`, reason: 'REQUIRED', params: { part: 'birthDate' } });
      else if (!isValidIso(raw) || raw > opts.today || (opts.earliest !== null && raw > opts.earliest)) {
        out.push({ field: `${base}.birthDate`, reason: 'BIRTH_DATE_INVALID' });
      } else {
        birth = raw;
        if (opts.earliest !== null && ageOn(raw, opts.earliest) >= ADULT_MIN_AGE) {
          out.push({ field: `${base}.birthDate`, reason: 'CHILD_AGE_INVALID', params: { turned12On: adultFrom(raw) } });
        }
      }
    } else if (flightDates.length) {
      birth = checkAdultBirth(item, base, [...flightDates].sort()[0], opts.today, out);
    }
    const documents = flightDates.length ? checkDocuments(item, base, flightDates, out) : null;
    travelers.push({
      ref: item.travelerRef, type: item.type, surname, givenNames, birth, fullName: `${surname} ${givenNames}`.trim(),
      escortRef: documents?.escortRef ?? null,
    });
  });
  if (flightDates.length) checkEscorts(travelers, flightDates, out);
  return { travelers, violations: out };
}

// --- giấy tờ hành khách cho vé máy bay (FR-BKG-13) ------------------------------------------------------

/** R-DOC-01: người lớn có vé bay phải có ngày sinh hợp lệ và từ 12 tuổi tại ngày bay đầu tiên. */
function checkAdultBirth(item: TravelerInput, base: string, firstFlight: string, today: string, out: Violation[]): string | null {
  const raw = (item.birthDate ?? '').trim();
  if (!raw) {
    out.push({ field: `${base}.birthDate`, reason: 'REQUIRED', params: { part: 'birthDate' } });
    return null;
  }
  if (!isValidIso(raw) || raw > today) {
    out.push({ field: `${base}.birthDate`, reason: 'BIRTH_DATE_INVALID' });
    return null;
  }
  if (ageOn(raw, firstFlight) < ADULT_MIN_AGE) out.push({ field: `${base}.birthDate`, reason: 'ADULT_AGE_INVALID', params: { flightDate: firstFlight } });
  return raw;
}

/** R-DOC-02…07: danh xưng, quốc tịch, loại và số giấy tờ, hạn hộ chiếu. Trẻ em, em bé không có giấy tờ. */
function checkDocuments(item: TravelerInput, base: string, flightDates: string[], out: Violation[]): { escortRef: string | null } {
  const raw = item.documents ?? {};
  const path = `${base}.documents`;
  const title = (raw.title ?? '').trim();
  if (!title) out.push({ field: `${path}.title`, reason: 'REQUIRED', params: { part: 'title' } });
  else if (!TITLES[item.type].includes(title)) out.push({ field: `${path}.title`, reason: 'TITLE_INVALID' });
  const nationality = (raw.nationality ?? '').trim();
  if (!nationality) out.push({ field: `${path}.nationality`, reason: 'REQUIRED', params: { part: 'nationality' } });
  else if (!(NATIONALITIES as readonly string[]).includes(nationality)) out.push({ field: `${path}.nationality`, reason: 'NATIONALITY_INVALID' });
  if (item.type === 'CHILD') return { escortRef: (raw.escortTravelerRef ?? '').trim() || null };
  const docType = (raw.docType ?? '').trim();
  const number = (raw.docNumber ?? '').replace(/\s+/g, '').toUpperCase();
  if (!docType) out.push({ field: `${path}.docType`, reason: 'REQUIRED', params: { part: 'docType' } });
  else {
    if (!(DOC_TYPES as readonly string[]).includes(docType) || (docType === 'CCCD' && nationality !== 'VN')) {
      out.push({ field: `${path}.docType`, reason: 'DOC_TYPE_INVALID' });
    }
    if ((DOC_TYPES as readonly string[]).includes(docType)) {
      if (!number) out.push({ field: `${path}.docNumber`, reason: 'REQUIRED', params: { part: 'docNumber' } });
      else if (!(docType === 'CCCD' ? CCCD_PATTERN : PASSPORT_PATTERN).test(number)) {
        out.push({ field: `${path}.docNumber`, reason: 'DOC_NUMBER_INVALID', params: { docType } });
      }
    }
  }
  if (docType === 'PASSPORT') {
    const expiry = (raw.docExpiry ?? '').trim();
    const lastFlight = [...flightDates].sort().at(-1)!;
    if (!expiry) out.push({ field: `${path}.docExpiry`, reason: 'REQUIRED', params: { part: 'docExpiry' } });
    else if (!isValidIso(expiry)) out.push({ field: `${path}.docExpiry`, reason: 'DOC_EXPIRY_INVALID' });
    else if (expiry <= lastFlight) out.push({ field: `${path}.docExpiry`, reason: 'DOC_EXPIRED', params: { flightDate: lastFlight } });
  }
  return { escortRef: null };
}

/** R-DOC-08: mỗi em bé (dưới 2 tuổi tại một ngày bay bất kỳ) chọn một người lớn đi kèm có trong đoàn. */
function checkEscorts(travelers: Traveler[], flightDates: string[], out: Violation[]): void {
  const adults = new Set(travelers.filter((t) => t.type === 'ADULT').map((t) => t.ref));
  travelers.forEach((t, index) => {
    if (!flightDates.some((day) => isInfantOn(t, day))) return;
    const field = `travelers[${index}].documents.escortTravelerRef`;
    if (!t.escortRef) out.push({ field, reason: 'REQUIRED', params: { part: 'escortTravelerRef' } });
    else if (!adults.has(t.escortRef)) out.push({ field, reason: 'ESCORT_INVALID' });
  });
}

// --- bước ②: phân bổ theo dịch vụ --------------------------------------------------------------------

/** R-ITM-01…04, R-FLT-01, R-HTL-01…05. */
export function checkItems(travelers: Traveler[], details: ItemInput[], cart: CartFacts[]): Violation[] {
  const byRef = new Map<string, Traveler>();
  for (const t of travelers) if (!byRef.has(t.ref)) byRef.set(t.ref, t);
  const cartById = new Map(cart.map((c) => [c.cartItemId, c]));
  const out: Violation[] = [];
  const seen = new Set<string>();
  const handled: Array<[number, ItemInput, CartFacts]> = [];
  details.forEach((detail, index) => {
    const facts = cartById.get(detail.cartItemId);
    if (!facts) out.push({ field: `itemDetails[${index}]`, reason: 'ITEM_DETAIL_UNKNOWN' });
    else if (seen.has(detail.cartItemId)) {
      out.push({ field: `itemDetails[${index}]`, reason: 'ITEM_DETAIL_DUPLICATED', cartItemId: facts.cartItemId, params: { itemName: facts.name } });
    } else {
      seen.add(detail.cartItemId);
      handled.push([index, detail, facts]);
    }
  });
  for (const facts of cart) {
    if (!seen.has(facts.cartItemId)) {
      out.push({ field: 'itemDetails', reason: 'ITEM_DETAIL_MISSING', cartItemId: facts.cartItemId, params: { itemName: facts.name } });
    }
  }
  for (const [index, detail, facts] of handled) {
    out.push(...(facts.taxonomy === 'hotel' ? checkHotel(index, detail, facts, byRef) : checkPerPerson(index, detail, facts, byRef)));
  }
  return out;
}

const PER_PERSON = ['flight', 'attraction', 'golf'];

function checkPerPerson(index: number, detail: ItemInput, facts: CartFacts, byRef: Map<string, Traveler>): Violation[] {
  const path = `itemDetails[${index}].travelerRefs`;
  const cid = facts.cartItemId;
  const refs = detail.travelerRefs ?? [];
  if (!refs.length) return [{ field: path, reason: 'ITEM_WITHOUT_TRAVELER', cartItemId: cid, params: { itemName: facts.name } }];
  const out: Violation[] = [];
  const seen = new Set<string>();
  const reported = new Set<string>();
  let structural = true;
  for (const ref of refs) {
    let reason: string;
    if (!byRef.has(ref)) reason = 'TRAVELER_UNKNOWN';
    else if (seen.has(ref)) reason = 'TRAVELER_DUPLICATED';
    else {
      seen.add(ref);
      continue;
    }
    structural = false;
    if (!reported.has(`${reason}|${ref}`)) {
      reported.add(`${reason}|${ref}`);
      out.push({ field: path, reason, cartItemId: cid, params: { travelerName: byRef.get(ref)?.fullName ?? '' } });
    }
  }
  if (!structural) return out;
  const fares = refs.map((ref) => fareTypeOn(byRef.get(ref)!, facts.usingDate));
  const adults = fares.filter((f) => f === 'ADULT').length;
  const children = fares.length - adults;
  if (children && !adults) out.push({ field: path, reason: 'ADULT_REQUIRED', cartItemId: cid, params: { scope: 'item' } });
  if (PER_PERSON.includes(facts.taxonomy) && (adults !== facts.guests.adults || children !== facts.guests.children)) {
    out.push({ field: `itemDetails[${index}]`, reason: 'GUEST_COUNT_MISMATCH', cartItemId: cid, params: { itemName: facts.name } });
  }
  if (facts.taxonomy === 'flight') {
    const infants = refs.filter((ref) => isInfantOn(byRef.get(ref)!, facts.usingDate)).length;
    if (infants > adults) out.push({ field: path, reason: 'INFANTS_EXCEED_ADULTS', cartItemId: cid });
    out.push(...checkFlightEscorts(path, index, refs, byRef, facts));
  }
  return out;
}

/** R-DOC-09, R-DOC-10: người lớn đi kèm em bé phải bay chặng này; mỗi người lớn đi kèm tối đa 1 em bé. */
function checkFlightEscorts(path: string, index: number, refs: string[], byRef: Map<string, Traveler>, facts: CartFacts): Violation[] {
  const out: Violation[] = [];
  const load = new Map<string, number>();
  for (const ref of refs) {
    const t = byRef.get(ref)!;
    if (!t.escortRef || !isInfantOn(t, facts.usingDate) || !byRef.has(t.escortRef)) continue;
    load.set(t.escortRef, (load.get(t.escortRef) ?? 0) + 1);
    if (!refs.includes(t.escortRef)) out.push({ field: path, reason: 'ESCORT_NOT_ON_FLIGHT', cartItemId: facts.cartItemId, params: { travelerName: t.fullName } });
  }
  if ([...load.values()].some((n) => n > 1)) out.push({ field: `itemDetails[${index}]`, reason: 'ESCORT_OVERLOADED', cartItemId: facts.cartItemId });
  return out;
}

function checkHotel(index: number, detail: ItemInput, facts: CartFacts, byRef: Map<string, Traveler>): Violation[] {
  const base = `itemDetails[${index}]`;
  const cid = facts.cartItemId;
  const rooms = detail.rooms ?? [];
  const out: Violation[] = [];
  if (rooms.length !== facts.quantity) out.push({ field: `${base}.rooms`, reason: 'ROOM_COUNT_MISMATCH', cartItemId: cid, params: { rooms: facts.quantity } });
  const seenInItem = new Set<string>();
  rooms.forEach((room, k) => {
    const roomPath = `${base}.rooms[${k}]`;
    const reported = new Set<string>();
    for (const ref of room.travelerRefs) {
      let reason: string | null = null;
      if (!byRef.has(ref)) reason = 'TRAVELER_UNKNOWN';
      else if (seenInItem.has(ref)) reason = 'TRAVELER_DUPLICATED';
      else seenInItem.add(ref);
      if (reason && !reported.has(`${reason}|${ref}`)) {
        reported.add(`${reason}|${ref}`);
        out.push({ field: `${roomPath}.travelerRefs`, reason, cartItemId: cid, params: { travelerName: byRef.get(ref)?.fullName ?? '' } });
      }
    }
    const adults = room.travelerRefs.filter((ref) => byRef.has(ref) && fareTypeOn(byRef.get(ref)!, facts.usingDate) === 'ADULT');
    if (!adults.length) out.push({ field: roomPath, reason: 'ADULT_REQUIRED', cartItemId: cid, params: { scope: 'room', roomNo: k + 1 } });
    const capacity = roomCapacity(facts.maxOccupancy);
    if (room.travelerRefs.length > capacity) {
      out.push({ field: roomPath, reason: 'OCCUPANCY_EXCEEDED', cartItemId: cid, params: { roomNo: k + 1, maxOccupancy: capacity } });
    }
    if (adults.length && !adults.includes(room.leadTravelerRef ?? '')) {
      out.push({ field: `${roomPath}.leadTravelerRef`, reason: 'LEAD_GUEST_INVALID', cartItemId: cid, params: { roomNo: k + 1 } });
    }
  });
  return out;
}

/** Ngày bay của các mục vé máy bay; có ngày bay thì áp luật giấy tờ hành khách (FR-BKG-13). */
export function flightDatesOf(cart: CartFacts[]): string[] {
  return cart.filter((c) => c.taxonomy === 'flight').map((c) => c.usingDate);
}

/** Toàn bộ luật của `POST /bookings` khi request có `travelers` (§8.3 bước 5). */
export function checkCheckout(
  contact: ContactInput, inputs: TravelerInput[], details: ItemInput[], cart: CartFacts[], today: string,
): { travelers: Traveler[]; violations: Violation[] } {
  const earliest = cart.reduce<string | null>((min, c) => (min === null || c.usingDate < min ? c.usingDate : min), null);
  const maxParty = orderPartyCap(cart);
  const party = checkParty(inputs, { earliest, today, flightDates: flightDatesOf(cart), maxParty });
  // Khách sạn trên 9 khách phải đặt riêng: đơn trộn với dịch vụ khác chỉ khai được đoàn tối đa 9 người.
  const mixed: Violation[] = cart
    .filter((c) => c.taxonomy === 'hotel' && c.guests.adults + c.guests.children > maxParty)
    .map((c) => ({ field: 'itemDetails', reason: 'PARTY_TOO_LARGE', cartItemId: c.cartItemId, params: { scope: 'mixed', itemName: c.name } }));
  return {
    travelers: party.travelers,
    violations: [...checkContact(contact), ...party.violations, ...mixed, ...checkItems(party.travelers, details, cart)],
  };
}

// --- câu thông báo (§5.6) ----------------------------------------------------------------------------

function requiredMessage(field: string, params: Violation['params']): string {
  if (field.endsWith('.surname')) return 'Vui lòng nhập họ.';
  if (field.endsWith('.givenNames')) return 'Vui lòng nhập tên đệm và tên.';
  if (field.endsWith('.birthDate')) return 'Vui lòng nhập ngày sinh.';
  if (field.endsWith('.documents.title')) return 'Chọn danh xưng.';
  if (field.endsWith('.documents.nationality')) return 'Chọn quốc tịch.';
  if (field.endsWith('.documents.docType')) return 'Chọn loại giấy tờ.';
  if (field.endsWith('.documents.docNumber')) return 'Nhập số giấy tờ.';
  if (field.endsWith('.documents.docExpiry')) return 'Nhập ngày hết hạn hộ chiếu.';
  if (field.endsWith('.documents.escortTravelerRef')) return 'Chọn người lớn đi kèm em bé.';
  if (field === 'contact.fullName') return 'Vui lòng nhập họ và tên người liên hệ.';
  if (field === 'contact.email') return 'Vui lòng nhập email.';
  if (field === 'contact.phone') return 'Vui lòng nhập số điện thoại.';
  if (field.endsWith('.guestNames')) return `Vui lòng nhập họ tên khách của ${params?.itemName ?? 'dịch vụ này'}.`;
  return 'Vui lòng nhập thông tin còn thiếu.';
}

/** Câu tiếng Việt hiển thị được trực tiếp; giống hệt `application/booking/messages.py`. */
export function messageFor(v: Violation): string {
  const p = v.params ?? {};
  const name = String(p.itemName ?? 'dịch vụ này');
  switch (v.reason) {
    case 'REQUIRED': return requiredMessage(v.field, p);
    case 'NAME_INVALID': return v.field.startsWith('contact.') ? 'Họ và tên người liên hệ tối đa 100 ký tự.' : 'Chỉ gồm chữ cái, đúng như trên giấy tờ.';
    case 'PHONE_INVALID': return 'Số điện thoại gồm 10 chữ số, bắt đầu bằng 0.';
    case 'EMAIL_INVALID': return 'Email không hợp lệ.';
    case 'BIRTH_DATE_INVALID': return 'Ngày sinh không hợp lệ.';
    case 'CHILD_AGE_INVALID': return `Bé đã đủ 12 tuổi vào ${formatDmy(String(p.turned12On))}. Vui lòng chọn loại Người lớn.`;
    case 'ADULT_AGE_INVALID': return `Người lớn phải từ 12 tuổi tại ngày bay ${formatDmy(String(p.flightDate))}.`;
    case 'TITLE_INVALID': return 'Danh xưng không hợp lệ.';
    case 'NATIONALITY_INVALID': return 'Quốc tịch không hợp lệ.';
    case 'DOC_TYPE_INVALID': return 'Khách quốc tịch nước ngoài dùng hộ chiếu.';
    case 'DOC_NUMBER_INVALID': return p.docType === 'CCCD' ? 'Số CCCD gồm 12 chữ số.' : 'Số hộ chiếu gồm 6–9 chữ và số.';
    case 'DOC_EXPIRY_INVALID': return 'Ngày hết hạn không hợp lệ.';
    case 'DOC_EXPIRED': return `Hộ chiếu hết hạn trước ngày bay cuối cùng (${formatDmy(String(p.flightDate))}).`;
    case 'ESCORT_INVALID': return 'Người lớn đi kèm phải là người lớn trong đoàn.';
    case 'ESCORT_NOT_ON_FLIGHT': return `Người lớn đi kèm ${p.travelerName || 'em bé'} không bay chuyến này.`;
    case 'ESCORT_OVERLOADED': return 'Mỗi người lớn chỉ đi kèm 1 em bé.';
    case 'ADULT_REQUIRED':
      if (p.scope === 'item') return 'Trẻ em cần đi cùng ít nhất 1 người lớn trong dịch vụ này.';
      if (p.scope === 'room') return 'Mỗi phòng cần ít nhất 1 người lớn.';
      return 'Cần ít nhất 1 người lớn (từ 12 tuổi).';
    case 'PARTY_TOO_LARGE': {
      const cap = Number(p.maxParty ?? MAX_PARTY);
      if (p.scope === 'mixed') return `${p.itemName ?? 'Khách sạn'} trên 9 khách phải đặt riêng, không gộp với dịch vụ khác.`;
      if (p.rooms) return `Mỗi phòng tối đa 9 khách (${cap} khách cho ${p.rooms} phòng). Vui lòng thêm phòng.`;
      if (v.field === 'travelers' && cap > MAX_PARTY) return `Mỗi đơn tối đa ${cap} khách. Vui lòng tách thành nhiều đơn.`;
      return 'Mỗi đơn tối đa 9 khách. Vui lòng tách thành nhiều đơn.';
    }
    case 'ROOMS_TOO_MANY': return `Mỗi lần đặt tối đa ${p.maxRooms ?? MAX_ROOMS} phòng.`;
    case 'TRAVELER_UNKNOWN': return 'Hành khách không có trong đoàn.';
    case 'TRAVELER_DUPLICATED':
      return v.field.endsWith('.travelerRef') ? 'Mã hành khách bị trùng.' : `${p.travelerName || 'Hành khách này'} đã được chọn ở chỗ khác trong dịch vụ này.`;
    case 'ITEM_DETAIL_MISSING': return `Thiếu thông tin cho ${name}.`;
    case 'ITEM_DETAIL_UNKNOWN':
    case 'ITEM_DETAIL_DUPLICATED': return 'Thông tin dịch vụ không khớp giỏ hàng. Vui lòng tải lại giỏ.';
    case 'ITEM_WITHOUT_TRAVELER': return `Chọn ít nhất 1 khách dùng ${name}, hoặc xoá dịch vụ khỏi giỏ.`;
    case 'GUEST_COUNT_MISMATCH': return v.field === 'quantity' ? 'Số lượng phải bằng số người lớn cộng số trẻ em.' : `Số khách của ${name} vừa thay đổi. Vui lòng xem lại giá.`;
    case 'INFANTS_EXCEED_ADULTS': return 'Mỗi em bé dưới 2 tuổi cần một người lớn đi kèm trên chuyến bay.';
    case 'ROOM_COUNT_MISMATCH': return `Bạn đã đặt ${p.rooms ?? 1} phòng. Hãy xếp khách vào đủ ${p.rooms ?? 1} phòng hoặc giảm số phòng.`;
    case 'OCCUPANCY_EXCEEDED': return p.roomNo ? `Phòng ${p.roomNo} chứa tối đa ${p.maxOccupancy} khách.` : `Mỗi phòng chứa tối đa ${p.maxOccupancy} khách. Vui lòng thêm phòng.`;
    case 'LEAD_GUEST_INVALID': return 'Người đại diện nhận phòng phải là người lớn ở trong phòng.';
    case 'TRAVELERS_REQUIRED': return 'Đơn có trẻ em cần khai thông tin hành khách. Vui lòng tải lại trang và thử lại.';
    default: return 'Thông tin chưa hợp lệ.';
  }
}
