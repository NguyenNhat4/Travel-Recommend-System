/**
 * Mô hình hiển thị của trang kết quả vé máy bay: từ danh sách sản phẩm tầng con của một tuyến (`ProductSummary`) sang
 * "một thẻ cho mỗi hành trình", cùng các hàm lọc, sắp xếp, gom ngày và ghép chặng đi/về. Toàn bộ là hàm thuần.
 *
 * Nguyên tắc dữ liệu (docs/guide/hien-thi-hang-ve-may-bay.md): mọi chuyến, giờ, giá, hạng vé lấy nguyên từ response; trường
 * `null` hoặc vắng mặt là "chưa biết" và không được hiện thành "0 kg" hay "không hoàn được". Web không tự suy giá.
 */
import type { ProductSummary } from '../../../services/catalog';
import { fold } from '../../catalog/landing/searchHref';

type Attributes = Record<string, unknown>;
const attributesOf = (product: ProductSummary): Attributes => (product.attributes ?? {}) as Attributes;
const text = (value: unknown): string => (typeof value === 'string' ? value : '');
const ISO_DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

/** Một hạng vé của hành trình; mỗi hạng là một `productId` riêng và là thứ được thêm vào giỏ. */
export interface FareOption {
  productId: string;
  /** Nhãn của backend ("Phổ thông", "Thương gia", "Giá rẻ nhất"); rỗng khi response không có `fareClasses`. */
  name: string;
  code: string | null;
  price: number;
  /** Vé Thương gia mô phỏng: bắt buộc hiện "Giá minh hoạ". */
  simulated: boolean;
  /** Báo giá quá hạn tại nguồn. Không phải hết chỗ và không khoá đặt vé. */
  expired: boolean;
  carryOnKg: number | null;
  checkedKg: number | null;
  summary: ProductSummary;
}

/** Một hành trình bay một chiều (một thẻ trên danh sách), có một hoặc nhiều hạng vé. */
export interface FlightOption {
  key: string;
  /** Ngày bay YYYY-MM-DD, giờ Việt Nam. */
  date: string;
  depAt: string;
  arrAt: string;
  depClock: string;
  arrClock: string;
  depMinutes: number;
  /** 0 = đến trong ngày; 1 = qua nửa đêm. */
  arrDayOffset: number;
  from: string;
  to: string;
  fromCity: string;
  toCity: string;
  toAirportName: string;
  airline: string;
  airlineCode: string;
  flightNumber: string;
  durationMinutes: number | null;
  /** true = bay thẳng; false = có điểm dừng; null = nguồn không nói. */
  nonstop: boolean | null;
  priceObservedAt: string | null;
  /** Theo thứ tự backend gửi (ECO, PRE, BUS, FST, chưa rõ); phần tử đầu là hạng mặc định. */
  fares: FareOption[];
}

export const minPrice = (option: FlightOption): number => Math.min(...option.fares.map((fare) => fare.price));

function isBookableOneWay(product: ProductSummary): boolean {
  const a = attributesOf(product);
  return a.level === 'flight' && a.tripType !== 'roundTrip' && a.ticketed !== false
    && product.available && product.unitPrice != null
    && ISO_DATE_TIME.test(text(a.departureAt)) && ISO_DATE_TIME.test(text(a.arrivalAt));
}

function dayDiff(fromIso: string, toIso: string): number {
  const utc = (iso: string) => Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)));
  return Math.round((utc(toIso) - utc(fromIso)) / 86_400_000);
}

function durationOf(a: Attributes): number | null {
  if (typeof a.durationMinutes === 'number' && a.durationMinutes > 0) return Math.round(a.durationMinutes);
  const minutes = Math.round((Date.parse(text(a.arrivalAt)) - Date.parse(text(a.departureAt))) / 60_000);
  return Number.isFinite(minutes) && minutes > 0 ? minutes : null;
}

