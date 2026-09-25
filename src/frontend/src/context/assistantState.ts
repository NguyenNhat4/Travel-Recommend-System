import type { components } from '../types/api.gen';
import type { AssistantRequest, AssistantResponse } from '../services/assistantStream';

export type AssistantPhase =
  | 'idle'
  | 'connecting'
  | 'streaming'
  | 'completed'
  | 'needs_clarification'
  | 'no_results'
  | 'fallback'
  | 'failed'
  | 'aborted';

export type AssistantRequestSnapshot = AssistantRequest;

export const CONVERSATION_RESTARTED_TEXT = 'Đã bắt đầu cuộc trò chuyện mới.';

export interface AssistantProgress {
  sequence?: number;
  nodeId?: string;
  outcome?: string;
  message?: string;
  durationMs?: number;
}

export interface AssistantError {
  code: string;
  message: string;
  retryable: boolean;
  details?: unknown;
  status?: number;
}

export interface AssistantTranscriptItem {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  response?: AssistantResponse;
  createdAt: number;
}

export interface AssistantState {
  isHydrated: boolean;
  phase: AssistantPhase;
  transcript: AssistantTranscriptItem[];
  response: AssistantResponse | null;
  topology: Record<string, unknown> | null;
  progress: AssistantProgress[];
  error: AssistantError | null;
  conversationId: string | null;
  lastRequest: AssistantRequestSnapshot | null;
  isSlow: boolean;
  isFloatingOpen: boolean;
  isHeaderDrawerOpen: boolean;
  floatingInitialMessage: string | null;
}

type Action =
  | { type: 'hydrate-conversation'; conversationId: string | null }
  | { type: 'request-started'; request: AssistantRequestSnapshot; userText: string; appendUser: boolean }
  | { type: 'stream-started' }
  | { type: 'topology-received'; topology: Record<string, unknown> }
  | { type: 'node-completed'; progress: AssistantProgress }
  | { type: 'response-received'; response: AssistantResponse }
  | { type: 'request-failed'; error: AssistantError }
  | { type: 'conversation-restarted' }
  | { type: 'request-aborted' }
  | { type: 'slow-state'; isSlow: boolean }
  | { type: 'reset' }
  | { type: 'open-floating'; initialMessage?: string }
  | { type: 'close-floating' }
  | { type: 'consume-floating-initial-message' }
  | { type: 'open-header-drawer' }
  | { type: 'close-header-drawer' };

export function createInitialAssistantState(conversationId: string | null = null): AssistantState {
  return {
    isHydrated: false,
    phase: 'idle',
    transcript: [],
    response: null,
    topology: null,
    progress: [],
    error: null,
    conversationId,
    lastRequest: null,
    isSlow: false,
    isFloatingOpen: false,
    isHeaderDrawerOpen: false,
    floatingInitialMessage: null,
  };
}

function responseText(response: AssistantResponse): string {
  switch (response.status) {
    case 'COMPLETED': return response.itinerary.title || 'Lịch trình đã được hoàn tất.';
    case 'NEEDS_CLARIFICATION': return response.question;
    case 'NO_RESULTS':
    case 'FALLBACK': return response.message;
  }
}

function responsePhase(response: AssistantResponse): AssistantPhase {
  switch (response.status) {
    case 'COMPLETED': return 'completed';
    case 'NEEDS_CLARIFICATION': return 'needs_clarification';
    case 'NO_RESULTS': return 'no_results';
    case 'FALLBACK': return 'fallback';
  }
}

export function assistantReducer(state: AssistantState, action: Action): AssistantState {
  switch (action.type) {
    case 'hydrate-conversation':
      return { ...state, isHydrated: true, conversationId: action.conversationId };
    case 'request-started': {
      const userMessage: AssistantTranscriptItem = {
        id: `user-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        sender: 'user',
        text: action.userText,
        createdAt: Date.now(),
      };
      return {
        ...state,
        phase: 'connecting',
        transcript: action.appendUser ? [...state.transcript, userMessage] : state.transcript,
        response: null,
        topology: null,
        progress: [],
        error: null,
        lastRequest: action.request,
        isSlow: false,
      };
    }
    case 'stream-started':
      return { ...state, phase: 'streaming' };
    case 'topology-received':
      return { ...state, phase: 'streaming', topology: action.topology };
    case 'node-completed':
      return { ...state, phase: 'streaming', progress: [...state.progress, action.progress] };
    case 'response-received':
      return {
        ...state,
        phase: responsePhase(action.response),
        response: action.response,
        conversationId: action.response.conversationId,
        transcript: [...state.transcript, {
          id: `assistant-${Date.now()}-${Math.random().toString(16).slice(2)}`,
          sender: 'assistant',
          text: responseText(action.response),
          response: action.response,
          createdAt: Date.now(),
        }],
        error: null,
        isSlow: false,
      };
    case 'request-failed': {
      const details = action.error.details as { conversationId?: unknown } | undefined;
      const conversationId = action.error.code === 'CONVERSATION_NOT_FOUND'
        ? null
        : action.error.code === 'UNSUPPORTED_DESTINATION' && typeof details?.conversationId === 'string'
          ? details.conversationId
          : state.conversationId;
      return { ...state, phase: 'failed', conversationId, error: action.error, isSlow: false };
    }
    case 'conversation-restarted':
      // Hợp đồng Frontend §8: hội thoại hết hạn thì bỏ conversationId và báo đã bắt đầu hội thoại mới.
      return {
        ...state,
        conversationId: null,
        transcript: [...state.transcript, {
          id: `assistant-${Date.now()}-${Math.random().toString(16).slice(2)}`,
          sender: 'assistant',
          text: CONVERSATION_RESTARTED_TEXT,
          createdAt: Date.now(),
        }],
      };
    case 'request-aborted':
      return { ...state, phase: 'aborted', error: null, isSlow: false };
    case 'slow-state':
      return { ...state, isSlow: action.isSlow };
    case 'reset':
      return {
        ...createInitialAssistantState(),
        isHydrated: state.isHydrated,
        isFloatingOpen: state.isFloatingOpen,
        isHeaderDrawerOpen: state.isHeaderDrawerOpen,
      };
    case 'open-floating':
      return { ...state, isFloatingOpen: true, floatingInitialMessage: action.initialMessage ?? null };
    case 'close-floating':
      return { ...state, isFloatingOpen: false };
    case 'consume-floating-initial-message':
      return { ...state, floatingInitialMessage: null };
    case 'open-header-drawer':
      return { ...state, isHeaderDrawerOpen: true };
    case 'close-header-drawer':
      return { ...state, isHeaderDrawerOpen: false };
  }
}

export type AssistantAction = Action;
