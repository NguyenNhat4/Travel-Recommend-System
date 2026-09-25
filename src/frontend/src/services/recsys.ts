/**
 * Gợi ý cá nhân hoá — GET /api/v1/recommendations qua BFF (docs/spec/hop-dong-tich-hop-frontend.md §4.1).
 *
 * Danh tính đi theo cookie phiên; không gửi cdp_user_id (IDOR, auth §3.5). Không có bộ giả lập cục bộ:
 * lỗi thì ném `ApiError` để trang ẩn khối gợi ý và hiện "Chưa tải được gợi ý · Thử lại" (product.md §4.1.5),
 * không bao giờ thay bằng sản phẩm giả.
 */
import type { components } from '../types/api.gen';
import type { BecauseItem, Destination, RecommendationResponse, Taxonomy } from '../types/travel';
import { productFromApi } from './catalog';
import { apiJson } from './http';

type ApiRecommendationResponse = components['schemas']['RecommendationResponse'];
type ApiRecommendationItem = components['schemas']['RecommendationItem'];

export interface FetchRecommendationsParams {
  k?: number;
  destination?: string;
  signal?: AbortSignal;
}

function because(item: ApiRecommendationItem): BecauseItem[] {
  return (item.because ?? []).map((b: any) => ({
    productId: b.productId ?? undefined,
    productName: b.productName,
    event: b.event,
    daysAgo: typeof b.daysAgo === 'number' ? Math.round(b.daysAgo) : 0,
    contribution: typeof b.contribution === 'number' ? b.contribution : 0,
    imageUrl: b.imageUrl ?? undefined,
  }));
}

export async function fetchRecommendations(params: FetchRecommendationsParams = {}): Promise<RecommendationResponse> {
  const { k = 4, destination, signal } = params;
  const search = new URLSearchParams({ k: String(k) });
  if (destination) search.set('destination', destination);
  const data = await apiJson<ApiRecommendationResponse>(`/api/v1/recommendations?${search}`, {
    headers: { Accept: 'application/json' },
    cache: 'no-store',
    signal,
  });
  const diagnostics: any = data.diagnostics ?? {};
  return {
    strategy: data.strategy,
    nextVertical: (data as any).nextVertical ?? undefined,
    destination: ((data as any).destination ?? undefined) as Destination | undefined,
    recommendations: (data.recommendations ?? []).map((item, idx) => ({
      product: productFromApi(item as any),
      score: typeof (item as any).score === 'number' ? (item as any).score : 0,
      rank: typeof (item as any).rank === 'number' ? (item as any).rank : idx + 1,
      because: because(item),
    })),
    diagnostics: {
      eventsUsed: diagnostics.eventsUsed ?? 0,
      coldStart: diagnostics.coldStart ?? false,
      excludedVerticals: (diagnostics.excludedVerticals ?? []) as Taxonomy[],
      modelVersion: diagnostics.modelVersion ?? (data as any).modelVersion ?? '',
      latencyMs: diagnostics.latencyMs,
    },
    generatedAt: (data as any).generatedAt ?? new Date().toISOString(),
  };
}
