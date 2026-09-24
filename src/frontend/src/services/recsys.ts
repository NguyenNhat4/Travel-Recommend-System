/**
 * Recommendation Engine Simulator & Client Service
 * Implements spec §5:
 * C1 (Section title based on strategy)
 * C2 (Trip checklist: [✓ Khách sạn] [○ Vé máy bay] [○ Vé tham quan])
 * C3 (BecauseLine on card with relative time & event verb)
 * C4 (WhyPopover with qualitative contribution dots)
 */

import { CATALOG } from '../data/catalog';
import { Product, RecommendationResponse, UserPersona, UserEvent, Taxonomy, Destination, BecauseItem } from '../types/travel';
import { apiFetch } from './http';

export function calculateRecommendations(
  user: UserPersona | null,
  activeEvents: UserEvent[] = []
): RecommendationResponse {
  const allEvents = [...(user?.seedEvents || []), ...activeEvents];
  const now = Date.now();

  // Guest or P4 with 0 events
  if (!user || (user.id === 'P4' && allEvents.length === 0)) {
    const popularProducts = CATALOG.filter(p => p.available).slice(0, 5);
    return {
      strategy: 'popular',
      recommendations: popularProducts.map((p, idx) => ({
        product: p,
        score: +(0.85 - idx * 0.05).toFixed(2),
        rank: idx + 1,
        because: []
      })),
      diagnostics: {
        eventsUsed: 0,
        coldStart: true,
        excludedVerticals: [],
        modelVersion: 'v3.2-prod-hybrid',
        latencyMs: 14
      },
      generatedAt: new Date().toISOString()
    };
  }

  // P3 Dormant
  if (user.isDormant) {
    const nhaTrangProducts = CATALOG.filter(p => p.destination === 'Nha Trang' && p.taxonomy !== 'hotel');
    return {
      strategy: 'dormant',
      destination: 'Nha Trang',
      recommendations: nhaTrangProducts.slice(0, 4).map((p, idx) => ({
        product: p,
        score: +(0.78 - idx * 0.04).toFixed(2),
        rank: idx + 1,
        because: [
          {
            productId: 'nt-hotel-01',
            productName: 'V-OTA Resort Nha Trang - Deluxe Ocean View',
            event: 'purchase',
            daysAgo: 180,
            contribution: 0.65
          }
        ]
      })),
      diagnostics: {
        eventsUsed: 1,
        coldStart: false,
        excludedVerticals: ['hotel'],
        modelVersion: 'v3.2-dormant-revival',
        latencyMs: 18
      },
      generatedAt: new Date().toISOString()
    };
  }

  // P2 Cold Start with recent views
  if (user.id === 'P2' && !allEvents.some(e => e.eventType === 'purchase')) {
    const viewedProductIds = allEvents.map(e => e.productId);
    const relatedProducts = CATALOG.filter(p => p.destination === 'Nha Trang' && !viewedProductIds.includes(p.id));
    return {
      strategy: 'recent_views',
      destination: 'Nha Trang',
      recommendations: relatedProducts.slice(0, 4).map((p, idx) => ({
        product: p,
        score: +(0.82 - idx * 0.05).toFixed(2),
        rank: idx + 1,
        because: [
          {
            productId: 'nt-hotel-01',
            productName: 'V-OTA Resort Nha Trang - Deluxe Ocean View',
            event: 'product_view',
            daysAgo: 1,
            contribution: 0.55
          }
        ]
      })),
      diagnostics: {
        eventsUsed: allEvents.length,
        coldStart: true,
        excludedVerticals: [],
        modelVersion: 'v3.2-coldstart-session',
        latencyMs: 15
      },
      generatedAt: new Date().toISOString()
    };
  }

  // Check recent purchase events across all events (including just booked ones)
  const recentPurchases = allEvents.filter(e => e.eventType === 'purchase');
  const bookedTaxonomies: Taxonomy[] = Array.from(new Set(recentPurchases.map(e => e.taxonomy)));
  if (user.bookedVerticals) {
    user.bookedVerticals.forEach(t => {
      if (!bookedTaxonomies.includes(t)) bookedTaxonomies.push(t);
    });
  }

  const destination: Destination = (recentPurchases[recentPurchases.length - 1]?.destination as Destination) || user.activeDestination || 'Nha Trang';

  // Determine next vertical
  let nextVertical: Taxonomy = 'flight';
  if (bookedTaxonomies.includes('flight') && !bookedTaxonomies.includes('attraction')) {
    nextVertical = 'attraction';
  } else if (bookedTaxonomies.includes('flight') && bookedTaxonomies.includes('attraction')) {
    nextVertical = 'combo';
  }

  // Exclude booked verticals to prevent suggesting duplicate hotel
  const availableCandidates = CATALOG.filter(p => 
    p.destination === destination && 
    !bookedTaxonomies.includes(p.taxonomy) &&
    p.available
  );

  // If few candidates, add attraction/combo
  const recommendationsPool = availableCandidates.length > 0 
    ? availableCandidates 
    : CATALOG.filter(p => p.destination === destination && p.taxonomy !== 'hotel');

  const sourceEvent = recentPurchases[recentPurchases.length - 1] || allEvents[0];
  const daysAgo = sourceEvent ? Math.max(0, Math.floor((now - new Date(sourceEvent.timestamp).getTime()) / (24 * 3600 * 1000))) : 0;

  return {
    strategy: 'cross_vertical',
    nextVertical,
    destination,
    recommendations: recommendationsPool.slice(0, 5).map((p, idx) => {
      const becauseList: BecauseItem[] = [
        {
          productId: sourceEvent?.productId || 'nt-hotel-01',
          productName: sourceEvent?.productName || 'V-OTA Resort Nha Trang - Deluxe Ocean View',
          event: sourceEvent?.eventType || 'purchase',
          daysAgo: daysAgo,
          contribution: idx === 0 ? 0.72 : 0.48
        }
      ];

      // If user also viewed VinWonders
      if (allEvents.some(e => e.productId === 'nt-attraction-01' && e.productId !== p.id)) {
        becauseList.push({
          productId: 'nt-attraction-01',
          productName: 'Vé Vui Chơi VinWonders Nha Trang',
          event: 'product_view',
          daysAgo: 2,
          contribution: 0.28
        });
      }

      return {
        product: p,
        score: +(0.92 - idx * 0.04).toFixed(2),
        rank: idx + 1,
        because: becauseList
      };
    }),
    diagnostics: {
      eventsUsed: allEvents.length,
      coldStart: false,
      excludedVerticals: bookedTaxonomies,
      modelVersion: 'v3.2-cross-vertical-twotower',
      latencyMs: 22
    },
    generatedAt: new Date().toISOString()
  };
}

