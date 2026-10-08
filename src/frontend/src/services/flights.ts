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
