/**
 * URL của trang kết quả vé máy bay: `/flights?origin&destination[&checkIn&checkOut&adults&children]`.
 * Ngày và số khách dùng cùng quy ước và cùng kiểm tra với ngữ cảnh chuyến đi (features/search/tripContext.ts).
 */
import { parseTripContext, serializeTripContext, type TripContext } from '../../search/tripContext';

export const FLIGHTS_ROUTE = '/flights';

export interface FlightSearch {
  origin: string;
  destination: string;
  trip: TripContext;
}

export function buildFlightResultsHref({ origin, destination, trip }: FlightSearch): string {
  const params = new URLSearchParams({ origin: origin.trim(), destination: destination.trim() });
  const query = serializeTripContext({ checkIn: trip.checkIn, checkOut: trip.checkOut, adults: trip.adults, children: trip.children });
  return `${FLIGHTS_ROUTE}?${params.toString()}${query ? `&${query}` : ''}`;
}

/** Giá trị tấm tìm kiếm gửi lên khi bấm Tìm: điểm đến là nhãn chuẩn, hoặc null khi chưa nhập hay chưa chọn từ gợi ý. */
export interface FlightSearchInput {
  origin: string;
  /** Chữ trong ô điểm đến (kể cả khi chưa khớp nhãn nào). */
  location: string;
  destination: string | null;
  trip: TripContext;
}

type ParamSource = { get(name: string): string | null };

/** Có cả điểm đi và điểm đến thì là tìm chuyến; thiếu một trong hai thì `/flights` vẫn là trang danh mục. */
export function parseFlightSearch(params: ParamSource): FlightSearch | null {
  const origin = params.get('origin')?.trim();
  const destination = params.get('destination')?.trim();
  return origin && destination ? { origin, destination, trip: parseTripContext(params) } : null;
}
