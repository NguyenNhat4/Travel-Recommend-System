import type { components } from '../types/api.gen';
import { apiFetch } from './http';

export type AssistantRequest = {
  message: string | null;
  conversationId: string | null;
  intentOverride: components['schemas']['TripIntentPatch'] | null;
  /** Chọn một phương án của hàng thẻ "Phương án khác" (contract 1.20.0, AC-AGT-04); cần conversationId. */
  selectStayOption?: { index: number } | null;
  context?: { language?: 'vi' | 'en' | null };
};
export type AssistantResponse = components['schemas']['ItineraryResponse'];

export interface AssistantStreamEvent {
  event: 'run.started' | 'graph.topology' | 'node.completed' | 'node.activity' | 'run.preview' | 'run.completed' | 'run.failed' | string;
  data: Record<string, unknown>;
}

export class AssistantStreamError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly retryable = false,
    readonly details?: unknown,
    readonly status?: number,
  ) {
    super(message);
    this.name = 'AssistantStreamError';
  }
}

function abortError() {
  return new DOMException('The operation was aborted', 'AbortError');
}

async function readWithAbort(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  signal?: AbortSignal,
) {
  if (!signal) return reader.read();
  if (signal.aborted) throw abortError();

  let onAbort: (() => void) | undefined;
  try {
    return await Promise.race([
      reader.read(),
      new Promise<never>((_, reject) => {
        onAbort = () => {
          void reader.cancel().catch(() => undefined);
          reject(abortError());
        };
        signal.addEventListener('abort', onAbort, { once: true });
      }),
    ]);
  } finally {
    if (onAbort) signal.removeEventListener('abort', onAbort);
  }
}

function parseFrame(frame: string): AssistantStreamEvent | null {
  let event = '';
  const data: string[] = [];
  for (const line of frame.split('\n')) {
    if (!line || line.startsWith(':')) continue;
    const separator = line.indexOf(':');
    const field = separator < 0 ? line : line.slice(0, separator);
    const value = separator < 0 ? '' : line.slice(separator + 1).replace(/^ /, '');
    if (field === 'event') event = value;
    if (field === 'data') data.push(value);
  }
  if (!event && data.length === 0) return null;
  if (!event) throw new AssistantStreamError('SSE event name is missing', 'INVALID_SSE_EVENT');

  try {
    const payload: unknown = JSON.parse(data.join('\n'));
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      throw new Error('Event data must be a JSON object');
    }
    return { event, data: payload as Record<string, unknown> };
  } catch (error) {
    throw new AssistantStreamError(
      error instanceof Error ? error.message : 'Invalid SSE JSON payload',
      'INVALID_SSE_JSON',
    );
  }
}

export async function* parseAssistantSse(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<AssistantStreamEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await readWithAbort(reader, signal);
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
      let boundary = buffer.search(/\n\n/);
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const parsed = parseFrame(frame);
        if (parsed) yield parsed;
        boundary = buffer.search(/\n\n/);
      }
    }

    buffer += decoder.decode().replace(/\r\n/g, '\n');
    if (buffer.trim()) {
      const parsed = parseFrame(buffer);
      if (parsed) yield parsed;
    }
  } finally {
    reader.releaseLock();
  }
}

export async function collectAssistantEvents(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): Promise<AssistantStreamEvent[]> {
  const events: AssistantStreamEvent[] = [];
  let terminal = false;
  for await (const event of parseAssistantSse(stream, signal)) {
    events.push(event);
    if (event.event === 'run.completed' || event.event === 'run.failed') terminal = true;
  }
  if (signal?.aborted) throw abortError();
  if (!terminal) throw new AssistantStreamError(
    'Kết nối với trợ lý bị gián đoạn giữa chừng. Bấm "Thử lại" để gửi lại yêu cầu; nếu vẫn lỗi, tải lại trang.',
    'MISSING_TERMINAL_EVENT',
    true,
  );
  return events;
}

function requestId() {
  return globalThis.crypto?.randomUUID?.() ?? `assistant-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function errorFromResponse(response: Response): Promise<AssistantStreamError> {
  let payload: Record<string, unknown> | null = null;
  try {
    payload = await response.json() as Record<string, unknown>;
  } catch {
    // Keep a useful transport error if the backend did not return its JSON envelope.
  }
  const envelope = payload?.error && typeof payload.error === 'object'
    ? payload.error as Record<string, unknown>
    : payload;
  return new AssistantStreamError(
    typeof envelope?.message === 'string' ? envelope.message : `Assistant request failed (${response.status})`,
    typeof envelope?.code === 'string' ? envelope.code : 'HTTP_ERROR',
    envelope?.retryable === true || response.status >= 500,
    envelope?.details,
    response.status,
  );
}

export async function requestAssistantStream(
  request: AssistantRequest,
  options: {
    signal: AbortSignal;
    onEvent: (event: AssistantStreamEvent) => void;
  },
): Promise<void> {
  const headers = new Headers({
    Accept: 'text/event-stream',
    'Content-Type': 'application/json',
    'X-Request-ID': requestId(),
  });
  // Danh tính do BFF gắn từ cookie phiên; client không bao giờ tự đặt Authorization.
  const response = await apiFetch('/api/v1/assistant/itineraries/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
    signal: options.signal,
    cache: 'no-store',
  });
  if (!response.ok) throw await errorFromResponse(response);
  if (!response.body) throw new AssistantStreamError('Assistant response did not include a stream', 'EMPTY_STREAM', true, undefined, response.status);

  let terminal = false;
  for await (const event of parseAssistantSse(response.body, options.signal)) {
    options.onEvent(event);
    if (event.event === 'run.completed' || event.event === 'run.failed') terminal = true;
  }
  if (options.signal.aborted) throw abortError();
  if (!terminal) throw new AssistantStreamError(
    'Kết nối với trợ lý bị gián đoạn giữa chừng. Bấm "Thử lại" để gửi lại yêu cầu; nếu vẫn lỗi, tải lại trang.',
    'MISSING_TERMINAL_EVENT',
    true,
  );
}
