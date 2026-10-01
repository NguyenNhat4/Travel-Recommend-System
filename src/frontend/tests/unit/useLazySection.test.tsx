// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clearSectionCache, useLazySection } from '../../src/hooks/useLazySection';

describe('useLazySection', () => {
  beforeEach(() => clearSectionCache());
  afterEach(() => cleanup());

  it('does not call the fetcher while disabled, then loads once enabled', async () => {
    const fetcher = vi.fn().mockResolvedValue(['a']);
    const { result, rerender } = renderHook(({ enabled }) => useLazySection('k1', fetcher, { enabled }), { initialProps: { enabled: false } });
    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);

    rerender({ enabled: true });
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.data).toEqual(['a']));
    expect(result.current.loading).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('shares one request between sections with the same key', async () => {
    let resolve!: (value: string[]) => void;
    const fetcher = vi.fn(() => new Promise<string[]>((r) => { resolve = r; }));
    const first = renderHook(() => useLazySection('same', fetcher));
    const second = renderHook(() => useLazySection('same', fetcher));
    expect(fetcher).toHaveBeenCalledTimes(1);

    await act(async () => { resolve(['x']); });
    await waitFor(() => expect(first.result.current.data).toEqual(['x']));
    await waitFor(() => expect(second.result.current.data).toEqual(['x']));
  });

  it('serves a remount from the cache inside the ttl', async () => {
    const fetcher = vi.fn().mockResolvedValue(['cached']);
    const first = renderHook(() => useLazySection('ttl', fetcher));
    await waitFor(() => expect(first.result.current.data).toEqual(['cached']));
    first.unmount();

    const second = renderHook(() => useLazySection('ttl', fetcher));
    expect(second.result.current.data).toEqual(['cached']);
    expect(second.result.current.loading).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('refetches after the ttl has passed', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(['old']).mockResolvedValueOnce(['new']);
    const first = renderHook(() => useLazySection('expire', fetcher, { ttlMs: 5 }));
    await waitFor(() => expect(first.result.current.data).toEqual(['old']));
    first.unmount();
    await new Promise((r) => setTimeout(r, 20));

    const second = renderHook(() => useLazySection('expire', fetcher, { ttlMs: 5 }));
    await waitFor(() => expect(second.result.current.data).toEqual(['new']));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('reports errors and retries on demand without caching the failure', async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce(['ok']);
    const { result } = renderHook(() => useLazySection('retry', fetcher));
    await waitFor(() => expect(result.current.error?.message).toBe('boom'));
    expect(result.current.data).toBeNull();

    act(() => result.current.retry());
    await waitFor(() => expect(result.current.data).toEqual(['ok']));
    expect(result.current.error).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('aborts and fails when the request exceeds timeoutMs', async () => {
    const fetcher = vi.fn((signal: AbortSignal) => new Promise<string[]>((_, reject) => {
      signal.addEventListener('abort', () => reject(new Error('timeout')));
    }));
    const { result } = renderHook(() => useLazySection('timeout', fetcher, { timeoutMs: 20 }));
    await waitFor(() => expect(result.current.error?.message).toBe('timeout'));
  });

  it('keeps the result in the cache when the section unmounts mid-request', async () => {
    let resolve!: (value: string[]) => void;
    const fetcher = vi.fn(() => new Promise<string[]>((r) => { resolve = r; }));
    const first = renderHook(() => useLazySection('leave', fetcher));
    first.unmount();
    await act(async () => { resolve(['late']); });

    const second = renderHook(() => useLazySection('leave', fetcher));
    expect(second.result.current.data).toEqual(['late']);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('starts fresh after clearSectionCache (account switch)', async () => {
    const fetcher = vi.fn().mockResolvedValue(['v']);
    const first = renderHook(() => useLazySection('acct', fetcher));
    await waitFor(() => expect(first.result.current.data).toEqual(['v']));
    first.unmount();
    clearSectionCache();

    const second = renderHook(() => useLazySection('acct', fetcher));
    await waitFor(() => expect(second.result.current.data).toEqual(['v']));
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
