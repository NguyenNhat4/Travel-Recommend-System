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
  /** `priceMin` / `priceMax` của POST /search: hard filter trên giá thấp nhất (kể cả phòng con); chưa có giá thì bị loại. */
  minPrice?: number;
  maxPrice?: number;
  /** `starRatingMin`: soft filter ([C6]) — sản phẩm khai sao thấp hơn bị loại, chưa khai sao vẫn giữ và xếp sau. */
  minStarRating?: number;
  /** Số khách một phòng/đơn vị: hard filter sức chứa ở POST /search (travelContext.guests, contract 1.16.0). */
  guests?: Guests;
  /** Ngày nhận phòng / ngày dùng (YYYY-MM-DD) và ngày trả (không bao gồm): hard filter ngày ở POST /search (contract 1.19.0). */
  stay?: Stay;
}

/** `travelContext.checkIn` / `checkOut`: chỉ ngày dùng (vé, combo) thì không có `checkOut`. */
export interface Stay {
  checkIn: string;
  checkOut?: string;
}

/** `travelContext.guests`: tổng `adults + children` là sức chứa tối thiểu; chỉ có trẻ em thì backend không lọc. */
export interface Guests {
  adults: number;
  children: number;
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
  results: SearchResultItem[];
  /** Cosine cao nhất trong toàn bộ kết quả; null khi rỗng. */
  topScore: number | null;
  isWeakMatch: boolean;
  /** Cụm khiến câu không có đáp án (`diagnostics.queryPlan.unexplained`, contract 1.28.0); [] khi không có. */
  unexplained: string[];
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
      ...(filters.minPrice !== undefined ? { priceMin: filters.minPrice } : {}),
      ...(filters.maxPrice !== undefined ? { priceMax: filters.maxPrice } : {}),
      ...(filters.minStarRating !== undefined ? { starRatingMin: filters.minStarRating } : {}),
      ...(filters.guests || filters.stay ? { travelContext: {
        ...(filters.guests ? { guests: filters.guests } : {}),
        ...(filters.stay ? { checkIn: filters.stay.checkIn, ...(filters.stay.checkOut ? { checkOut: filters.stay.checkOut } : {}) } : {}),
      } } : {}),
    }),
  });

  const results: SearchResultItem[] = (Array.isArray(data.results) ? data.results : []).map((item: any) => {
    const product: Product = productFromApi(item);
    return {
      product,
      relevanceScore: typeof item.score === 'number' ? item.score : 0,
      matchTags: [product.destination, TAXONOMY_TAG[product.taxonomy]].filter(Boolean),
    };
  });

  // 'relevance' giữ nguyên thứ tự backend: hybrid sắp theo RRF (spec §2.2), còn score là cosine nên không
  // dùng nó để sắp lại — sắp lại sẽ đẩy kết quả khớp tên/thương hiệu xuống cuối.
  if (sort === 'price_asc') {
    results.sort(byPrice(1));
  } else if (sort === 'price_desc') {
    results.sort(byPrice(-1));
  }

  const topScore = typeof data.topScore === 'number' ? data.topScore : null;
  const backgroundScore = typeof data.backgroundScore === 'number' ? data.backgroundScore : null;
  const diagnostics = data.diagnostics ?? {};
  const filteredCount = typeof diagnostics.filteredCount === 'number' ? diagnostics.filteredCount : 0;
  const unexplained = Array.isArray(diagnostics.queryPlan?.unexplained) ? diagnostics.queryPlan.unexplained : [];
  return {
    query: cleanQ,
    total: data.total ?? results.length,
    results,
    topScore,
    isWeakMatch: isWeakMatch(topScore, backgroundScore, filteredCount, diagnostics.filterOnly === true),
    unexplained,
  };
}

export const WEAK_RESULT_TOP_SCORE = 0.35;
/** Quy tắc margin (spec tích hợp §3.4; plan 2026-10-13 §2.7) — giá trị tạm, chốt lại trên split dev của gold. */
export const WEAK_RESULT_MARGIN = 0.058;
export const WEAK_TOP_CEILING = 0.88;
export const WEAK_MIN_FILTERED = 20;

/**
 * frontend §6.4: băng "kết quả gần nhất". Không có kết quả → không hiện. Backend phát `backgroundScore` (cờ
 * SEARCH_EMIT_BACKGROUND) → yếu khi top chỉ nhỉnh hơn nền (margin nhỏ) VÀ top dưới trần, và chỉ khi tập đã lọc đủ lớn (điểm
 * đến nhỏ thì nền ≈ top, margin vô nghĩa); chế độ chỉ-filter không gắn nhãn. Không có `backgroundScore` → luật cũ topScore < 0.35.
 */