function toFare(product: ProductSummary): FareOption {
  const fareClass = product.fareClasses?.find((f) => f.productId === product.productId);
  const a = attributesOf(product);
  return {
    productId: product.productId,
    name: fareClass?.name ?? '',
    code: fareClass?.code ?? null,
    price: product.unitPrice as number,
    simulated: a.simulated === true || /\(giá minh hoạ\)\s*$/i.test(product.name),
    expired: fareClass?.availabilityStatus === 'EXPIRED',
    carryOnKg: fareClass?.carryOnKg ?? null,
    checkedKg: fareClass?.checkedKg ?? null,
    summary: product,
  };
}

/**
 * Các sản phẩm tầng con của tuyến → các hành trình một chiều đặt được, sắp theo giờ đi. Vé khứ hồi (`tripType: roundTrip`)
 * và vé hết chỗ bị bỏ. Các sản phẩm cùng hành trình có chung `fareClasses` nên được gom thành một thẻ, mỗi hạng một `FareOption`.
 */
export function flightOptionsFromVariants(variants: ProductSummary[]): FlightOption[] {
  const groups = new Map<string, ProductSummary[]>();
  for (const product of variants) {
    if (!isBookableOneWay(product)) continue;
    const ids = product.fareClasses?.map((f) => f.productId) ?? [];
    const key = ids.length > 0 ? [...ids].sort().join('|') : product.productId;
    groups.set(key, [...(groups.get(key) ?? []), product]);
  }

  const options: FlightOption[] = [];
  for (const [key, members] of groups) {
    const order = new Map((members[0].fareClasses ?? []).map((f, index) => [f.productId, index] as const));
    const fares = members
      .map(toFare)
      .sort((a, b) => (order.get(a.productId) ?? 99) - (order.get(b.productId) ?? 99) || a.price - b.price);
    const a = attributesOf(members[0]);
    const depAt = text(a.departureAt);
    const arrAt = text(a.arrivalAt);
    const flightNumber = text(a.flightNumber);
    options.push({
      key,
      date: members[0].availableFrom || depAt.slice(0, 10),
      depAt,
      arrAt,
      depClock: depAt.slice(11, 16),
      arrClock: arrAt.slice(11, 16),
      depMinutes: Number(depAt.slice(11, 13)) * 60 + Number(depAt.slice(14, 16)),
      arrDayOffset: dayDiff(depAt, arrAt),
      from: text(a.originAirport),
      to: text(a.destinationAirport),
      fromCity: text(a.originCity),
      toCity: text(a.destinationCity) || members[0].destination,
      toAirportName: text(a.destinationAirportName),
      airline: text(a.airline),
      airlineCode: text(a.airlineCode) || flightNumber.match(/^[A-Z0-9]{2}(?=\d)/)?.[0] || '',
      flightNumber,
      durationMinutes: durationOf(a),
      nonstop: a.nonstop === true ? true : a.nonstop === false ? false : null,
      priceObservedAt: text(a.priceObservedAt) || null,
      fares,
    });
  }
  return options.sort((x, y) => x.depAt.localeCompare(y.depAt) || x.flightNumber.localeCompare(y.flightNumber));
}

/** "2h10'" */
export function formatDuration(minutes: number): string {
  return `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, '0')}'`;
}

/** Chuyến chiều về phải cất cánh sau khi chuyến chiều đi hạ cánh. */
export function canFollow(outbound: FlightOption, ret: FlightOption): boolean {
  return Date.parse(ret.depAt) >= Date.parse(outbound.arrAt);
}

// ---------------------------------------------------------------------------------------------------------------- Khung giờ

export type SlotId = 'morning' | 'noon' | 'afternoon' | 'evening' | 'late';

/** Khung giờ khởi hành; `from` tính, `to` không tính. Khuya vắt qua nửa đêm. */
export const TIME_SLOTS: ReadonlyArray<{ id: SlotId; label: string; hours: string; from: number; to: number }> = [
  { id: 'morning', label: 'Sáng', hours: '05:00 – 11:00', from: 300, to: 660 },
  { id: 'noon', label: 'Trưa', hours: '11:00 – 14:00', from: 660, to: 840 },
  { id: 'afternoon', label: 'Chiều', hours: '14:00 – 18:00', from: 840, to: 1080 },
  { id: 'evening', label: 'Tối', hours: '18:00 – 22:00', from: 1080, to: 1320 },
  { id: 'late', label: 'Khuya', hours: '22:00 – 05:00', from: 1320, to: 300 },
];

