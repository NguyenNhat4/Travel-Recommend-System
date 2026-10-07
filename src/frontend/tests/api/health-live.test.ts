import { afterEach, describe, expect, it, vi } from 'vitest';
import { GET } from '../../src/app/health/live/route';

describe('public liveness route', () => {
  afterEach(() => vi.restoreAllMocks());

  it('is live when the backend answers /health, whatever its readiness says', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ok' }), { status: 200 })),
    );

    const response = await GET();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: 'ok', live: true });
    expect(fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/health',
      expect.objectContaining({ cache: 'no-store', signal: expect.any(AbortSignal) }),
    );
  });

  it('never asks the backend for readiness, so RecSys or database outages do not trigger autohealing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })));

    await GET();

    const url = String(vi.mocked(fetch).mock.calls[0][0]);
    expect(url).not.toContain('/health/ready');
  });

  it('returns 503 when the backend is unreachable or hangs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('timeout')));

    const response = await GET();

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ status: 'unavailable', live: false });
  });

  it('returns 503 when the backend answers with an error status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('boom', { status: 500 })));

    expect((await GET()).status).toBe(503);
  });
});
