import { afterEach, describe, expect, it, vi } from 'vitest';
import { POST } from '../../src/app/api/[...path]/route';
import { createAnonymousSession } from '../../src/services/server/bffSession';
import { MemorySessionStore, setSessionStoreForTests } from '../../src/services/server/sessionStore';

describe('Next BFF streaming proxy', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.BACKEND_BASE_URL;
    setSessionStoreForTests(undefined);
  });

  it('forwards status and headers and returns upstream chunks without buffering', async () => {
    process.env.BACKEND_BASE_URL = 'http://127.0.0.1:8000';
    let upstreamController: ReadableStreamDefaultController<Uint8Array> | undefined;
    let upstreamSignal: AbortSignal | undefined;
    const fetchMock = vi.fn(async (_url: URL, init: RequestInit) => {
      upstreamSignal = init.signal as AbortSignal;
      const body = new ReadableStream<Uint8Array>({ start(controller) { upstreamController = controller; } });
      return new Response(body, {
        status: 200,
        headers: { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const store = new MemorySessionStore();
    setSessionStoreForTests(store);
    const ua = { 'user-agent': 'vitest' };
    const { sid, record } = await createAnonymousSession(new Request('http://localhost:3000/', { headers: ua }), store);

    const abortController = new AbortController();
    const request = new Request('http://localhost:3000/api/v1/assistant/itineraries/stream', {
      method: 'POST',
      headers: {
        'content-type': 'application/json', accept: 'text/event-stream', ...ua,
        origin: 'http://localhost:3000', cookie: `vota_sid=${sid}; vota_csrf=${record.csrfToken}`,
        'x-csrf-token': record.csrfToken,
      },
      body: JSON.stringify({ message: 'stream this' }),
      signal: abortController.signal,
    });
    const requestSignal = request.signal;
    const response = await POST(request, { params: Promise.resolve({ path: ['v1', 'assistant', 'itineraries', 'stream'] }) });

    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toBe('text/event-stream');
    expect(fetchMock).toHaveBeenCalledWith(
      new URL('http://127.0.0.1:8000/api/v1/assistant/itineraries/stream'),
      expect.objectContaining({ method: 'POST', signal: requestSignal }),
    );

    const reader = response.body!.getReader();
    const chunk = new TextEncoder().encode('event: run.started\ndata: {}\n\n');
    upstreamController!.enqueue(chunk);
    await expect(reader.read()).resolves.toMatchObject({ value: chunk, done: false });

    abortController.abort();
    expect(upstreamSignal?.aborted).toBe(true);
    await reader.cancel();
  });
});