export function isWeakMatch(topScore: number | null, backgroundScore: number | null = null, filteredCount = 0,
                            filterOnly = false): boolean {
  if (topScore === null || filterOnly) return false;
  if (topScore < WEAK_RESULT_TOP_SCORE) return true;
  if (backgroundScore === null || filteredCount < WEAK_MIN_FILTERED) return false;
  return topScore - backgroundScore < WEAK_RESULT_MARGIN && topScore < WEAK_TOP_CEILING;
}

/**
 * Nhóm hiển thị của `/search` (khớp nhóm ở header, navConfig): Lưu trú, Tour và trải nghiệm, Tiện ích khác.
 * Vé máy bay không nằm trong tìm kiếm ngữ nghĩa: nhóm `flight` chỉ có khi trang được mở từ /flights
 * (`?type=flight`), không có tab.
 */
export type SearchGroup = 'stay' | 'exp' | 'more' | 'flight';
export type TabGroup = Exclude<SearchGroup, 'flight'>;

export const TAB_GROUPS: readonly TabGroup[] = ['stay', 'exp', 'more'];

export const SEARCH_GROUPS: Record<SearchGroup, { label: string; taxonomies: Taxonomy[] }> = {
  stay: { label: 'Lưu trú', taxonomies: ['hotel'] },
  exp: { label: 'Tour và trải nghiệm', taxonomies: ['attraction', 'golf'] },
  more: { label: 'Tiện ích khác', taxonomies: ['combo'] },
  flight: { label: 'Vé máy bay', taxonomies: ['flight'] },
};

/** Số mục mỗi nhóm ở tab "Tất cả" (chỉ để xem nhanh) và mỗi lần "Xem thêm" ở tab nhóm. */
export const PREVIEW_LIMIT = 6;
export const GROUP_PAGE_SIZE = 20;

/** `?type=` nhận id nhóm hoặc taxonomy cũ (từ trang danh mục: hotel, attraction, golf, combo, flight). */
export function parseGroupParam(raw: string | null | undefined): SearchGroup | undefined {
  if (!raw) return undefined;
  if (raw in SEARCH_GROUPS) return raw as SearchGroup;
  return (Object.keys(SEARCH_GROUPS) as SearchGroup[]).find((g) => SEARCH_GROUPS[g].taxonomies.includes(raw as Taxonomy));
}

export interface GroupPage {
  items: SearchResultItem[];
  /** Tổng số kết quả của cả nhóm (không phải của trang). */
  total: number;
  hasMore: boolean;
  /** `topScore` cao nhất của các request trong nhóm; null khi cả nhóm rỗng. */
  topScore: number | null;
  /** Request có `topScore` cao nhất của nhóm bị coi là yếu (`isWeakMatch`). */
  isWeakMatch: boolean;
  /** Cụm khiến câu không có đáp án (gộp các request của nhóm). */
  unexplained: string[];
}

/** Bộ lọc thanh bên của tab Lưu trú: gửi lên API nên `total` và "Xem thêm" đếm theo đúng bộ lọc. */
export interface PriceStarFilter {
  maxPrice?: number;
  minStarRating?: number;
}

/**
 * Một trang kết quả của một nhóm: mỗi taxonomy trong nhóm là một `POST /search` (contract chỉ nhận một taxonomy),
 * chạy song song. Nhóm có hai taxonomy (attraction + golf) được trộn theo `score` giảm dần.
 */
export async function searchGroupApi(
  query: string,
  group: SearchGroup,
  { destination, limit, offset = 0, taxonomy: only, guests, stay, maxPrice, minStarRating }: {
    destination?: string | null; limit: number; offset?: number; taxonomy?: Taxonomy; guests?: Guests; stay?: Stay;
  } & PriceStarFilter,
): Promise<GroupPage> {
  // `taxonomy` thu hẹp nhóm về một loại (tab Vé tham quan / Sân golf ở /experiences); không có thì cả nhóm.
  const taxonomies = only && SEARCH_GROUPS[group].taxonomies.includes(only) ? [only] : SEARCH_GROUPS[group].taxonomies;
  const responses = await Promise.all(taxonomies.map((taxonomy) => searchProductsApi(
    query,
    { taxonomy, destination: destination ? [destination as Destination] : undefined, guests, stay, maxPrice, minStarRating },
    'relevance',
    limit,
    offset,
  )));
  const merged = responses.flatMap((r) => r.results);
  if (responses.length > 1) merged.sort((a, b) => b.relevanceScore - a.relevanceScore);
  return {
    items: merged,
    total: responses.reduce((sum, r) => sum + r.total, 0),
    hasMore: responses.some((r) => r.total > offset + limit),
    topScore: maxScore(responses.map((r) => r.topScore)),
    isWeakMatch: strongest(responses)?.isWeakMatch ?? false,
    unexplained: [...new Set(responses.flatMap((r) => r.unexplained))],
  };
}

