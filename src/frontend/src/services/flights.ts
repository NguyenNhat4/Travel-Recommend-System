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