export function slotOf(depMinutes: number): SlotId {
  return TIME_SLOTS.find((slot) => slot.id !== 'late' && depMinutes >= slot.from && depMinutes < slot.to)?.id ?? 'late';
}

// ---------------------------------------------------------------------------------------------------------------- Bộ lọc, sắp xếp

export type StopKind = 'nonstop' | 'connecting';

export interface FlightFilters {
  /** Rỗng = mọi khung giờ. */
  slots: ReadonlySet<SlotId>;
  /** Hãng bị bỏ chọn; hãng mới xuất hiện ở ngày khác vẫn được hiện. */
  hiddenAirlines: ReadonlySet<string>;
  /** Rỗng = mọi loại. Chuyến chưa rõ có dừng hay không bị loại khi bật một loại. */
  stops: ReadonlySet<StopKind>;
}

export const noFilters = (): FlightFilters => ({ slots: new Set(), hiddenAirlines: new Set(), stops: new Set() });

export function countActiveFilters(filters: FlightFilters): number {
  return filters.slots.size + filters.hiddenAirlines.size + filters.stops.size;
}

export function applyFilters(options: FlightOption[], filters: FlightFilters): FlightOption[] {
  return options.filter((option) => {
    if (filters.slots.size > 0 && !filters.slots.has(slotOf(option.depMinutes))) return false;
    if (filters.hiddenAirlines.has(option.airline)) return false;
    if (filters.stops.size > 0) {
      const kind: StopKind | null = option.nonstop === true ? 'nonstop' : option.nonstop === false ? 'connecting' : null;
      if (!kind || !filters.stops.has(kind)) return false;
    }
    return true;
  });
}

export type FlightSort = 'price' | 'early' | 'late' | 'fast';

export const FLIGHT_SORT_LABELS: Record<FlightSort, string> = {
  price: 'Giá thấp nhất',
  early: 'Giờ đi sớm nhất',
  late: 'Giờ đi muộn nhất',
  fast: 'Bay nhanh nhất',
};

export function sortFlights(options: FlightOption[], sort: FlightSort): FlightOption[] {
  const byDeparture = (a: FlightOption, b: FlightOption) => a.depAt.localeCompare(b.depAt);
  const compare: Record<FlightSort, (a: FlightOption, b: FlightOption) => number> = {
    price: (a, b) => minPrice(a) - minPrice(b) || byDeparture(a, b),
    early: byDeparture,
    late: (a, b) => byDeparture(b, a),
    fast: (a, b) => (a.durationMinutes ?? Infinity) - (b.durationMinutes ?? Infinity) || minPrice(a) - minPrice(b),
  };
  return [...options].sort(compare[sort]);
}

/** Số hành trình theo từng giá trị lọc, tính trên danh sách chưa lọc của ngày đang xem. */
export function countFacets(options: FlightOption[]) {
  const slots = new Map<SlotId, number>();
  const airlines = new Map<string, number>();
  let nonstop = 0;
  let connecting = 0;
  for (const option of options) {
    const slot = slotOf(option.depMinutes);
    slots.set(slot, (slots.get(slot) ?? 0) + 1);
    airlines.set(option.airline, (airlines.get(option.airline) ?? 0) + 1);
    if (option.nonstop === true) nonstop += 1;
    else if (option.nonstop === false) connecting += 1;
  }
  return { slots, airlines, nonstop, connecting };
}

/** Bỏ khỏi bộ lọc những khung giờ và loại điểm dừng không còn chuyến nào ở ngày đang xem (đổi ngày, đổi chặng). */
export function pruneFilters(filters: FlightFilters, facets: ReturnType<typeof countFacets>): FlightFilters {
  const stops = new Set<StopKind>();
  if (filters.stops.has('nonstop') && facets.nonstop > 0) stops.add('nonstop');
  if (filters.stops.has('connecting') && facets.connecting > 0) stops.add('connecting');
  return {
    slots: new Set([...filters.slots].filter((slot) => (facets.slots.get(slot) ?? 0) > 0)),
    hiddenAirlines: filters.hiddenAirlines,
    stops,
  };
}

