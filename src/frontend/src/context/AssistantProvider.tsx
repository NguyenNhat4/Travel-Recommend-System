'use client';

import React, { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react';
import type { ReactNode } from 'react';
import type { components } from '../types/api.gen';
import { useTravel } from './TravelContext';
import {
  assistantReducer,
  createInitialAssistantState,
  type AssistantError,
  type AssistantState,
} from './assistantState';
import {
  AssistantStreamError,
  requestAssistantStream,
  type AssistantRequest,
  type AssistantResponse,
  type AssistantStreamEvent,
} from '../services/assistantStream';

const CONVERSATION_STORAGE_KEY = 'vota.assistant.conversationId';
type IntentOverride = components['schemas']['TripIntentPatch'];
type AssistantContextData = NonNullable<AssistantRequest['context']>;

interface AssistantContextValue {
  state: AssistantState;
  sendMessage: (message: string, context?: AssistantContextData) => void;
  submitIntentOverride: (intentOverride: IntentOverride, context?: AssistantContextData) => void;
  retry: () => void;
  abort: () => void;
  resetConversation: () => void;
  openFloatingWidget: (initialMessage?: string) => void;
  openHeaderDrawer: () => void;
  closeFloatingWidget: () => void;
  closeHeaderDrawer: () => void;
  consumeFloatingInitialMessage: () => void;
}

const AssistantContext = createContext<AssistantContextValue | null>(null);

function id() {
  return globalThis.crypto?.randomUUID?.() ?? `run-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function assistantError(error: unknown): AssistantError {
  if (error instanceof AssistantStreamError) {
    return {
      code: error.code,
      message: error.message,
      retryable: error.retryable,
      details: error.details,
      status: error.status,
    };
  }
  return {
    code: 'NETWORK_ERROR',
    message: error instanceof Error ? error.message : 'Không thể kết nối với trợ lý lúc này.',
    retryable: true,
  };
}

function backendEventError(data: Record<string, unknown>): AssistantError {
  const outer = data.error && typeof data.error === 'object'
    ? data.error as Record<string, unknown>
    : data;
  const payload = outer.error && typeof outer.error === 'object'
    ? outer.error as Record<string, unknown>
    : outer;
  return {
    code: typeof payload.code === 'string' ? payload.code : 'ASSISTANT_FAILED',
    message: typeof payload.message === 'string' ? payload.message : 'Trợ lý không thể xử lý yêu cầu này.',
    retryable: payload.retryable === true,
    details: payload.details,
    status: typeof data.httpStatus === 'number' ? data.httpStatus : undefined,
  };
}

function isAssistantResponse(value: unknown): value is AssistantResponse {
  if (!value || typeof value !== 'object') return false;
  const response = value as Record<string, unknown>;
  return ['COMPLETED', 'NEEDS_CLARIFICATION', 'NO_RESULTS', 'FALLBACK'].includes(String(response.status))
    && typeof response.conversationId === 'string';
}

function nodeProgress(data: Record<string, unknown>) {
  return {
    sequence: typeof data.sequence === 'number' ? data.sequence : undefined,
    nodeId: typeof data.nodeId === 'string' ? data.nodeId : undefined,
    outcome: typeof data.outcome === 'string' ? data.outcome : undefined,
    message: typeof data.message === 'string' ? data.message : undefined,
    durationMs: typeof data.durationMs === 'number' ? data.durationMs : undefined,
  };
}

function intentDescription(intent: IntentOverride) {
  const fields = [intent.destination, intent.days ? `${intent.days} ngày` : null].filter(Boolean);
  return fields.length ? `Cập nhật yêu cầu: ${fields.join(' · ')}` : 'Cập nhật yêu cầu chuyến đi';
}

export function AssistantProvider({ children }: { children: ReactNode }) {
  const { currentLocale, currentPersona } = useTravel();
  const [state, dispatch] = useReducer(assistantReducer, null, () => createInitialAssistantState());
  const activeRunIdRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const hydrationCompleteRef = useRef(false);
  const previousPersonaRef = useRef<string | null | undefined>(undefined);

  const abortCurrentRun = useCallback(() => {
    const controller = abortControllerRef.current;
    if (controller && !controller.signal.aborted) controller.abort();
    abortControllerRef.current = null;
    activeRunIdRef.current = null;
  }, []);

  useEffect(() => {
    let conversationId: string | null = null;
    try {
      conversationId = window.sessionStorage.getItem(CONVERSATION_STORAGE_KEY);
    } catch {
      // Storage can be unavailable in privacy-restricted contexts; runtime remains usable.
    }
    dispatch({ type: 'hydrate-conversation', conversationId });
    hydrationCompleteRef.current = true;
  }, []);

  useEffect(() => {
    if (!hydrationCompleteRef.current) return;
    try {
      if (state.conversationId) window.sessionStorage.setItem(CONVERSATION_STORAGE_KEY, state.conversationId);
      else window.sessionStorage.removeItem(CONVERSATION_STORAGE_KEY);
    } catch {
      // The backend session remains usable for this tab even if browser storage is disabled.
    }
  }, [state.conversationId]);

  useEffect(() => {
    const personaId = currentPersona?.code ?? null;
    if (previousPersonaRef.current === undefined) {
      previousPersonaRef.current = personaId;
      return;
    }
    if (previousPersonaRef.current !== personaId) {
      abortCurrentRun();
      dispatch({ type: 'reset' });
      previousPersonaRef.current = personaId;
    }
  }, [currentPersona?.code, abortCurrentRun]);

  useEffect(() => () => abortCurrentRun(), [abortCurrentRun]);

  const executeRequest = useCallback((
    request: AssistantRequest,
    userText: string,
    appendUser: boolean,
  ) => {
    abortCurrentRun();
    const runId = id();
    const controller = new AbortController();
    activeRunIdRef.current = runId;
    abortControllerRef.current = controller;
    dispatch({ type: 'request-started', request, userText, appendUser });

    const isCurrent = () => activeRunIdRef.current === runId && !controller.signal.aborted;
    const slowTimer = window.setTimeout(() => {
      if (isCurrent()) dispatch({ type: 'slow-state', isSlow: true });
    }, 8_000);

    void requestAssistantStream(request, {
      signal: controller.signal,
      onEvent: (event: AssistantStreamEvent) => {
        if (!isCurrent()) return;
        if (event.event === 'run.started') {
          dispatch({ type: 'stream-started' });
        } else if (event.event === 'graph.topology') {
          dispatch({ type: 'topology-received', topology: event.data });
        } else if (event.event === 'node.completed') {
          dispatch({ type: 'node-completed', progress: nodeProgress(event.data) });
        } else if (event.event === 'run.completed') {
          const response = event.data.response;
          if (!isAssistantResponse(response)) {
            throw new AssistantStreamError('Backend returned an invalid assistant response', 'INVALID_RESPONSE');
          }
          dispatch({ type: 'response-received', response });
          activeRunIdRef.current = null;
        } else if (event.event === 'run.failed') {
          dispatch({ type: 'request-failed', error: backendEventError(event.data) });
          activeRunIdRef.current = null;
        }
      },
    }).catch((error: unknown) => {
      if (controller.signal.aborted || activeRunIdRef.current !== runId) return;
      dispatch({ type: 'request-failed', error: assistantError(error) });
      activeRunIdRef.current = null;
      abortControllerRef.current = null;
    }).finally(() => {
      window.clearTimeout(slowTimer);
      if (abortControllerRef.current === controller) abortControllerRef.current = null;
    });
  }, [abortCurrentRun]);

  const sendMessage = useCallback((message: string, context?: AssistantContextData) => {
    const cleanMessage = message.trim();
    if (!cleanMessage) return;
    const request: AssistantRequest = {
      message: cleanMessage,
      conversationId: state.conversationId,
      intentOverride: null,
      context: { language: currentLocale === 'en' ? 'en' : 'vi', ...context },
    };
    executeRequest(request, cleanMessage, true);
  }, [currentLocale, executeRequest, state.conversationId]);

  const submitIntentOverride = useCallback((intentOverride: IntentOverride, context?: AssistantContextData) => {
    if (!state.conversationId) return;
    const request: AssistantRequest = {
      message: null,
      conversationId: state.conversationId,
      intentOverride,
      context: { language: currentLocale === 'en' ? 'en' : 'vi', ...context },
    };
    executeRequest(request, intentDescription(intentOverride), true);
  }, [currentLocale, executeRequest, state.conversationId]);

  const retry = useCallback(() => {
    if (state.lastRequest) {
      executeRequest(state.lastRequest, state.lastRequest.message || 'Tiếp tục cập nhật lịch trình', false);
    }
  }, [executeRequest, state.lastRequest]);

  const abort = useCallback(() => {
    if (!activeRunIdRef.current) return;
    abortCurrentRun();
    dispatch({ type: 'request-aborted' });
  }, [abortCurrentRun]);

  const resetConversation = useCallback(() => {
    abortCurrentRun();
    dispatch({ type: 'reset' });
  }, [abortCurrentRun]);

  const value = useMemo<AssistantContextValue>(() => ({
    state,
    sendMessage,
    submitIntentOverride,
    retry,
    abort,
    resetConversation,
    openFloatingWidget: (initialMessage) => dispatch({ type: 'open-floating', initialMessage }),
    openHeaderDrawer: () => dispatch({ type: 'open-header-drawer' }),
    closeFloatingWidget: () => dispatch({ type: 'close-floating' }),
    closeHeaderDrawer: () => dispatch({ type: 'close-header-drawer' }),
    consumeFloatingInitialMessage: () => dispatch({ type: 'consume-floating-initial-message' }),
  }), [state, sendMessage, submitIntentOverride, retry, abort, resetConversation]);

  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}

export function useAssistant() {
  const context = useContext(AssistantContext);
  if (!context) throw new Error('useAssistant must be used within AssistantProvider');
  return context;
}
