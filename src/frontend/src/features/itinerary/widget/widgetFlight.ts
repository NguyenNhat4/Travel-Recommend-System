import type { ItineraryFlightItem } from '../../../types/travel';

/** Một đầu của chặng bay: ngày ("T3, 20 thg 10"), giờ ("08:00") và nơi (thành phố, thiếu thì mã sân bay). */
export interface FlightEnd {
  day: string | null;
  time: string | null;
  place: string;
}

/** Một chặng hiển thị trên thẻ vé; vé khứ hồi có hai chặng (chiều đi, chiều về). */
export interface FlightSegment {
  label: 'Chiều đi' | 'Chiều về';
  airline: string | null;
  flightNumber: string | null;
  departure: FlightEnd;
  arrival: FlightEnd;
  /** Phút bay tính từ `departureAt`/`arrivalAt` (có múi giờ); null khi thiếu một trong hai. */
  durationMinutes: number | null;
  nonstop: boolean;
}

const WEEKDAY = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/** "2026-10-20T08:00:00+07:00" → "T3, 20 thg 10". Giờ trong chuỗi đã là giờ Việt Nam nên chỉ đọc phần ngày. */
export function flightDay(iso: string | null): string | null {
  const match = iso ? /^(\d{4})-(\d{2})-(\d{2})/.exec(iso) : null;
  if (!match) return null;
  const [, year, month, day] = match;
  const weekday = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day))).getUTCDay();
  return `${WEEKDAY[weekday]}, ${Number(day)} thg ${Number(month)}`;
}

/** Giờ địa phương "HH:MM" của chuỗi ISO có múi giờ (không đổi sang giờ máy người xem). */
export function flightTime(iso: string | null): string | null {
  const match = iso ? /T(\d{2}:\d{2})/.exec(iso) : null;
  return match ? match[1] : null;
}

function minutesBetween(from: string | null, to: string | null): number | null {
  if (!from || !to) return null;
  const minutes = (Date.parse(to) - Date.parse(from)) / 60000;
  return Number.isFinite(minutes) && minutes > 0 ? Math.round(minutes) : null;
}

/** 60 → "1h00'", 135 → "2h15'". */
export function formatDuration(minutes: number): string {
  return `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, '0')}'`;
}

/**
 * Các chặng của một vé trong lịch trình (AC-AGT-02, user-flow §4.2): hãng, số hiệu, giờ và nơi đi/đến, bay thẳng. Mọi giá
 * trị đọc từ `attributes` của sản phẩm chuyến bay; không có trường nào thì để trống, không đoán. Vé khứ hồi thêm chiều về
 * từ `returnFlight`.
 */
export function flightSegments(flight: ItineraryFlightItem): FlightSegment[] {
  const attributes = (flight.product.attributes ?? {}) as Record<string, unknown>;
  const origin = text(attributes.originCity) ?? text(attributes.originAirport) ?? '';
  const destination = text(attributes.destinationCity) ?? text(attributes.destinationAirport) ?? flight.product.destination;
  const departureAt = text(attributes.departureAt);
  const arrivalAt = text(attributes.arrivalAt);
  const nonstop = attributes.nonstop === true;
  const going: FlightSegment = {
    label: flight.direction === 'RETURN' ? 'Chiều về' : 'Chiều đi',
    airline: text(attributes.airline),
    flightNumber: text(attributes.flightNumber),
    departure: { day: flightDay(departureAt ?? flight.date), time: flightTime(departureAt) ?? text(attributes.departureTimeLocal), place: origin },
    arrival: { day: flightDay(arrivalAt ?? flight.date), time: flightTime(arrivalAt) ?? text(attributes.arrivalTimeLocal), place: destination },
    durationMinutes: minutesBetween(departureAt, arrivalAt),
    nonstop,
  };
  const back = attributes.returnFlight as Record<string, unknown> | undefined;
  if (flight.direction !== 'ROUND_TRIP' || !back) return [going];
  const backDeparture = text(back.departureAt);
  const backArrival = text(back.arrivalAt);
  return [going, {
    label: 'Chiều về',
    airline: text(back.airline) ?? going.airline,
    flightNumber: text(back.flightNumber),
    departure: { day: flightDay(backDeparture ?? flight.returnDate), time: flightTime(backDeparture), place: destination },
    arrival: { day: flightDay(backArrival ?? flight.returnDate), time: flightTime(backArrival), place: origin },
    durationMinutes: minutesBetween(backDeparture, backArrival),
    nonstop: back.nonstop === true,
  }];
}
