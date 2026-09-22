import { afterEach, describe, expect, it, vi } from 'vitest';
import { POST } from '../../src/app/api/[...path]/route';

describe('Next BFF streaming proxy', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.BACKEND_BASE_URL;
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

    const abortController = new AbortController();
    const request = new Request('http://localhost:3000/api/v1/assistant/itineraries/stream', {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
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