export function getSimilarProducts(productId: string): Product[] {
  const current = CATALOG.find(p => p.id === productId);
  if (!current) return [];

  return CATALOG.filter(p => 
    p.id !== productId && 
    (p.taxonomy === current.taxonomy || p.destination === current.destination)
  ).slice(0, 4);
}

export const PERSONA_CDP_USER_MAP: Record<string, string> = {
  P1: 'VP0000001',
  P2: 'VP0000002',
  P3: 'VP0000003',
  P4: 'VP0000004',
};

export interface FetchRecommendationsParams {
  k?: number;
  destination?: string;
  fallbackUser?: UserPersona | null;
  fallbackEvents?: UserEvent[];
  signal?: AbortSignal;
}

/**
 * Fetch recommendations from backend endpoint GET /api/v1/recommendations
 * Proxied via Next.js BFF (/api/v1/recommendations); cá nhân hoá theo phiên đăng nhập.
 * Gracefully falls back to local recommendation calculation if backend is unreachable.
 */
export async function fetchRecommendations(
  params: FetchRecommendationsParams = {}
): Promise<RecommendationResponse> {
  const {
    k = 4,
    destination,
    fallbackUser = null,
    fallbackEvents = [],
    signal,
  } = params;

  try {
    // Danh tính đi theo cookie phiên qua BFF; không gửi cdp_user_id (IDOR, auth §3.5).
    const searchParams = new URLSearchParams();
    if (k) {
      searchParams.set('k', String(k));
    }
    if (destination) {
      searchParams.set('destination', destination);
    }

    const queryString = searchParams.toString();
    const endpoint = `/api/v1/recommendations${queryString ? `?${queryString}` : ''}`;

    const response = await apiFetch(endpoint, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      cache: 'no-store',
      signal,
    });

    if (!response.ok) {
      throw new Error(`Recommendations API returned status ${response.status}`);
    }

    const data = await response.json();

    // Map backend items to frontend RecommendationResponse
    const rawItems: any[] = Array.isArray(data.recommendations) ? data.recommendations : [];

    const mappedRecs = rawItems.map((item: any, idx: number) => {
      const pid = item.productId || item.product?.id || `rec-${idx}`;
      const catalogMatch = CATALOG.find(p => p.id === pid);

      const product: Product = catalogMatch || {
        id: pid,
        name: item.name || item.product?.name || 'Sản phẩm đề xuất',
        taxonomy: (item.taxonomy || item.product?.taxonomy || 'hotel') as Taxonomy,
        destination: (item.destination || item.product?.destination || 'Nha Trang') as Destination,
        unitPrice: Number(item.unitPrice ?? item.product?.unitPrice ?? 0),
        currency: 'VND',
        imageUrl: item.imageUrl || item.product?.imageUrl || 'https://images.unsplash.com/photo-1566073771259-6a8506099945?q=80&w=800&auto=format&fit=crop',
        description: item.description || item.product?.description || '',
        attributes: item.attributes || item.product?.attributes || {},
        available: item.available ?? true,
      };

      const becauseList: BecauseItem[] = Array.isArray(item.because)
        ? item.because.map((b: any) => ({
            productId: b.productId,
            productName: b.productName || 'Sản phẩm quan tâm gần đây',
            event: b.event || 'product_view',
            daysAgo: typeof b.daysAgo === 'number' ? Math.round(b.daysAgo) : 1,
            contribution: typeof b.contribution === 'number' ? b.contribution : 0.5,
            imageUrl: b.imageUrl,
          }))
        : [];

      return {
        product,
        score: typeof item.score === 'number' ? item.score : +(0.9 - idx * 0.05).toFixed(2),
        rank: typeof item.rank === 'number' ? item.rank : idx + 1,
        because: becauseList,
      };
    });

    return {
      strategy: data.strategy || 'popular',
      nextVertical: data.nextVertical,
      destination: data.destination || (fallbackUser?.activeDestination || 'Nha Trang'),
      recommendations: mappedRecs,
      diagnostics: {
        eventsUsed: data.diagnostics?.eventsUsed ?? 0,
        coldStart: data.diagnostics?.coldStart ?? false,
        excludedVerticals: data.diagnostics?.excludedVerticals ?? [],
        modelVersion: data.modelVersion || 'v3.2-prod-hybrid',
        latencyMs: data.diagnostics?.latencyMs,
      },
      generatedAt: data.generatedAt || new Date().toISOString(),
    };
  } catch (error: any) {
    if (signal?.aborted) {
      throw error;
    }
    console.warn('[recsys] Backend API fetch failed, falling back to local simulator:', error?.message || error);
    return calculateRecommendations(fallbackUser, fallbackEvents);
  }
}

