/**
 * Ngữ cảnh chuyến đi (ngày, số khách, số phòng) mang qua URL từ tấm tìm kiếm ở trang danh mục
 * tới `/search` rồi tới hộp đặt ở trang chi tiết (docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md §6).
 *
 * Đây là ngữ cảnh điền sẵn, không phải bộ lọc phòng trống: Backend chưa lọc theo ngày. Giá trị sai bị bỏ im lặng.
 * Không đưa họ tên, token hay dữ liệu cá nhân vào URL.
 */

export interface TripContext {
  /** YYYY-MM-DD */
  checkIn?: string;
  /** YYYY-MM-DD, sau `checkIn`. */
  checkOut?: string;
  adults?: number;
  children?: number;
  rooms?: number;
}

export const TRIP_PARAM_KEYS = ['checkIn', 'checkOut', 'adults', 'children', 'rooms'] as const;

/** Đoàn tối đa 9 người mỗi mục (FR-BKG-08). */
export const MAX_PARTY_SIZE = 9;

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const DAY_MS = 24 * 3600 * 1000;

type ParamSource = { get(name: string): string | null };

/** Ngày hôm nay theo giờ Việt Nam, dạng YYYY-MM-DD (cùng cách `TravelContext` tính ngày mặc định). */
export function todayVN(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(now);
}

export function addDaysIso(iso: string, days: number): string {
  return new Date(Date.parse(`${iso}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

function validDate(value: string | null): string | undefined {
  if (!value || !ISO_DATE.test(value)) return undefined;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value ? undefined : value;
}

function validInt(value: string | null, min: number, max: number): number | undefined {
  if (value === null || !/^\d+$/.test(value)) return undefined;
  const n = Number(value);
  return n >= min && n <= max ? n : undefined;
}

export function parseTripContext(params: ParamSource, today: string = todayVN()): TripContext {
  const ctx: TripContext = {};
  const checkIn = validDate(params.get('checkIn'));
  if (checkIn && checkIn >= today) {
    ctx.checkIn = checkIn;
    const checkOut = validDate(params.get('checkOut'));
    if (checkOut && checkOut > checkIn) ctx.checkOut = checkOut;
  }
  const adults = validInt(params.get('adults'), 1, MAX_PARTY_SIZE);
  if (adults !== undefined) {
    ctx.adults = adults;
    const children = validInt(params.get('children'), 0, MAX_PARTY_SIZE - 1);
    if (children !== undefined && adults + children <= MAX_PARTY_SIZE) ctx.children = children;
  }
  const rooms = validInt(params.get('rooms'), 1, MAX_PARTY_SIZE);
  // Mỗi phòng ít nhất một người lớn (FR-BKG-08): số phòng vượt số người lớn là giá trị sai.
  if (rooms !== undefined && (ctx.adults === undefined || rooms <= ctx.adults)) ctx.rooms = rooms;
  return ctx;
}

/** Query string không có dấu `?`; rỗng khi không có gì. `children = 0` không cần ghi. */
export function serializeTripContext(ctx: TripContext): string {
  const search = new URLSearchParams();
  if (ctx.checkIn) search.set('checkIn', ctx.checkIn);
  if (ctx.checkIn && ctx.checkOut) search.set('checkOut', ctx.checkOut);
  if (ctx.adults) search.set('adults', String(ctx.adults));
  if (ctx.children) search.set('children', String(ctx.children));
  if (ctx.rooms) search.set('rooms', String(ctx.rooms));
  return search.toString();
}

function shortDate(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

/** "15/10 – 17/10 · 1 phòng, 2 người lớn, 1 trẻ em"; rỗng khi không có gì để nói. */
export function describeTripContext(ctx: TripContext): string {
  const parts: string[] = [];
  if (ctx.checkIn) parts.push(ctx.checkOut ? `${shortDate(ctx.checkIn)} – ${shortDate(ctx.checkOut)}` : shortDate(ctx.checkIn));
  const who: string[] = [];
  if (ctx.rooms) who.push(`${ctx.rooms} phòng`);
  if (ctx.adults) who.push(`${ctx.adults} người lớn`);
  if (ctx.children) who.push(`${ctx.children} trẻ em`);
  if (who.length) parts.push(who.join(', '));
  return parts.join(' · ');
}
