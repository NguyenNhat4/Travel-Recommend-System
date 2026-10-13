/**
 * Dữ liệu cho trang kết quả vé máy bay (`/flights?origin&destination`, docs/spec/hop-dong-tich-hop-frontend.md §4.1b).
 *
 * Không có endpoint riêng: dùng `GET /products` của catalog. Tuyến bay (`level: route`) là tầng cha, lọc theo điểm đến;
 * chuyến bay cụ thể (`level: flight`) là tầng con của tuyến, lấy bằng `parentProductId`. Mọi chuyến, giá, hạng vé hiển thị
 * trên Web đến từ hai lời gọi này (grounding, NFR-REL-01).
 */
import { listProducts, type ListProductsParams, type ProductSummary } from './catalog';

/** `limit` tối đa của contract. */
const PAGE_SIZE = 50;
/** Chặn vòng lặp nếu Backend báo `total` sai: 10 trang = 500 mục, gấp hàng chục lần tuyến đông nhất hiện có. */
const MAX_PAGES = 10;

async function allPages(params: Omit<ListProductsParams, 'limit' | 'offset'>, signal?: AbortSignal): Promise<ProductSummary[]> {
  const items: ProductSummary[] = [];
  for (let page = 0; page < MAX_PAGES; page++) {
    const response = await listProducts({ ...params, limit: PAGE_SIZE, offset: page * PAGE_SIZE }, signal);
    items.push(...response.results);
    if (response.results.length < PAGE_SIZE || items.length >= response.total) break;
  }
  return items;
}

/** Các tuyến bay đến một điểm đến (nhãn chuẩn của `/destinations`). Không có tuyến nào thì trả mảng rỗng. */
export async function listRoutesTo(destination: string, signal?: AbortSignal): Promise<ProductSummary[]> {
  const products = await allPages({ taxonomy: 'flight', destination }, signal);
  return products.filter((product) => (product.attributes as Record<string, unknown> | undefined)?.level === 'route');
}

/** Mọi chuyến bay (tầng con) của một tuyến, kể cả vé khứ hồi và các hạng vé; lọc và gom ở `flightModel`. */
export function listRouteFlights(routeProductId: string, signal?: AbortSignal): Promise<ProductSummary[]> {
  return allPages({ parentProductId: routeProductId, sort: 'price_asc' }, signal);
}

/**
 * Sân bay hiện hành: một mã IATA gắn với thành phố của tuyến còn bán (spec ui-dia-diem-san-bay-va-khach-san-noi-tieng §2.1).
 * Không có danh sách sân bay cố định nào trong mã nguồn: mọi sân bay đến từ `attributes` của tuyến trong catalog.
 */
export interface FlightAirport {
  /** Mã IATA, ví dụ "SGN". */
  code: string;
  /** Đúng giá trị `originCity` / `destinationCity` của catalog; cũng là điểm đi, điểm đến trên URL. */
  city: string;
  /** `destinationAirportName` của catalog; null khi catalog chưa có tên cho mã này. */
  name: string | null;
  /** Số tuyến còn bán đi hoặc đến sân bay này: dùng để xếp "phổ biến". */
  routeCount: number;
}

const textOf = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');
const codesOf = (value: unknown): string[] => (Array.isArray(value) ? value.map(textOf).filter(Boolean) : []);

/**
 * Gom sân bay từ các tuyến (tầng cha của `GET /products`). Một tuyến góp mỗi sân bay của nó một lần vào `routeCount`.
 * Tên lấy từ `destinationAirportName` khi tuyến chỉ có một sân bay đến. Thứ tự kết quả: thành phố, rồi mã.
 */
export function collectFlightAirports(routes: readonly ProductSummary[]): FlightAirport[] {
  const airports = new Map<string, FlightAirport>();
  for (const route of routes) {
    const a = (route.attributes ?? {}) as Record<string, unknown>;
    if (a.level !== 'route') continue;
    const touched = new Set<string>();
    const sides = [
      { city: textOf(a.originCity), codes: codesOf(a.originAirports) },
      { city: textOf(a.destinationCity), codes: codesOf(a.destinationAirports) },
    ];
    for (const side of sides) {
      if (!side.city) continue;
      for (const code of side.codes) {
        if (!airports.has(code)) airports.set(code, { code, city: side.city, name: null, routeCount: 0 });
        if (!touched.has(code)) {
          touched.add(code);
          airports.get(code)!.routeCount += 1;
        }
      }
    }
    const destinationCodes = codesOf(a.destinationAirports);
    const name = textOf(a.destinationAirportName);
    const airport = destinationCodes.length === 1 ? airports.get(destinationCodes[0]) : undefined;
    if (name && airport && !airport.name) airport.name = name;
  }
  return [...airports.values()].sort((x, y) => x.city.localeCompare(y.city, 'vi') || x.code.localeCompare(y.code));
}

/** Sân bay hiện hành: mọi tuyến còn bán (`availableOnly`), gom theo `collectFlightAirports`. */
export async function listFlightAirports(signal?: AbortSignal): Promise<FlightAirport[]> {
  return collectFlightAirports(await allPages({ taxonomy: 'flight', availableOnly: true }, signal));
}

/** Sân bay đi có trong catalog: tên thành phố (`originCity`, đúng giá trị Backend nhận) và toạ độ sân bay. */
export interface DepartureAirport {
  city: string;
  latitude: number;
  longitude: number;
}

/**
 * Mọi thành phố có tuyến bay khởi hành trong catalog, lấy từ thuộc tính của tuyến (`originCity`, `originLatitude`,
 * `originLongitude`). Dùng để gợi ý nơi đi từ vị trí trình duyệt (AC-AGT-03): chỉ gợi ý nơi thật sự có chuyến bay.
 */
export async function listDepartureAirports(signal?: AbortSignal): Promise<DepartureAirport[]> {
  const routes = await allPages({ taxonomy: 'flight' }, signal);
  const airports = new Map<string, DepartureAirport>();
  for (const route of routes) {
    const attributes = (route.attributes ?? {}) as Record<string, unknown>;
    const city = attributes.originCity;
    const latitude = Number(attributes.originLatitude);
    const longitude = Number(attributes.originLongitude);
    if (typeof city === 'string' && city && Number.isFinite(latitude) && Number.isFinite(longitude) && !airports.has(city)) {
      airports.set(city, { city, latitude, longitude });
    }
  }
  return [...airports.values()];
}

/** Khoảng cách theo đường tròn lớn (km). */
function distanceKm(a: { latitude: number; longitude: number }, b: { latitude: number; longitude: number }): number {
  const rad = (degrees: number) => (degrees * Math.PI) / 180;
  const dLat = rad(b.latitude - a.latitude);
  const dLng = rad(b.longitude - a.longitude);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

/**
 * Thành phố có sân bay gần vị trí nhất; `null` khi catalog chưa có sân bay nào. Toạ độ chỉ dùng tại đây trong trình
 * duyệt, không lưu và không gửi đi: Web chỉ gửi tên thành phố (AC-AGT-03).
 */
export function nearestDepartureCity(
  position: { latitude: number; longitude: number },
  airports: DepartureAirport[],
): string | null {
  let best: DepartureAirport | null = null;
  let bestDistance = Infinity;
  for (const airport of airports) {
    const distance = distanceKm(position, airport);
    if (distance < bestDistance) {
      best = airport;
      bestDistance = distance;
    }
  }
  return best?.city ?? null;
}
