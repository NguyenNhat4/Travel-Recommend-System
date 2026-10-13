'use client';

import React, { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react';
import type { ReactNode } from 'react';
import type { ProgressUpdate, ProgressActivity } from '../features/itinerary/widget/progressModel';
import type { components } from '../types/api.gen';
import type { components as V2 } from '../types/assistant-v2.gen';
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
import { getAssistantConversation } from '../services/assistantHistory';
import { ApiError, apiJson } from '../services/http';
import { newAssistantV2TurnId, requestAssistantV2Stream, type AssistantV2Request } from '../services/assistantV2Stream';
import { v2Actions, v2AsV1Response, v2Timeline } from '../features/itinerary/widget/widgetV2';

const CONVERSATION_STORAGE_KEY = 'vota.assistant.conversationId';
type IntentOverride = components['schemas']['TripIntentPatch'];
type V2UiAction = V2['schemas']['UiAction'];
type AssistantContextData = NonNullable<AssistantRequest['context']>;

interface AssistantContextValue {
  state: AssistantState;
  sendMessage: (message: string, context?: AssistantContextData) => void;
  submitIntentOverride: (intentOverride: IntentOverride, context?: AssistantContextData) => void;
  /**
   * Bấm thẻ khách sạn trong hàng "Phương án khác" (contract 1.20.0): lưu lựa chọn lên server ở nền, không thêm tin nhắn.
   * `true` khi server đã đổi lịch (câu trả lời gần nhất mang lịch mới), `false` khi lỗi.
   */
  selectStayOption: (index: number) => Promise<boolean>;
  retry: () => void;
  abort: () => void;
  resetConversation: () => void;
  loadConversation: (conversationId: string) => Promise<void>;
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
  if (error instanceof AssistantStreamError || error instanceof ApiError) {
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

const SLOW_NODE_MS = 12_000;

/** Next.js defaults to the current assistant; v1 requires an explicit compatibility override. */
const ASSISTANT_V2 = process.env.NEXT_PUBLIC_ASSISTANT_API !== 'v1';

function nodeProgress(data: Record<string, unknown>) {
  return {
    sequence: typeof data.sequence === 'number' ? data.sequence : undefined,
    nodeId: typeof data.nodeId === 'string' ? data.nodeId : undefined,
    outcome: typeof data.outcome === 'string' ? data.outcome : undefined,
    message: typeof data.message === 'string' ? data.message : undefined,
    durationMs: typeof data.durationMs === 'number' ? data.durationMs : undefined,
    progress: data.progress && typeof data.progress==='object' ? data.progress as ProgressUpdate : undefined,
  };
}

function intentDescription(intent: IntentOverride) {
  const fields = [intent.destination, intent.days ? `${intent.days} ngày` : null].filter(Boolean);
  return fields.length ? `Cập nhật yêu cầu: ${fields.join(' · ')}` : 'Cập nhật yêu cầu chuyến đi';
}

export function AssistantProvider({ children }: { children: ReactNode }) {
  const { currentLocale, currentPersona, authReady } = useTravel();
  const [state, dispatch] = useReducer(assistantReducer, null, () => createInitialAssistantState());
  const activeRunIdRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const historyVersionRef = useRef(0);
  const previousPersonaRef = useRef<string | null | undefined>(undefined);
  // Assistant v2: revision lịch đang hiện, lệnh của các nút lượt trước, mã lượt để gửi lại không thành lượt mới.
  const planRevisionRef = useRef<number | null>(null);
  const v2ActionsRef = useRef(new Map<string, V2UiAction>());
  const lastV2TurnRef = useRef<{ request: AssistantRequest; clientTurnId: string } | null>(null);

  const abortCurrentRun = useCallback(() => {
    historyVersionRef.current += 1;
    const controller = abortControllerRef.current;
    if (controller && !controller.signal.aborted) controller.abort();
    abortControllerRef.current = null;
    activeRunIdRef.current = null;
  }, []);

  useEffect(() => {
    if (!authReady) return;
    const personaId = currentPersona?.id ?? null;
    if (previousPersonaRef.current !== undefined) {
      if (previousPersonaRef.current !== personaId) {
        abortCurrentRun();
        dispatch({ type: 'reset' });
        previousPersonaRef.current = personaId;
        return;
      }
    }
    previousPersonaRef.current = personaId;
    let conversationId: string | null = null;
    try {
      conversationId = window.sessionStorage.getItem(CONVERSATION_STORAGE_KEY);
    } catch {
      // Storage can be unavailable in privacy-restricted contexts; runtime remains usable.
    }
    dispatch({ type: 'hydrate-conversation', conversationId });
    if (conversationId && personaId) {
      const version = historyVersionRef.current;
      void getAssistantConversation(conversationId).then((detail) => {
        if (version === historyVersionRef.current) dispatch({ type: 'conversation-loaded', detail });
      }).catch((error: unknown) => {
        if (version !== historyVersionRef.current) return;
        if (error instanceof ApiError && error.code === 'CONVERSATION_NOT_FOUND') {
          dispatch({ type: 'reset' });
        } else {
          dispatch({ type: 'request-failed', error: assistantError(error) });
        }
      });
    }
  }, [authReady, currentPersona?.id, abortCurrentRun]);

  useEffect(() => {
    if (!state.isHydrated) return;
    try {
      if (state.conversationId) window.sessionStorage.setItem(CONVERSATION_STORAGE_KEY, state.conversationId);
      else window.sessionStorage.removeItem(CONVERSATION_STORAGE_KEY);
    } catch {
      // The backend session remains usable for this tab even if browser storage is disabled.
    }
  }, [state.conversationId, state.isHydrated]);

  useEffect(() => () => abortCurrentRun(), [abortCurrentRun]);

  const executeRequestRef = useRef<((request: AssistantRequest, userText: string, appendUser: boolean) => void) | null>(null);

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
    // Chậm = 12 giây không có node nào xong. Thời gian dồn vào các node gọi LLM, nên đo theo từng node chứ không
    // theo cả lượt: lượt dài nhưng vẫn tiến đều thì không báo chậm.
    const requestStartedAt = Date.now();
    let previewTimer = 0;
    let slowTimer = 0;
    const armSlowTimer = () => {
      window.clearTimeout(slowTimer);
      slowTimer = window.setTimeout(() => {
        if (isCurrent()) dispatch({ type: 'slow-state', isSlow: true });
      }, SLOW_NODE_MS);
    };
    armSlowTimer();

    if (ASSISTANT_V2) {
      // Gửi lại (retry) đúng request cũ thì giữ mã lượt: server trả câu trả lời đã có, không chạy lượt mới.
      const clientTurnId = lastV2TurnRef.current?.request === request
        ? lastV2TurnRef.current.clientTurnId : newAssistantV2TurnId();
      lastV2TurnRef.current = { request, clientTurnId };
      const uiAction = request.message ? v2ActionsRef.current.get(request.message) ?? null : null;
      const body: AssistantV2Request = {
        clientTurnId, basePlanRevision: planRevisionRef.current, conversationId: request.conversationId ?? null,
        message: uiAction ? null : request.message ?? null, intentOverride: request.intentOverride ?? null, uiAction,
        context: { language: request.context?.language === 'en' ? 'en' : 'vi' },
      };
      void requestAssistantV2Stream(body, {
        signal: controller.signal,
        onEvent: (event) => {
          if (!isCurrent()) return;
          if (event.event === 'start') {
            dispatch({ type: 'run-started', runId: event.runId, requestId: event.runId });
            dispatch({ type: 'v2-progress-started' });
          } else if (event.event === 'activity') {
            dispatch({ type: 'v2-progress', entry: v2Timeline(event.data) });
            armSlowTimer();
          } else if (event.event === 'tool-completed') {
            dispatch({ type: 'v2-progress', entry: v2Timeline(event.data, true) });
            armSlowTimer();
          } else if (event.event === 'preview') {
            dispatch({ type: 'run-preview', preview: { runId: event.runId, products: event.data.products.slice(0, 6) } });
            window.clearTimeout(previewTimer);
            previewTimer = window.setTimeout(() => {
              if (isCurrent()) dispatch({ type: 'preview-visible' });
            }, Math.max(0, 5000 - (Date.now() - requestStartedAt)));
          }
        },
      }).then((final) => {
        if (!isCurrent()) return;
        planRevisionRef.current = final.planRevision;
        v2ActionsRef.current = v2Actions(final);
        dispatch({ type: 'response-received', response: v2AsV1Response(final) });
        activeRunIdRef.current = null;
      }).catch((error: unknown) => {
        if (controller.signal.aborted || activeRunIdRef.current !== runId) return;
        const failure = assistantError(error);
        activeRunIdRef.current = null;
        if (failure.code === 'CONVERSATION_NOT_FOUND' && request.conversationId && request.message) {
          planRevisionRef.current = null;
          dispatch({ type: 'conversation-restarted' });
          executeRequestRef.current?.({ ...request, conversationId: null }, userText, false);
          return;
        }
        dispatch(failure.code === 'VALIDATION_ERROR' && failure.status === 400
          ? { type: 'request-refused', text: failure.message } : { type: 'request-failed', error: failure });
      }).finally(() => {
        window.clearTimeout(slowTimer);
        window.clearTimeout(previewTimer);
        if (abortControllerRef.current === controller) abortControllerRef.current = null;
      });
      return;
    }

    void requestAssistantStream(request, {
      signal: controller.signal,
      onEvent: (event: AssistantStreamEvent) => {
        if (!isCurrent()) return;
        if (event.event === 'run.started') {
          dispatch(typeof event.data.runId==='string' && typeof event.data.requestId==='string'
            ? {type:'run-started',runId:event.data.runId,requestId:event.data.requestId}
            : { type: 'stream-started' });
        } else if (event.event === 'graph.topology') {
          dispatch({ type: 'topology-received', topology: event.data });
        } else if (event.event === 'node.activity') {
          if (typeof event.data.nodeId==='string' && typeof event.data.code==='string') {
            dispatch({type:'node-activity',activity:event.data as ProgressActivity});
            armSlowTimer();
          }
        } else if (event.event === 'run.preview') {
          if (Array.isArray(event.data.products) && typeof event.data.runId==='string') {
            const preview = event.data as components['schemas']['AssistantRunPreview'];
            dispatch({type:'run-preview',preview});
            window.clearTimeout(previewTimer);
            previewTimer=window.setTimeout(() => {
              if (isCurrent()) dispatch({type:'preview-visible'});
            },Math.max(0,5000-(Date.now()-requestStartedAt)));
          }
        } else if (event.event === 'node.completed') {
          dispatch({ type: 'node-completed', progress: nodeProgress(event.data) });
          armSlowTimer();
        } else if (event.event === 'run.completed') {
          const response = event.data.response;
          if (!isAssistantResponse(response)) {
            throw new AssistantStreamError('Backend returned an invalid assistant response', 'INVALID_RESPONSE');
          }
          dispatch({ type: 'response-received', response });
          activeRunIdRef.current = null;
        } else if (event.event === 'run.failed') {
          const error = backendEventError(event.data);
          // Hội thoại đã hết hạn: gửi lại đúng tin nhắn như hội thoại mới (hợp đồng Frontend §8).
          // Request mới có conversationId null nên không thể 404 lần nữa. Patch chip không có
          // message thì không gửi lại được, vì contract bắt intentOverride đi cùng conversationId.
          if (error.code === 'CONVERSATION_NOT_FOUND' && request.conversationId && request.message) {
            dispatch({ type: 'conversation-restarted' });
            executeRequestRef.current?.({ ...request, conversationId: null }, userText, false);
            return;
          }
          // Ngoài phạm vi (đặt chỗ, chèn lệnh, chuyện ngoài du lịch): backend trả VALIDATION_ERROR kèm câu từ chối
          // của trợ lý — hiện như tin nhắn thường, không phải khung lỗi.
          dispatch(error.code === 'VALIDATION_ERROR'
            ? { type: 'request-refused', text: error.message }
            : { type: 'request-failed', error });
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
      window.clearTimeout(previewTimer);
      if (abortControllerRef.current === controller) abortControllerRef.current = null;
    });
  }, [abortCurrentRun]);

  useEffect(() => {
    executeRequestRef.current = executeRequest;
  }, [executeRequest]);

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

  const selectStayOption = useCallback(async (index: number) => {
    if (!state.conversationId) return false;
    if (ASSISTANT_V2) {
      // Saved v1 cards have no server-issued v2 action. Send the user's choice to the current agent for refresh.
      const option = state.response?.status === 'COMPLETED'
        ? state.response.stayOptions?.options.find((item) => item.index === index) : undefined;
      const hotel = option?.itinerary.stays?.[0]?.product ?? option?.itinerary.stay?.product;
      if (!hotel) return false;
      const message = `Chọn khách sạn ${hotel.name}`;
      executeRequest({ message, conversationId: state.conversationId, intentOverride: null,
        context: { language: currentLocale === 'en' ? 'en' : 'vi' } }, message, true);
      return true;
    }
    const request: AssistantRequest = {
      message: null,
      conversationId: state.conversationId,
      intentOverride: null,
      selectStayOption: { index },
      context: { language: currentLocale === 'en' ? 'en' : 'vi' },
    };
    try {
      const response = await apiJson<AssistantResponse>('/api/v1/assistant/itineraries', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request), cache: 'no-store',
      });
      if (!isAssistantResponse(response) || response.status !== 'COMPLETED') return false;
      dispatch({ type: 'stay-option-applied', response });
      return true;
    } catch {
      return false;
    }
  }, [currentLocale, executeRequest, state.conversationId, state.response]);

  const retry = useCallback(() => {
    if (state.lastRequest) {
      executeRequest(state.lastRequest, state.lastRequest.message || 'Tiếp tục cập nhật lịch trình', false);
    } else if (state.conversationId && currentPersona?.id) {
      abortCurrentRun();
      const version = historyVersionRef.current;
      void getAssistantConversation(state.conversationId).then((detail) => {
        if (version === historyVersionRef.current) dispatch({ type: 'conversation-loaded', detail });
      }).catch((error: unknown) => {
        if (version === historyVersionRef.current) dispatch({ type: 'request-failed', error: assistantError(error) });
      });
    }
  }, [abortCurrentRun, currentPersona?.id, executeRequest, state.lastRequest, state.conversationId]);

  const abort = useCallback(() => {
    if (!activeRunIdRef.current) return;
    abortCurrentRun();
    dispatch({ type: 'request-aborted' });
  }, [abortCurrentRun]);

  const resetConversation = useCallback(() => {
    abortCurrentRun();
    planRevisionRef.current = null;
    v2ActionsRef.current = new Map();
    dispatch({ type: 'reset' });
  }, [abortCurrentRun]);

  const loadConversation = useCallback(async (conversationId: string) => {
    abortCurrentRun();
    const version = historyVersionRef.current;
    const detail = await getAssistantConversation(conversationId);
    if (version === historyVersionRef.current) dispatch({ type: 'conversation-loaded', detail });
  }, [abortCurrentRun]);

  const value = useMemo<AssistantContextValue>(() => ({
    state,
    sendMessage,
    submitIntentOverride,
    selectStayOption,
    retry,
    abort,
    resetConversation,
    loadConversation,
    openFloatingWidget: (initialMessage) => dispatch({ type: 'open-floating', initialMessage }),
    openHeaderDrawer: () => dispatch({ type: 'open-header-drawer' }),
    closeFloatingWidget: () => dispatch({ type: 'close-floating' }),
    closeHeaderDrawer: () => dispatch({ type: 'close-header-drawer' }),
    consumeFloatingInitialMessage: () => dispatch({ type: 'consume-floating-initial-message' }),
  }), [state, sendMessage, submitIntentOverride, selectStayOption, retry, abort, resetConversation, loadConversation]);

  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}

export function useAssistant() {
  const context = useContext(AssistantContext);
  if (!context) throw new Error('useAssistant must be used within AssistantProvider');
  return context;
}
