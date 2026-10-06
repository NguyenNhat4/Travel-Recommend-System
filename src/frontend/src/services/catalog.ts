/**
 * Catalog qua BFF `/api/v1/*` (docs/spec/hop-dong-tich-hop-frontend.md §4.1, §4.3; backend §4, §7.5).
 *
 * Mọi sản phẩm hiển thị trên Web đến từ đây, Search, Recommendation hoặc Assistant — không có catalog cục bộ.
 * Khách sạn (`level: property`) và tuyến bay (`level: route`) chỉ để xem; khách đặt tầng con của chúng
 * (hạng phòng, chuyến bay cụ thể) lấy bằng `listVariants`.
 */
import type { components } from '../types/api.gen';
import type { Destination, Product, Taxonomy } from '../types/travel';
import { apiFetch, apiJson } from './http';

export type ProductSummary = components['schemas']['ProductSummary'];
export type ProductDetail = components['schemas']['ProductDetail'];
export type ProductListResponse = components['schemas']['ProductListResponse'];
export type SimilarProductsResponse = components['schemas']['SimilarProductsResponse'];
export type ProductSort = components['schemas']['ProductSort'];
export type VariantSummary = NonNullable<ProductDetail['variantSummary']>;

export interface ListProductsParams {
  destination?: string;
  taxonomy?: Taxonomy;
  availableOnly?: boolean;
  sort?: ProductSort;
  limit?: number;
  offset?: number;
  parentProductId?: string;
}

const PLACEHOLDER_IMAGE: Record<Taxonomy, string> = {
  hotel: '/placeholders/hotel.svg',
  flight: '/placeholders/flight.svg',
  attraction: '/placeholders/attraction.svg',
  combo: '/placeholders/combo.svg',
  golf: '/placeholders/golf.svg',
};

/** Ảnh thay thế theo loại khi `imageUrl` null hoặc tải lỗi (docs/spec/hop-dong-tich-hop-frontend.md §6.6). */
export function placeholderImage(taxonomy: string): string {
  return PLACEHOLDER_IMAGE[taxonomy as Taxonomy] ?? PLACEHOLDER_IMAGE.hotel;
}

function coordinates(attributes: Record<string, unknown>): Product['coordinates'] {
  const lat = Number(attributes.latitude);
  const lng = Number(attributes.longitude);
  return Number.isFinite(lat) && Number.isFinite(lng) && (lat !== 0 || lng !== 0) ? { lat, lng } : undefined;
}

/**
 * ProductSummary/ProductDetail của API → Product hiển thị. Tên, giá, ảnh lấy nguyên từ response (grounding);
 * tọa độ và địa chỉ đọc từ `attributes` của catalog, không có thì để trống.
 */
export function productFromApi(summary: ProductSummary | ProductDetail): Product {
  const attributes = (summary.attributes || {}) as Record<string, any>;
  const taxonomy = summary.taxonomy as Taxonomy;
  return {
    id: summary.productId,
    name: summary.name,
    taxonomy,
    destination: summary.destination as Destination,
    unitPrice: summary.unitPrice ?? null,
    currency: 'VND',
    imageUrl: summary.imageUrl || PLACEHOLDER_IMAGE[taxonomy] || PLACEHOLDER_IMAGE.hotel,
    description: summary.description ?? '',
    attributes,
    available: summary.available,
    availableFrom: summary.availableFrom ?? undefined,
    availableTo: summary.availableTo ?? undefined,
    aggregateRating: summary.rating != null
      ? { score: summary.rating, count: summary.reviewCount ?? 0 }
      : undefined,
    coordinates: coordinates(attributes),
    address: typeof attributes.address === 'string' && attributes.address ? attributes.address : summary.destination,
    level: typeof attributes.level === 'string' ? attributes.level : undefined,
    parentProductId: typeof attributes.parentProductId === 'string' ? attributes.parentProductId : undefined,
  };
}

/** Khách sạn và tuyến bay đặt qua tầng con; mọi loại khác đặt trực tiếp. */
export function hasVariants(product: Pick<Product, 'level'>): boolean {
  return product.level === 'property' || product.level === 'route';
}

function query(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

export function getProduct(productId: string, signal?: AbortSignal): Promise<ProductDetail> {
  return apiJson(`/api/v1/products/${encodeURIComponent(productId)}`, { signal });
}

export function listProducts(params: ListProductsParams = {}, signal?: AbortSignal): Promise<ProductListResponse> {
  return apiJson(`/api/v1/products${query(params)}`, { signal });
}

/** Hạng phòng / chuyến bay của một sản phẩm cha, rẻ nhất trước. */
export function listVariants(parentProductId: string, signal?: AbortSignal): Promise<ProductListResponse> {
  return listProducts({ parentProductId, sort: 'price_asc', limit: 50 }, signal);
}

export function getSimilarProducts(productId: string, limit = 8, signal?: AbortSignal): Promise<SimilarProductsResponse> {
  return apiJson(`/api/v1/products/${encodeURIComponent(productId)}/similar${query({ limit })}`, { signal });
}

/**
 * Ghi `product_view` (FR-CDP-01). Chỉ gọi khi đã đăng nhập, một lần mỗi lần mở trang chi tiết.
 * Mọi lỗi bỏ qua im lặng (frontend §4.3): ghi hành vi không được làm hỏng trang.
 */
export async function trackProductView(productId: string): Promise<void> {
  try {
    await apiFetch('/api/v1/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ eventName: 'product_view', productId }),
    });
  } catch {
    /* bỏ qua */
  }
}
