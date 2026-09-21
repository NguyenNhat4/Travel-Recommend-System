/**
 * Semantic & Catalog Search Service
 * Translates natural language queries into relevance scores based on semantic intent
 * (e.g. "nghỉ dưỡng biển cho gia đình", "vé tham quan trẻ nhỏ", "5 sao hướng biển")
 */

import { CATALOG } from '../data/catalog';
import { Product, Destination, Taxonomy } from '../types/travel';

export interface SearchFilters {
  destination?: Destination[];
  taxonomy?: Taxonomy;
  minPrice?: number;
  maxPrice?: number;
  minStarRating?: number;
}

export type SortOption = 'relevance' | 'price_asc' | 'price_desc';

export interface SearchResultItem {
  product: Product;
  relevanceScore: number;
  matchTags: string[];
}

export interface SearchResponse {
  query: string;
  total: number;
  results: SearchResultItem[];
  isWeakMatch: boolean;
  categoryCounts: Record<string, number>;
}

export function searchProducts(
  query: string,
  filters: SearchFilters = {},
  sort: SortOption = 'relevance'
): SearchResponse {
  const cleanQ = query.toLowerCase().trim();
  const tokens = cleanQ.split(/\s+/).filter(Boolean);

  // Semantic keyword intents
  const familyIntent = tokens.some(t => ['gia', 'đình', 'trẻ', 'nhỏ', 'con', 'family', 'kid', 'kids'].includes(t));
  const beachIntent = tokens.some(t => ['biển', 'beach', 'bãi', 'ocean'].includes(t));
  const luxuryIntent = tokens.some(t => ['5', 'sao', 'luxury', 'sang', 'resort'].includes(t));
  const funIntent = tokens.some(t => ['vui', 'chơi', 'safari', 'cáp', 'treo', 'công', 'viên', 'theme', 'park', 'show'].includes(t));
  const flightIntent = tokens.some(t => ['bay', 'vé', 'máy', 'khứ', 'hồi', 'vietnam', 'vietjet', 'bamboo'].includes(t));
  const golfIntent = tokens.some(t => ['golf', 'hố', 'sân'].includes(t));

  // Destination intents in query
  let queryDest: Destination | null = null;
  if (cleanQ.includes('nha trang') || cleanQ.includes('cam ranh')) queryDest = 'Nha Trang';
  else if (cleanQ.includes('phú quốc') || cleanQ.includes('phu quoc')) queryDest = 'Phú Quốc';
  else if (cleanQ.includes('đà nẵng') || cleanQ.includes('da nang')) queryDest = 'Đà Nẵng';
  else if (cleanQ.includes('hội an') || cleanQ.includes('hoi an')) queryDest = 'Hội An';
  else if (cleanQ.includes('hà nội') || cleanQ.includes('ha noi')) queryDest = 'Hà Nội';
  else if (cleanQ.includes('hạ long') || cleanQ.includes('ha long')) queryDest = 'Hạ Long';

  // Score each product
  const scoredItems: SearchResultItem[] = CATALOG.map(product => {
    let score = 0.5; // base score
    const matchTags: string[] = [];

    // Destination match
    if (queryDest) {
      if (product.destination === queryDest) {
        score += 0.35;
        matchTags.push(product.destination);
      } else {
        score -= 0.3;
      }
    }

    // Direct name or description token matches
    tokens.forEach(token => {
      if (product.name.toLowerCase().includes(token)) score += 0.15;
      if (product.description.toLowerCase().includes(token)) score += 0.08;
    });

    // Semantic intent checks
    if (familyIntent && product.attributes.familyFriendly) {
      score += 0.25;
      matchTags.push('Phù hợp gia đình');
    }
    if (beachIntent && (product.attributes.beachfront || product.attributes.oceanView)) {
      score += 0.25;
      matchTags.push('Hướng biển');
    }
    if (luxuryIntent && product.attributes.starRating && product.attributes.starRating >= 5) {
      score += 0.25;
      matchTags.push('Đẳng cấp 5★');
    }
    if (funIntent && (product.attributes.themePark || product.attributes.safari || product.attributes.waterPark)) {
      score += 0.25;
      matchTags.push('Công viên giải trí');
    }
    if (flightIntent && product.taxonomy === 'flight') {
      score += 0.3;
      matchTags.push('Vé máy bay');
    }
    if (golfIntent && product.taxonomy === 'golf') {
      score += 0.35;
      matchTags.push('Sân Golf');
    }

    if (product.attributes.pool) matchTags.push('Hồ bơi');

    return {
      product,
      relevanceScore: Math.min(0.99, Math.max(0.1, score)),
      matchTags: Array.from(new Set(matchTags))
    };
  });

  // Calculate category counts across all matched products
  const categoryCounts: Record<string, number> = {
    all: 0,
    hotel: 0,
    flight: 0,
    attraction: 0,
    combo: 0,
    golf: 0
  };

  scoredItems.forEach(item => {
    categoryCounts.all++;
    categoryCounts[item.product.taxonomy] = (categoryCounts[item.product.taxonomy] || 0) + 1;
  });

  // Apply filters
  let filtered = scoredItems.filter(item => {
    const p = item.product;

    if (filters.destination && filters.destination.length > 0) {
      if (!filters.destination.includes(p.destination)) return false;
    }

    if (filters.taxonomy && p.taxonomy !== filters.taxonomy) {
      return false;
    }

    if (filters.minPrice !== undefined && p.unitPrice < filters.minPrice) {
      return false;
    }

    if (filters.maxPrice !== undefined && p.unitPrice > filters.maxPrice) {
      return false;
    }

    if (filters.minStarRating !== undefined && p.attributes.starRating) {
      if (p.attributes.starRating < filters.minStarRating) return false;
    }

    return true;
  });

  // Sort
  if (sort === 'relevance') {
    filtered.sort((a, b) => b.relevanceScore - a.relevanceScore);
  } else if (sort === 'price_asc') {
    filtered.sort((a, b) => a.product.unitPrice - b.product.unitPrice);
  } else if (sort === 'price_desc') {
    filtered.sort((a, b) => b.product.unitPrice - a.product.unitPrice);
  }

  const isWeakMatch = query.length > 3 && filtered.length > 0 && filtered[0].relevanceScore < 0.65;

  return {
    query,
    total: filtered.length,
    results: filtered,
    isWeakMatch,
    categoryCounts
  };
}
