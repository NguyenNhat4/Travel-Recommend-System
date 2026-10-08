'use client';

import { useEffect, useState } from 'react';
import { fetchSuggestions, type SearchSuggestion } from '../../../services/suggest';
import { fold } from '../../catalog/landing/searchHref';

/**
 * Gợi ý tức thì khi gõ (FR-SRC-05). Mọi luật giữ số lượt gọi thấp nằm ở đây:
 * - chỉ gọi khi có ít nhất `MIN_QUERY_CHARS` ký tự chữ hoặc số (rỗng, khoảng trắng, dấu câu thì không gọi);
 * - chờ `DEBOUNCE_MS` không có phím mới rồi mới gọi;
 * - phím mới huỷ lượt gọi đang bay (`AbortController`), response về trễ bị bỏ;
 * - kết quả giữ trong bộ nhớ trang theo khoá đã bỏ dấu ("Ha", "hà ", "HA" là một), tối đa `CACHE_MAX` khoá trong
 *   `CACHE_TTL_MS`. Dữ liệu công khai, giống nhau cho mọi người nên không cần xoá khi đổi tài khoản.
 */
export const MIN_QUERY_CHARS = 2;
export const DEBOUNCE_MS = 200;
export const CACHE_MAX = 50;
export const CACHE_TTL_MS = 5 * 60_000;

export type InstantStatus = 'idle' | 'loading' | 'ready' | 'error';

export interface InstantSearch {
  status: InstantStatus;
  suggestions: SearchSuggestion[];
}

const cache = new Map<string, { suggestions: SearchSuggestion[]; at: number }>();

export function clearSuggestionCache(): void {
  cache.clear();
}

/** Khoá của một truy vấn: bỏ dấu, chữ thường, gộp ký tự ngoài chữ/số; null khi chưa đủ ký tự để gợi ý. */
export function suggestionKey(query: string): string | null {
  const key = fold(query).replace(/[^a-z0-9]+/g, ' ').trim();
  return key.replace(/ /g, '').length >= MIN_QUERY_CHARS ? key : null;
}

function readCache(key: string): SearchSuggestion[] | null {
  const hit = cache.get(key);
  return hit && Date.now() - hit.at <= CACHE_TTL_MS ? hit.suggestions : null;
}

function writeCache(key: string, suggestions: SearchSuggestion[]): void {
  cache.delete(key);
  cache.set(key, { suggestions, at: Date.now() });
  while (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value as string);
}

const IDLE: InstantSearch = { status: 'idle', suggestions: [] };
const LOADING: InstantSearch = { status: 'loading', suggestions: [] };
const FAILED: InstantSearch = { status: 'error', suggestions: [] };

/** `enabled` false (panel đang đóng) thì không gọi gì. */
export function useInstantSearch(query: string, enabled = true): InstantSearch {
  const key = enabled ? suggestionKey(query) : null;
  // Kết quả của lượt gọi gần nhất; trạng thái của khoá hiện tại được suy ra lúc render để không lóe gợi ý của khoá cũ.
  const [settled, setSettled] = useState<{ key: string; suggestions: SearchSuggestion[] | null } | null>(null);

  useEffect(() => {
    if (!key || readCache(key)) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetchSuggestions(key, controller.signal)
        .then((suggestions) => {
          writeCache(key, suggestions);
          if (!controller.signal.aborted) setSettled({ key, suggestions });
        })
        .catch(() => {
          if (!controller.signal.aborted) setSettled({ key, suggestions: null });
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [key]);

  if (!key) return IDLE;
  const cached = readCache(key);
  if (cached) return { status: 'ready', suggestions: cached };
  if (settled?.key !== key) return LOADING;
  return settled.suggestions ? { status: 'ready', suggestions: settled.suggestions } : FAILED;
}
