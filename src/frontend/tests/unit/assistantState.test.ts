import { describe, expect, it } from 'vitest';
import {
  assistantReducer,
  createInitialAssistantState,
  type AssistantRequestSnapshot,
} from '../../src/context/assistantState';
import type { AssistantResponse } from '../../src/services/assistantStream';

const request: AssistantRequestSnapshot = {
  message: 'Plan trip',
  conversationId: 'old-conversation',
  intentOverride: null,
  context: { language: 'vi' },
};

describe('assistant reducer', () => {
  it('tracks connection, topology, progress, and completion lifecycle', () => {
    let state = createInitialAssistantState('restored-id');
    state = assistantReducer(state, { type: 'request-started', request, userText: 'Plan trip', appendUser: true });
    expect(state.phase).toBe('connecting');
    state = assistantReducer(state, { type: 'stream-started' });
    state = assistantReducer(state, { type: 'topology-received', topology: { nodes: ['search'] } });
    state = assistantReducer(state, {
      type: 'node-completed',
      progress: { sequence: 1, nodeId: 'search', outcome: 'completed', message: 'Found options' },
    });
    state = assistantReducer(state, {
      type: 'response-received',
      response: { status: 'NEEDS_CLARIFICATION', conversationId: 'backend-id', question: 'Which destination?' },
    });

    expect(state.phase).toBe('needs_clarification');
    expect(state.conversationId).toBe('backend-id');
    expect(state.progress).toHaveLength(1);
    expect(state.transcript.map((message) => message.sender)).toEqual(['user', 'assistant']);
  });

  it('a tapped hotel option swaps the latest plan without adding a message or touching its text', () => {
    let state = createInitialAssistantState();
    state = assistantReducer(state, { type: 'request-started', request, userText: 'Plan trip', appendUser: true });
    const first = { status: 'COMPLETED', conversationId: 'c1', message: '**Lịch**\nNơi nghỉ: Sunny', warnings: [],
      itinerary: { title: 'Lịch', days: [], estimatedTotal: 1, currency: 'VND', budgetStatus: 'NO_BUDGET' } } as unknown as AssistantResponse;
    state = assistantReducer(state, { type: 'response-received', response: first });
    const swapped = { ...first, message: undefined, itinerary: { ...(first as any).itinerary, estimatedTotal: 2 } } as unknown as AssistantResponse;
    state = assistantReducer(state, { type: 'stay-option-applied', response: swapped });
    expect(state.transcript.map((message) => message.sender)).toEqual(['user', 'assistant']);
    expect(state.transcript[1].text).toBe('**Lịch**\nNơi nghỉ: Sunny');
    expect(state.transcript[1].response).toBe(swapped);
    expect(state.response).toBe(swapped);
    expect(state.phase).toBe('completed');
  });

  it('clears expired conversation but preserves the exact request for explicit retry', () => {
    let state = createInitialAssistantState('expired-id');
    state = assistantReducer(state, { type: 'request-started', request, userText: 'Plan trip', appendUser: true });
    state = assistantReducer(state, {
      type: 'request-failed',
      error: { code: 'CONVERSATION_NOT_FOUND', message: 'Conversation expired', retryable: false },
    });

    expect(state.conversationId).toBeNull();
    expect(state.lastRequest).toEqual(request);
    expect(state.phase).toBe('failed');
  });

  it('shows an out-of-scope refusal as an assistant message, not as an error', () => {
    let state = createInitialAssistantState('conversation');
    state = assistantReducer(state, { type: 'request-started', request, userText: 'xin 50k', appendUser: true });
    state = assistantReducer(state, { type: 'request-refused', text: '**Ngoài phạm vi hỗ trợ**\nBạn muốn đi đâu?' });

    expect(state.error).toBeNull();
    expect(state.phase).toBe('idle');
    expect(state.conversationId).toBe('conversation');
    expect(state.transcript.map((message) => message.sender)).toEqual(['user', 'assistant']);
    expect(state.transcript[1].text).toContain('Ngoài phạm vi hỗ trợ');
  });

  it('reset clears runtime state and conversation', () => {
    let state = createInitialAssistantState('conversation');
    state = assistantReducer(state, { type: 'request-started', request, userText: 'Plan trip', appendUser: true });
    state = assistantReducer(state, { type: 'reset' });

    expect(state).toMatchObject({ phase: 'idle', conversationId: null, transcript: [], response: null, lastRequest: null });
  });

  it.each([
    ['COMPLETED', 'completed'],
    ['NO_RESULTS', 'no_results'],
    ['FALLBACK', 'fallback'],
  ] as const)('maps %s business response to the %s phase', (status, phase) => {
    const response = {
      status,
      conversationId: 'backend-id',
      ...(status === 'COMPLETED' ? { itinerary: { days: [], estimatedTotal: null, currency: 'VND', budgetStatus: 'UNKNOWN' }, warnings: [] } : {}),
      ...(status === 'NO_RESULTS' ? { message: 'No matches' } : {}),
      ...(status === 'FALLBACK' ? { message: 'Search results', searchResults: {} } : {}),
    } as AssistantResponse;
    const state = assistantReducer(createInitialAssistantState(), { type: 'response-received', response });
    expect(state.phase).toBe(phase);
    expect(state.conversationId).toBe('backend-id');
    expect(state.response?.status).toBe(status);
  });
  it.each([
    [{ message: '**Một ngày ở Hà Nội**\nMình ghi nhận đổi ngày đi thành 15/10/2026.', itinerary: { title: 'Tiêu đề lịch' } }, '**Một ngày ở Hà Nội**\nMình ghi nhận đổi ngày đi thành 15/10/2026.'],
    [{ itinerary: { title: 'Tiêu đề lịch' } }, 'Tiêu đề lịch'],
    [{ itinerary: {} }, 'Lịch trình đã được hoàn tất.'],
  ])('shows the narration of a COMPLETED itinerary in the chat, then its title, then the fixed sentence (%#)', (extra, expected) => {
    const response = {
      status: 'COMPLETED', conversationId: 'backend-id', warnings: [],
      ...extra,
      itinerary: { days: [], estimatedTotal: null, currency: 'VND', budgetStatus: 'UNKNOWN', ...extra.itinerary },
    } as unknown as AssistantResponse;
    const state = assistantReducer(createInitialAssistantState(), { type: 'response-received', response });
    expect(state.transcript.at(-1)?.text).toBe(expected);
  });
});
