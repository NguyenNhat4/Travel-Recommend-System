import { afterEach, describe, expect, it, vi } from 'vitest';
import { collectAssistantEvents, parseAssistantSse, requestAssistantStream } from '../../src/services/assistantStream';

function streamFrom(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
}

describe('assistant SSE parsing', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('handles split chunks, multiple events, and both LF and CRLF framing', async () => {
    const stream = streamFrom([
      'event: run.star',
      'ted\r\ndata: {"runId":"a"}\r\n\r\nevent: node.completed\ndata: {"nodeId":"search"}\n\n',
      'event: run.completed\ndata: {"response":{"status":"NO_RESULTS"}}\n\n',
    ]);

    await expect(collectAssistantEvents(stream)).resolves.toEqual([
      { event: 'run.started', data: { runId: 'a' } },
      { event: 'node.completed', data: { nodeId: 'search' } },
      { event: 'run.completed', data: { response: { status: 'NO_RESULTS' } } },
    ]);
  });

  it('rejects malformed JSON data', async () => {
    const stream = streamFrom(['event: run.started\ndata: {bad}\n\n']);
    await expect(collectAssistantEvents(stream)).rejects.toMatchObject({ code: 'INVALID_SSE_JSON' });
  });

  it('rejects a stream that ends without a terminal event', async () => {
    const stream = streamFrom(['event: run.started\ndata: {}\n\n']);
    await expect(collectAssistantEvents(stream)).rejects.toMatchObject({ code: 'MISSING_TERMINAL_EVENT' });
  });

  it('stops parsing when aborted', async () => {
    const controller = new AbortController();
    const stream = new ReadableStream<Uint8Array>({
      start(reader) {
        reader.enqueue(new TextEncoder().encode('event: run.started\ndata: {}\n\n'));
      },
      cancel: vi.fn(),
    });
    const events = parseAssistantSse(stream, controller.signal);
    const first = await events.next();
    expect(first.value).toEqual({ event: 'run.started', data: {} });
    controller.abort();
    await expect(events.next()).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('sends the typed request to the same-origin stream with required headers', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(streamFrom([
      'event: run.failed\ndata: {"error":{"code":"LLM_UNAVAILABLE","message":"Unavailable"}}\n\n',
    ]), { status: 200, headers: { 'content-type': 'text/event-stream' } }));
    vi.stubGlobal('fetch', fetchMock);
    const request = { message: 'Plan trip', conversationId: null, intentOverride: null, context: { language: 'vi' as const } };
    const signal = new AbortController().signal;
    const onEvent = vi.fn();

    await requestAssistantStream(request, { signal, onEvent });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(url).toBe('/api/v1/assistant/itineraries/stream');
    expect(headers.get('content-type')).toBe('application/json');
    expect(headers.get('accept')).toBe('text/event-stream');
    expect(headers.get('x-request-id')).toBeTruthy();
    // Trình duyệt không giữ token: BFF gắn Authorization từ cookie phiên (auth §4.2).
    expect(headers.get('authorization')).toBeNull();
    expect(init.credentials).toBe('same-origin');
    expect(JSON.parse(String(init.body))).toEqual(request);
    expect(onEvent).toHaveBeenCalledWith({ event: 'run.failed', data: { error: { code: 'LLM_UNAVAILABLE', message: 'Unavailable' } } });
  });
});
