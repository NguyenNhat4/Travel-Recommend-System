import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from '../../../shared/mocks/search/suggestSearch.200-default.json';
import { fetchSuggestions } from '../../src/services/suggest';

describe('suggest service', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  const respond = (body: unknown, status = 200) => {
    global.fetch = vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body });
  };

  it('calls the suggestion route with the query and limit, cancellable and browser-cacheable', async () => {
    respond(fixture);
    const controller = new AbortController();
    const suggestions = await fetchSuggestions('hà nội', controller.signal);
    expect(suggestions).toEqual(fixture.suggestions);

    const [url, init] = vi.mocked(global.fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/search/suggestions?q=h%C3%A0+n%E1%BB%99i&limit=8');
    expect(init.method).toBe('GET');
    expect(init.signal).toBe(controller.signal);
    expect(init.cache).toBeUndefined();   // không ép no-store: response có Cache-Control public
  });

  it('rejects a malformed payload instead of rendering half-known rows', async () => {
    for (const body of [null, {}, { suggestions: 'x' }, { suggestions: [{ type: 'product', label: 'Thiếu id' }] },
      { suggestions: [{ type: 'destination', label: '  ' }] }, { suggestions: [{ type: 'khac', label: 'A' }] }]) {
      respond(body);
      await expect(fetchSuggestions('ha')).rejects.toThrow('Danh sách gợi ý không hợp lệ');
    }
  });

  it('throws on an error status', async () => {
    respond({ error: { code: 'VALIDATION_ERROR' } }, 422);
    await expect(fetchSuggestions('ha')).rejects.toThrow('422');
  });
});