/** Request có topScore cao nhất (null khi mọi request rỗng). */
function strongest<T extends { topScore: number | null }>(pages: T[]): T | null {
  return pages.reduce<T | null>((best, p) => (p.topScore !== null && (best === null || best.topScore === null
    || p.topScore > best.topScore) ? p : best), null);
}

function maxScore(scores: Array<number | null>): number | null {
  const known = scores.filter((s): s is number => s !== null);
  return known.length > 0 ? Math.max(...known) : null;
}

/** Khóa bộ đệm của hàng một nhóm ở tab "Tất cả" (trang đầu, `PREVIEW_LIMIT` mục); số trên tab dùng chung khóa này. */
export function shelfCacheKey(query: string, destination: string | null | undefined, group: TabGroup): string {
  return searchCacheKey('group', query, destination, group, PREVIEW_LIMIT, 0);
}

export function searchShelfApi(query: string, group: TabGroup, destination?: string | null): Promise<GroupPage> {
  return searchGroupApi(query, group, { destination, limit: PREVIEW_LIMIT, offset: 0 });
}

export interface SearchOverview {
  counts: Record<TabGroup, number>;
  /** Tổng ba nhóm, không tính vé máy bay. */
  total: number;
  isWeakMatch: boolean;
  /** Cụm khiến câu không có đáp án (contract 1.28.0); [] khi không có. */
  unexplained: string[];
}

/** Tải qua bộ đệm theo khóa (`hooks/useLazySection` `loadSection`). */
export type SectionLoader = <T>(key: string, fetcher: () => Promise<T>) => Promise<T>;

/**
 * Số kết quả mỗi nhóm cho các tab: `total` của chính các request hàng ở tab "Tất cả" (cùng `shelfCacheKey`, nên qua
 * `load` có bộ đệm thì hàng đọc lại kết quả, không gọi thêm), "Tất cả" là tổng ba nhóm.
 *
 * Không đếm bằng `facets.taxonomy` của một request không lọc taxonomy: backend tính tập kết quả trên tập đã lọc của
 * TỪNG request (top-K dense, 10 suất vớt BM25 dùng chung cho mọi loại, kể cả vé máy bay), nên facets đó thường nhỏ
 * hơn `total` của request lọc theo loại và số trên tab lệch số trên hàng, trên "Xem thêm".
 */
export async function searchOverviewApi(
  query: string,
  destination?: string | null,
  load: SectionLoader = (_key, fetcher) => fetcher(),
): Promise<SearchOverview> {
  const pages = await Promise.all(TAB_GROUPS.map((group) => load(
    shelfCacheKey(query, destination, group),
    () => searchShelfApi(query, group, destination),
  )));
  const counts = Object.fromEntries(TAB_GROUPS.map((group, i) => [group, pages[i].total])) as Record<TabGroup, number>;
  return {
    counts,
    total: pages.reduce((sum, page) => sum + page.total, 0),
    isWeakMatch: strongest(pages)?.isWeakMatch ?? false,
    unexplained: [...new Set(pages.flatMap((page) => page.unexplained ?? []))],
  };
}

/**
 * Sắp xếp trên các mục đã tải (backend chưa nhận `sort`); 'relevance' giữ thứ tự backend. Sản phẩm chưa có giá luôn
 * xếp cuối.
 */
export function sortItems(items: SearchResultItem[], sort: SortOption): SearchResultItem[] {
  if (sort === 'price_asc') return [...items].sort(byPrice(1));
  if (sort === 'price_desc') return [...items].sort(byPrice(-1));
  return items;
}

/** Khóa bộ đệm (`hooks/useLazySection`): cùng truy vấn, điểm đến, nhóm, giới hạn và bộ lọc thì dùng lại kết quả. */
export function searchCacheKey(kind: 'overview' | 'group', query: string, destination: string | null | undefined, group?: SearchGroup, limit?: number, offset?: number, taxonomy?: Taxonomy, guests?: Guests, stay?: Stay, filter?: PriceStarFilter): string {
  const parts = ['search', kind, query.trim().toLowerCase(), destination ?? '', group ?? '', limit ?? '', offset ?? ''];
  if (taxonomy) parts.push(taxonomy);
  if (guests) parts.push(`g${guests.adults}-${guests.children}`);
  if (stay) parts.push(`d${stay.checkIn}~${stay.checkOut ?? ''}`);
  if (filter?.maxPrice !== undefined) parts.push(`p${filter.maxPrice}`);
  if (filter?.minStarRating !== undefined) parts.push(`s${filter.minStarRating}`);
  return parts.join('|');
}
