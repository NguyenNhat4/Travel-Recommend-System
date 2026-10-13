/**
 * Logic thuần của ô điểm đi, điểm đến ở `/flights` (spec ui-dia-diem-san-bay-va-khach-san-noi-tieng §3–§4).
 * Không gọi mạng và không giữ trạng thái: nhận danh sách sân bay hiện hành đã tải, trả nhóm gợi ý và kết quả khớp.
 */
import { fold, startsAWord } from '../../catalog/landing/searchHref';
import type { FlightAirport } from '../../../services/flights';

export const POPULAR_AIRPORT_LIMIT = 5;
export const MAX_AIRPORT_MATCHES = 8;
export const RECENT_AIRPORT_LIMIT = 5;

export const RECENT_TITLE = 'Tìm gần đây';
export const POPULAR_TITLE = 'Sân bay phổ biến';
export const DOMESTIC_TITLE = 'Trong nước';

/** Nhãn một sân bay trong ô nhập: "Nha Trang (CXR)". */
export function airportLabel(airport: Pick<FlightAirport, 'city' | 'code'>): string {
  return `${airport.city} (${airport.code})`;
}

const byCity = (a: FlightAirport, b: FlightAirport) => a.city.localeCompare(b.city, 'vi') || a.code.localeCompare(b.code);


/**
 * Sân bay đúng với chữ đã nhập: mã IATA, nhãn "Thành phố (MÃ)", hoặc tên thành phố khi thành phố đó chỉ có một sân bay.
 * Không khớp thì null; ô sẽ bị xoá khi rời ô (spec §4.4). Không phân biệt dấu và hoa thường.
 */
export function matchAirport(text: string, airports: readonly FlightAirport[] | null): FlightAirport | null {
  const wanted = fold(text);
  if (!airports || !wanted) return null;
  const exact = airports.find((airport) => fold(airport.code) === wanted || fold(airportLabel(airport)) === wanted);
  if (exact) return exact;
  const sameCity = airports.filter((airport) => fold(airport.city) === wanted);
  return sameCity.length === 1 ? sameCity[0] : null;
}

export interface AirportSection {
  title: string;
  airports: FlightAirport[];
}

interface AirportSectionsInput {
  /** Chữ đang gõ; rỗng thì hiện các nhóm mặc định. */
  text: string;
  airports: readonly FlightAirport[];
  /** Thành phố đã tìm gần đây (nhãn lưu ở trình duyệt); chỉ còn những sân bay hiện hành mới được hiện. */
  recent: readonly string[];
  /** Sân bay đã chọn ở ô kia: không đề xuất cùng một sân bay. */
  exclude?: FlightAirport | null;
}

/**
 * Các nhóm gợi ý theo thứ tự hiển thị: khi trống thì "Tìm gần đây", "Sân bay phổ biến" (nhiều tuyến nhất),
 * "Trong nước" (phần còn lại). Khi đang gõ chỉ còn một nhóm, cũng tên "Sân bay phổ biến" (các sân bay khớp chữ gõ). Nhóm trống thì không trả về.
 */
export function airportSections({ text, airports, recent, exclude }: AirportSectionsInput): AirportSection[] {
  const pool = exclude ? airports.filter((airport) => airport.code !== exclude.code) : [...airports];
  const wanted = fold(text);

  if (wanted) {
    // Thành phố bắt đầu bằng chữ gõ xếp trước, rồi tới khớp ở giữa tên (ví dụ "Đà" trước "Côn Đảo").
    const rank = (airport: FlightAirport) => (fold(airport.city).startsWith(wanted) || fold(airport.code).startsWith(wanted) ? 0 : 1);
    const matches = pool
      .filter((airport) => startsAWord(airport.city, text) || startsAWord(airport.code, text)
        || (airport.name !== null && startsAWord(airport.name, text)))
      .sort((a, b) => rank(a) - rank(b) || byCity(a, b))
      .slice(0, MAX_AIRPORT_MATCHES);
    return matches.length > 0 ? [{ title: POPULAR_TITLE, airports: matches }] : [];
  }

  const recentAirports: FlightAirport[] = [];
  for (const label of recent.slice(0, RECENT_AIRPORT_LIMIT)) {
    const airport = matchAirport(label, pool);
    if (airport && !recentAirports.some((item) => item.code === airport.code)) recentAirports.push(airport);
  }
  const taken = new Set(recentAirports.map((airport) => airport.code));
  const rest = pool.filter((airport) => !taken.has(airport.code));
  const popular = [...rest]
    .sort((a, b) => b.routeCount - a.routeCount || byCity(a, b))
    .slice(0, POPULAR_AIRPORT_LIMIT);
  const popularCodes = new Set(popular.map((airport) => airport.code));
  const domestic = rest.filter((airport) => !popularCodes.has(airport.code)).sort(byCity);

  const sections: AirportSection[] = [];
  if (recentAirports.length > 0) sections.push({ title: RECENT_TITLE, airports: recentAirports });
  if (popular.length > 0) sections.push({ title: POPULAR_TITLE, airports: popular });
  if (domestic.length > 0) sections.push({ title: DOMESTIC_TITLE, airports: domestic });
  return sections;
}

/** Mọi dòng theo đúng thứ tự hiển thị: dùng cho mũi tên lên xuống và Enter. */
export function flattenSections(sections: readonly AirportSection[]): FlightAirport[] {
  return sections.flatMap((section) => section.airports);
}
