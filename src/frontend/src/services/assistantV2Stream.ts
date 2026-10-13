import type { components } from '../types/assistant-v2.gen';
import { ApiError, apiFetch, apiJson, toApiError } from './http';
import { AssistantStreamError, parseAssistantSse } from './assistantStream';

export type AssistantV2Request = components['schemas']['AssistantV2Request'];
export type AssistantV2Final = components['schemas']['AssistantV2Final'];
export type AssistantV2Event = components['schemas']['AssistantV2Event'];

export function newAssistantV2TurnId(): string {
  return crypto.randomUUID().replaceAll('-', '');
}

export async function requestAssistantV2(request: AssistantV2Request, signal?: AbortSignal): Promise<AssistantV2Final> {
  return apiJson<AssistantV2Final>('/api/v2/assistant/itineraries', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request), cache: 'no-store', signal,
  });
}

function isV2Event(value: unknown): value is AssistantV2Event {
  if (!value || typeof value !== 'object') return false;
  const event = value as Record<string, unknown>;
  return typeof event.event === 'string' && typeof event.runId === 'string'
    && typeof event.sequence === 'number' && Number.isInteger(event.sequence)
    && event.sequence > 0 && event.data !== null && typeof event.data === 'object';
}

export async function requestAssistantV2Stream(
  request: AssistantV2Request,
  options: { signal: AbortSignal; onEvent: (event: AssistantV2Event) => void },
): Promise<AssistantV2Final> {
  const response = await apiFetch('/api/v2/assistant/itineraries/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(request), cache: 'no-store', signal: options.signal,
  });
  if (!response.ok) throw await toApiError(response);
  if (!response.body) throw new AssistantStreamError('Luồng trợ lý trống.', 'EMPTY_STREAM', true);

  let runId: string | null = null;
  let lastSequence = 0;
  let terminal: AssistantV2Final | null = null;
  for await (const frame of parseAssistantSse(response.body, options.signal)) {
    if (!isV2Event(frame.data) || frame.event !== frame.data.event) {
      throw new AssistantStreamError('Sự kiện trợ lý không hợp lệ.', 'INVALID_SSE_EVENT');
    }
    const event = frame.data;
    if (runId === null) {
      if (event.event !== 'start') throw new AssistantStreamError('Thiếu sự kiện bắt đầu.', 'INVALID_SSE_EVENT');
      runId = event.runId;
    }
    if (event.runId !== runId || event.sequence <= lastSequence) continue;
    if (terminal) continue;
    lastSequence = event.sequence;
    options.onEvent(event);
    if (event.event === 'error') {
      const error = event.data.error;
      throw new ApiError(error.message, error.code, response.status, error.retryable, error.requestId);
    }
    if (event.event === 'final') terminal = event.data;
  }
  if (options.signal.aborted) throw new DOMException('The operation was aborted', 'AbortError');
  if (!terminal) throw new AssistantStreamError('Kết nối bị gián đoạn. Thử lại với cùng mã lượt gửi.', 'MISSING_TERMINAL_EVENT', true);
  return terminal;
}
