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
});
