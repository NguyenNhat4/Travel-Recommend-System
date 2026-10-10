/**
 * Gợi ý tức thì khi gõ — GET /api/v1/search/suggestions qua BFF (FR-SRC-05, docs/spec/hop-dong-tich-hop-frontend.md §4.2).
 *
 * Khớp chữ trên catalog, không ghi hành vi, nên được gọi theo từng lần gõ. Không đặt `cache: 'no-store'`: response
 * có `Cache-Control: public` và giống nhau cho mọi người, trình duyệt được giữ lại.
 */
import type { components } from '../types/api.gen';
import { apiFetch } from './http';

export type SearchSuggestion = components['schemas']['SearchSuggestion'];

/** Số gợi ý tối đa trong panel (FR-SRC-05). */
export const SUGGESTION_LIMIT = 8;

function isSuggestion(value: unknown): value is SearchSuggestion {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  if (typeof item.label !== 'string' || !item.label.trim()) return false;
  if (item.type === 'destination') return true;
  return item.type === 'product' && typeof item.productId === 'string' && item.productId.length > 0 && typeof item.taxonomy === 'string';
}

export async function fetchSuggestions(query: string, signal?: AbortSignal): Promise<SearchSuggestion[]> {
  const params = new URLSearchParams({ q: query, limit: String(SUGGESTION_LIMIT) });
  const response = await apiFetch(`/api/v1/search/suggestions?${params}`, { method: 'GET', signal });
  if (!response.ok) throw new Error(`Suggestion API returned status: ${response.status}`);

  const payload: unknown = await response.json();
  const suggestions = payload && typeof payload === 'object' ? (payload as Record<string, unknown>).suggestions : null;
  if (!Array.isArray(suggestions) || !suggestions.every(isSuggestion)) throw new Error('Danh sách gợi ý không hợp lệ.');
  return suggestions.slice(0, SUGGESTION_LIMIT);
}