// ---------------------------------------------------------------------------------------------------------------- Ngày

export interface DaySummary {
  date: string;
  minPrice: number;
  count: number;
}

/** Chỉ những ngày có chuyến (dữ liệu thưa, ngày trống không có gì để chọn), từ `notBefore` trở đi, theo thứ tự ngày. */
export function summarizeDays(options: FlightOption[], notBefore?: string): DaySummary[] {
  const days = new Map<string, DaySummary>();
  for (const option of options) {
    if (notBefore && option.date < notBefore) continue;
    const day = days.get(option.date);
    const price = minPrice(option);
    if (day) {
      day.count += 1;
      day.minPrice = Math.min(day.minPrice, price);
    } else {
      days.set(option.date, { date: option.date, minPrice: price, count: 1 });
    }
  }
  return [...days.values()].sort((a, b) => a.date.localeCompare(b.date));
}

/**
 * Ngày đang xem: đúng ngày mong muốn nếu có chuyến; chưa có ngày mong muốn thì ngày đầu tiên có chuyến. Ngày mong muốn không có
 * chuyến thì **không** tự đổi sang ngày khác (`date: null`, không chuyến nào được hiện): chỉ trả các ngày gần nhất có chuyến, một
 * ngày trước và một ngày sau, để khách tự chọn.
 */
export function pickDate(days: DaySummary[], wanted?: string): { date: string | null; nearest: DaySummary[] } | null {
  if (days.length === 0) return null;
  if (!wanted) return { date: days[0].date, nearest: [] };
  if (days.some((day) => day.date === wanted)) return { date: wanted, nearest: [] };
  const before = days.filter((day) => day.date < wanted).pop();
  const after = days.find((day) => day.date > wanted);
  return { date: null, nearest: [before, after].filter((day): day is DaySummary => day !== undefined) };
}

// ---------------------------------------------------------------------------------------------------------------- Tuyến

/** Tuyến khớp điểm đi người dùng gõ: đúng tên thành phố hoặc mã sân bay (bỏ dấu), rồi mới đến chứa nhau ("Hồ Chí Minh" ~ "TP. Hồ Chí Minh"). */
export function matchRoute(routes: ProductSummary[], origin: string): ProductSummary | null {
  const wanted = fold(origin);
  if (!wanted) return null;
  const cities = (route: ProductSummary) => [attributesOf(route).originCity, attributesOf(route).originDestination].map(text).filter(Boolean).map(fold);
  const codes = (route: ProductSummary) => {
    const airports = attributesOf(route).originAirports;
    return Array.isArray(airports) ? airports.map(text).map(fold) : [];
  };
  return routes.find((route) => cities(route).includes(wanted) || codes(route).includes(wanted))
    ?? (wanted.length >= 3 ? routes.find((route) => cities(route).some((city) => city.includes(wanted) || wanted.includes(city))) : undefined)
    ?? null;
}

export interface OriginChoice {
  city: string;
  code: string;
}

/** Các điểm đi có tuyến tới điểm đến, để gợi ý khi điểm đi người dùng gõ không có tuyến. */
export function originChoices(routes: ProductSummary[]): OriginChoice[] {
  const seen = new Set<string>();
  const choices: OriginChoice[] = [];
  for (const route of routes) {
    const a = attributesOf(route);
    const city = text(a.originCity);
    if (!city || seen.has(city)) continue;
    seen.add(city);
    choices.push({ city, code: Array.isArray(a.originAirports) ? text(a.originAirports[0]) : '' });
  }
  return choices.sort((x, y) => x.city.localeCompare(y.city, 'vi'));
}

/** Thành phố đi của tuyến (điểm đến của tuyến chiều về). */
export const routeOriginCity = (route: ProductSummary): string => text(attributesOf(route).originCity);
