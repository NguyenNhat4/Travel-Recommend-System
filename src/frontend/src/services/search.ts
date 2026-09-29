/**
 * Semantic search — POST /api/v1/search qua BFF (docs/spec/hop-dong-tich-hop-frontend.md §4.2).
 *
 * Không có tìm kiếm cục bộ: lỗi thì ném `ApiError`, SearchView hiện ErrorState + Thử lại (503 SEARCH_UNAVAILABLE
 * giữ nguyên truy vấn trong ô).
 */

import { Product, Destination, Taxonomy } from '../types/travel';
import { productFromApi } from './catalog';
import { apiJson } from './http';
export interface SearchFilters {
  destination?: Destination[];
  taxonomy?: Taxonomy;
  minPrice?: number;
  maxPrice?: number;
  minStarRating?: number;
}

export type SortOption = 'relevance' | 'price_asc' | 'price_desc';

/**
 * Câu truy vấn thay cho ô trống theo danh mục: `/search?type=flight` không có `q` phải tìm "vé máy bay",
 * không phải "khách sạn" rồi mới lọc theo danh mục. Không lọc danh mục thì giữ 'khách sạn' như trước.
 */
export const DEFAULT_QUERY: Record<Taxonomy, string> = {
  hotel: 'khách sạn',
  flight: 'vé máy bay',
  attraction: 'vé tham quan',
  golf: 'sân golf',
  combo: 'combo du lịch',
};

export interface SearchResultItem {
  product: Product;
  relevanceScore: number;
  matchTags: string[];
}

export interface SearchResponse {
  query: string;
  total: number;
  /** false khi backend chỉ đếm trên top-K ứng viên (ANN_CANDIDATE_SCORE): total là cận dưới. */
  totalExact?: boolean;
  results: SearchResultItem[];
  isWeakMatch: boolean;
  categoryCounts: Record<string, number>;
}

const TAXONOMY_TAG: Record<Taxonomy, string> = {
  hotel: 'Khách sạn', flight: 'Vé máy bay', attraction: 'Vé tham quan', combo: 'Combo', golf: 'Sân Golf',
};

/** Giá null (chưa có giá) luôn xếp cuối, bất kể chiều sắp xếp. */
function byPrice(direction: 1 | -1) {
  return (a: SearchResultItem, b: SearchResultItem) => {
    const pa = a.product.unitPrice, pb = b.product.unitPrice;
    if (pa == null || pb == null) return (pa == null ? 1 : 0) - (pb == null ? 1 : 0);
    return direction * (pa - pb);
  };
}

export async function searchProductsApi(
  query: string,
  filters: SearchFilters = {},
  sort: SortOption = 'relevance',
  limit: number = 20,
  offset: number = 0
): Promise<SearchResponse> {
  const cleanQ = query.trim();
  const destination = filters.destination && filters.destination.length > 0 ? filters.destination[0] : undefined;
  const data: any = await apiJson('/api/v1/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: cleanQ || DEFAULT_QUERY[filters.taxonomy ?? 'hotel'],
      taxonomy: filters.taxonomy || null,
      destination: destination || null,
      limit,
      offset,
    }),
  });

  let results: SearchResultItem[] = (Array.isArray(data.results) ? data.results : []).map((item: any) => {
    const product: Product = productFromApi(item);
    return {
      product,
      relevanceScore: typeof item.score === 'number' ? item.score : 0,
      matchTags: [product.destination, TAXONOMY_TAG[product.taxonomy]].filter(Boolean),
    };
  });

  // Bộ lọc giá/sao chưa có trong request nên lọc trên trang đã nhận; sản phẩm chưa có giá không qua lọc giá.
  if (filters.minPrice !== undefined) {
    results = results.filter(r => r.product.unitPrice != null && r.product.unitPrice >= filters.minPrice!);
  }
  if (filters.maxPrice !== undefined) {
    results = results.filter(r => r.product.unitPrice != null && r.product.unitPrice <= filters.maxPrice!);
  }
  if (filters.minStarRating !== undefined) {
    results = results.filter(r => !r.product.attributes.starRating || r.product.attributes.starRating >= filters.minStarRating!);
  }

  // 'relevance' giữ nguyên thứ tự backend: hybrid sắp theo RRF (spec §2.2), còn score là cosine nên không
  // dùng nó để sắp lại — sắp lại sẽ đẩy kết quả khớp tên/thương hiệu xuống cuối.
  if (sort === 'price_asc') {
    results.sort(byPrice(1));
  } else if (sort === 'price_desc') {
    results.sort(byPrice(-1));
  }

  const facetsTax = data.facets?.taxonomy || {};
  const count = (taxonomy: Taxonomy) => facetsTax[taxonomy] ?? results.filter(r => r.product.taxonomy === taxonomy).length;
  const categoryCounts: Record<string, number> = {
    all: data.total || results.length,
    hotel: count('hotel'), flight: count('flight'), attraction: count('attraction'), combo: count('combo'), golf: count('golf'),
  };

  return {
    query: cleanQ,
    total: data.total ?? results.length,
    totalExact: data.diagnostics?.totalExact,
    results,
    // frontend §6.4: băng "kết quả yếu" khi topScore < 0.35; null thì không hiện.
    isWeakMatch: typeof data.topScore === 'number' && data.topScore < WEAK_RESULT_TOP_SCORE,
    categoryCounts,
  };
}

export const WEAK_RESULT_TOP_SCORE = 0.35;

export const EMPTY_SEARCH_RESPONSE: SearchResponse = {
  query: '', total: 0, results: [], isWeakMatch: false,
  categoryCounts: { all: 0, hotel: 0, flight: 0, attraction: 0, combo: 0, golf: 0 },
};
