'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Tải dữ liệu cho một khối giao diện khi `enabled` (thường là "đã vào vùng nhìn").
 *
 * Chỉ dùng cho dữ liệu công khai, giống nhau giữa mọi người dùng (danh sách sản phẩm, điểm đến): bộ đệm nằm
 * trong bộ nhớ trang, gộp các request cùng `key` đang bay và giữ kết quả `ttlMs`. Dữ liệu theo người dùng
 * (gợi ý cá nhân hóa) không đi qua đây; đổi tài khoản thì gọi `clearSectionCache()` (frontend §7 điều 7).
 *
 * `fetcher` phải là hàm của `services/`; component không tự gọi `fetch`. Request không bị hủy khi unmount:
 * kết quả vẫn vào bộ đệm, nên quay lại trang trong `ttlMs` là có ngay.
 */
export interface LazySection<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  retry: () => void;
}

export interface LazySectionOptions {
  enabled?: boolean;
  ttlMs?: number;
  /** Quá hạn thì hủy request và báo lỗi. */
  timeoutMs?: number;
}

const DEFAULT_TTL_MS = 60_000;

const cache = new Map<string, { data: unknown; at: number }>();
const inflight = new Map<string, Promise<unknown>>();

export function clearSectionCache(): void {
  cache.clear();
  inflight.clear();
}

function readCache<T>(key: string, ttlMs: number): T | null {
  const hit = cache.get(key);
  if (!hit) return null;
  if (Date.now() - hit.at > ttlMs) {
    cache.delete(key);
    return null;
  }
  return hit.data as T;
}

function load<T>(key: string, fetcher: (signal: AbortSignal) => Promise<T>, timeoutMs?: number): Promise<T> {
  const existing = inflight.get(key);
  if (existing) return existing as Promise<T>;
  const controller = new AbortController();
  const timer = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : undefined;
  const request = fetcher(controller.signal)
    .then((data) => {
      cache.set(key, { data, at: Date.now() });
      return data;
    })
    .finally(() => {
      if (timer) clearTimeout(timer);
      if (inflight.get(key) === request) inflight.delete(key);
    });
  inflight.set(key, request);
  return request;
}

function toError(error: unknown): Error {
  return error instanceof Error ? error : new Error('Chưa tải được dữ liệu.');
}

export function useLazySection<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
  { enabled = true, ttlMs = DEFAULT_TTL_MS, timeoutMs }: LazySectionOptions = {},
): LazySection<T> {
  const fetcherRef = useRef(fetcher);
  // Khai báo trước effect tải để effect đó luôn thấy `fetcher` mới nhất.
  useEffect(() => { fetcherRef.current = fetcher; });
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: Error | null }>(
    () => ({ data: readCache<T>(key, ttlMs), loading: false, error: null }),
  );

  useEffect(() => {
    if (!enabled) return;
    const cached = readCache<T>(key, ttlMs);
    if (cached !== null) {
      setState({ data: cached, loading: false, error: null });
      return;
    }
    let active = true;
    setState({ data: null, loading: true, error: null });
    load<T>(key, (signal) => fetcherRef.current(signal), timeoutMs).then(
      (data) => { if (active) setState({ data, loading: false, error: null }); },
      (error) => { if (active) setState({ data: null, loading: false, error: toError(error) }); },
    );
    return () => { active = false; };
  }, [key, enabled, ttlMs, timeoutMs, attempt]);

  const retry = useCallback(() => {
    cache.delete(key);
    setAttempt((n) => n + 1);
  }, [key]);

  // Trước khi effect chạy lần đầu (enabled vừa bật) vẫn coi là đang tải, để không nháy trạng thái rỗng.
  const pending = enabled && state.data === null && state.error === null;
  return { data: state.data, loading: state.loading || pending, error: state.error, retry };
}
