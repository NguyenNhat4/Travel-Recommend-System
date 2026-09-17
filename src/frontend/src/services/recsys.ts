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
