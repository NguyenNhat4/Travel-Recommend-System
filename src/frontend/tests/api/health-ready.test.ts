import { afterEach, describe, expect, it, vi } from 'vitest';
import { GET } from '../../src/app/health/ready/route';

describe('public readiness route', () => {
  afterEach(() => vi.restoreAllMocks());

  it('forwards the backend readiness status and payload', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: 'ok', ready: true }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    );

    const response = await GET();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: 'ok', ready: true });
    expect(fetch).toHaveBeenCalledWith('http://127.0.0.1:8000/health/ready', { cache: 'no-store' });
  });

  it('returns 503 when the backend cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connection refused')));

    const response = await GET();

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ status: 'unavailable', ready: false });
  });
});
