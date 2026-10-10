// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ fetchSuggestions: vi.fn() }));
vi.mock('../../src/services/suggest', () => ({ fetchSuggestions: api.fetchSuggestions, SUGGESTION_LIMIT: 8 }));

import {
  CACHE_MAX, CACHE_TTL_MS, DEBOUNCE_MS, clearSuggestionCache, suggestionKey, useInstantSearch,
} from '../../src/features/search/instant/useInstantSearch';

const HANOI = [{ type: 'destination', label: 'Hà Nội', productCount: 214 }];
const tick = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const hook = (query: string, enabled = true) =>
  renderHook((props: { query: string; enabled: boolean }) => useInstantSearch(props.query, props.enabled), { initialProps: { query, enabled } });

describe('suggestionKey', () => {
  it('needs two letters or digits; blanks and punctuation do not count', () => {
    for (const q of ['', ' ', '    ', 'h', ' h ', 'à', '--', '!?', 'h-']) expect(suggestionKey(q)).toBeNull();
    expect(suggestionKey('Ha')).toBe('ha');
    expect(suggestionKey('  HÀ   nội ')).toBe('ha noi');
    expect(suggestionKey('3n')).toBe('3n');
    expect(suggestionKey('Đà-Nẵng')).toBe('da nang');
  });
});

describe('useInstantSearch', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    clearSuggestionCache();
    api.fetchSuggestions.mockReset();
    api.fetchSuggestions.mockResolvedValue(HANOI);
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('does not call the API for one character, blanks or punctuation', async () => {
    const { result, rerender } = hook('');
    for (const query of ['h', ' ', '   ', '--', 'h ']) {
      rerender({ query, enabled: true });
      await tick(DEBOUNCE_MS * 3);
      expect(result.current).toEqual({ status: 'idle', suggestions: [] });
    }
    expect(api.fetchSuggestions).not.toHaveBeenCalled();
  });

  it('waits for the pause: fast typing costs one request', async () => {
    const { result, rerender } = hook('h');
    for (const query of ['ha', 'ha n', 'ha no', 'ha noi']) {
      rerender({ query, enabled: true });
      expect(result.current.status).toBe('loading');
      await tick(DEBOUNCE_MS - 50);
    }
    expect(api.fetchSuggestions).not.toHaveBeenCalled();
    await tick(DEBOUNCE_MS);
    expect(api.fetchSuggestions).toHaveBeenCalledTimes(1);
    expect(api.fetchSuggestions.mock.calls[0][0]).toBe('ha noi');
    expect(result.current).toEqual({ status: 'ready', suggestions: HANOI });
  });

  it('aborts the in-flight request when a new key arrives and ignores its late answer', async () => {
    const pending: Array<{ signal: AbortSignal; resolve: (value: unknown) => void }> = [];
    api.fetchSuggestions.mockImplementation((_q: string, signal: AbortSignal) => new Promise((resolve) => { pending.push({ signal, resolve }); }));
    const { result, rerender } = hook('vin');
    await tick(DEBOUNCE_MS);
    expect(pending).toHaveLength(1);
    expect(pending[0].signal.aborted).toBe(false);

    rerender({ query: 'vinp', enabled: true });
    expect(pending[0].signal.aborted).toBe(true);
    expect(result.current.status).toBe('loading');
    await tick(DEBOUNCE_MS);
    expect(pending).toHaveLength(2);

    await act(async () => { pending[0].resolve([{ type: 'destination', label: 'Cũ' }]); });
    expect(result.current.status).toBe('loading');
    await act(async () => { pending[1].resolve(HANOI); });
    expect(result.current).toEqual({ status: 'ready', suggestions: HANOI });
  });

  it('serves a repeated query from the cache, whatever its accents, case or spacing', async () => {
    const { result, rerender } = hook('Ha');
    await tick(DEBOUNCE_MS);
    expect(api.fetchSuggestions).toHaveBeenCalledTimes(1);

    rerender({ query: '', enabled: true });
    expect(result.current.status).toBe('idle');
    for (const query of ['Hà', ' HA ', 'hạ']) {
      rerender({ query, enabled: true });
      expect(result.current).toEqual({ status: 'ready', suggestions: HANOI });   // ngay lập tức, không qua loading
    }
    await tick(DEBOUNCE_MS * 2);
    expect(api.fetchSuggestions).toHaveBeenCalledTimes(1);

    await tick(CACHE_TTL_MS + 1);                                                // hết hạn: lần gõ lại sau đó gọi lại
    rerender({ query: '', enabled: true });
    rerender({ query: 'ha', enabled: true });
    await tick(DEBOUNCE_MS);
    expect(api.fetchSuggestions).toHaveBeenCalledTimes(2);
  });

  it('keeps at most CACHE_MAX keys', async () => {
    const { rerender } = hook('k0x');
    for (let i = 0; i <= CACHE_MAX; i++) {
      rerender({ query: `k${i}x`, enabled: true });
      await tick(DEBOUNCE_MS);
    }
    expect(api.fetchSuggestions).toHaveBeenCalledTimes(CACHE_MAX + 1);
    rerender({ query: 'k0x', enabled: true });                                    // khoá cũ nhất đã bị loại
    await tick(DEBOUNCE_MS);
    expect(api.fetchSuggestions).toHaveBeenCalledTimes(CACHE_MAX + 2);
    rerender({ query: `k${CACHE_MAX}x`, enabled: true });                         // khoá mới nhất còn
    await tick(DEBOUNCE_MS);
    expect(api.fetchSuggestions).toHaveBeenCalledTimes(CACHE_MAX + 2);
  });

  it('reports a failure and does nothing while disabled', async () => {
    api.fetchSuggestions.mockRejectedValue(new Error('500'));
    const { result, rerender } = hook('ha', false);
    await tick(DEBOUNCE_MS * 2);
    expect(api.fetchSuggestions).not.toHaveBeenCalled();
    expect(result.current.status).toBe('idle');

    rerender({ query: 'ha', enabled: true });
    await tick(DEBOUNCE_MS);
    expect(result.current).toEqual({ status: 'error', suggestions: [] });
  });
});
