// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  // These scenarios intentionally cover the retained v1 compatibility client, not the Next.js default.
  const previousVersion = process.env.NEXT_PUBLIC_ASSISTANT_API;
  process.env.NEXT_PUBLIC_ASSISTANT_API = 'v1';
  return {
  previousVersion,
  requestAssistantStream: vi.fn(), getAssistantConversation: vi.fn(),
  travel: { currentLocale: 'vi', authReady: true, currentPersona: null as { id: string; code: string } | null },
  };
});
afterAll(() => {
  if (mocks.previousVersion === undefined) delete process.env.NEXT_PUBLIC_ASSISTANT_API;
  else process.env.NEXT_PUBLIC_ASSISTANT_API = mocks.previousVersion;
});

vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => mocks.travel }));

vi.mock('../../src/services/assistantStream', () => ({
  AssistantStreamError: class AssistantStreamError extends Error {
    code = 'TEST_ERROR';
    retryable = false;
  },
  requestAssistantStream: mocks.requestAssistantStream,
}));

vi.mock('../../src/services/assistantHistory', () => ({
  getAssistantConversation: mocks.getAssistantConversation,
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn() }),
}));

import { AssistantProvider, useAssistant } from '../../src/context/AssistantProvider';
import { ApiError } from '../../src/services/http';
import type { AssistantStreamEvent } from '../../src/services/assistantStream';

function Probe() {
  const assistant = useAssistant();
  return <div>
    <output data-testid="phase">{assistant.state.phase}</output>
    <output data-testid="conversation">{assistant.state.conversationId ?? 'none'}</output>
    <output data-testid="transcript">{assistant.state.transcript.map((message) => message.text).join('|')}</output>
    <output data-testid="error">{assistant.state.error?.code ?? 'none'}</output>
    <output data-testid="slow">{String(assistant.state.isSlow)}</output>
    <button onClick={() => assistant.sendMessage('Plan trip', { language: 'en' })}>send</button>
    <button onClick={() => assistant.submitIntentOverride({ days: 3 }, { language: 'en' })}>override</button>
    <button onClick={assistant.retry}>retry</button>
    <button onClick={assistant.abort}>abort</button>
    <button onClick={assistant.resetConversation}>reset</button>
    <button onClick={() => void assistant.loadConversation('archive-id')}>load</button>
  </div>;
}

function mount() {
  return render(<AssistantProvider><Probe /></AssistantProvider>);
}

function archive(conversationId: string) {
  return {
    conversation: { conversationId, title: 'Nha Trang', status: 'open',
      createdAt: '2026-09-25T01:00:00Z', updatedAt: '2026-09-25T01:01:00Z', messageCount: 2 },
    messages: [
      { messageId: 1, role: 'user', content: 'Nha Trang 3 ngày', createdAt: '2026-09-25T01:00:00Z' },
      { messageId: 2, role: 'assistant', content: 'Bạn đi ngày nào?', createdAt: '2026-09-25T01:01:00Z',
        response: { status: 'NEEDS_CLARIFICATION', conversationId, question: 'Bạn đi ngày nào?' } },
    ],
  };
}

function completed(response: Record<string, unknown>): AssistantStreamEvent {
  return { event: 'run.completed', data: { response } };
}

describe('AssistantProvider', () => {
  beforeEach(() => {
    sessionStorage.clear();
    mocks.requestAssistantStream.mockReset();
    mocks.requestAssistantStream.mockResolvedValue(undefined);
    mocks.getAssistantConversation.mockReset();
    mocks.travel.authReady = true;
    mocks.travel.currentPersona = null;
  });
  afterEach(cleanup);

  it('waits for the authenticated session then restores messages and continues the saved chat', async () => {
    sessionStorage.setItem('vota.assistant.conversationId', 'restored-id');
    mocks.travel.authReady = false;
    mocks.getAssistantConversation.mockResolvedValue(archive('restored-id'));
    const view = mount();
    expect(mocks.getAssistantConversation).not.toHaveBeenCalled();
    expect(sessionStorage.getItem('vota.assistant.conversationId')).toBe('restored-id');

    mocks.travel.currentPersona = { id: 'user-1', code: 'P1' };
    mocks.travel.authReady = true;
    view.rerender(<AssistantProvider><Probe /></AssistantProvider>);
    await waitFor(() => expect(screen.getByTestId('transcript').textContent).toBe('Nha Trang 3 ngày|Bạn đi ngày nào?'));
    expect(screen.getByTestId('phase').textContent).toBe('needs_clarification');
    fireEvent.click(screen.getByText('send'));
    expect(mocks.requestAssistantStream.mock.calls[0][0].conversationId).toBe('restored-id');

    cleanup();
    mount();
    await waitFor(() => expect(screen.getByTestId('transcript').textContent).toBe('Nha Trang 3 ngày|Bạn đi ngày nào?'));
    expect([...Array(sessionStorage.length)].map((_, index) => sessionStorage.key(index))).toEqual(['vota.assistant.conversationId']);
  });

  it('restores in StrictMode after effect cleanup and replay', async () => {
    sessionStorage.setItem('vota.assistant.conversationId', 'restored-id');
    mocks.travel.currentPersona = { id: 'user-1', code: 'P1' };
    mocks.getAssistantConversation.mockResolvedValue(archive('restored-id'));
    render(<React.StrictMode><AssistantProvider><Probe /></AssistantProvider></React.StrictMode>);
    await waitFor(() => expect(screen.getByTestId('transcript').textContent).toContain('Bạn đi ngày nào?'));
  });

  it('restores the latest structured itinerary along with its transcript', async () => {
    sessionStorage.setItem('vota.assistant.conversationId', 'planned-id');
    mocks.travel.currentPersona = { id: 'user-1', code: 'P1' };
    const detail = archive('planned-id');
    mocks.getAssistantConversation.mockResolvedValue({
      ...detail,
      messages: [detail.messages[0], { ...detail.messages[1], content: 'Your itinerary', response: {
        status: 'COMPLETED', conversationId: 'planned-id', warnings: [],
        itinerary: { days: [], estimatedTotal: null, currency: 'VND', budgetStatus: 'UNKNOWN' },
      } }],
    });
    mount();
    await waitFor(() => expect(screen.getByTestId('phase').textContent).toBe('completed'));
    expect(screen.getByTestId('transcript').textContent).toBe('Nha Trang 3 ngày|Your itinerary');
  });

  it.each(['reset', 'send', 'account change', 'unmount'])('ignores delayed restoration after %s', async (action) => {
    sessionStorage.setItem('vota.assistant.conversationId', 'restored-id');
    mocks.travel.currentPersona = { id: 'user-1', code: 'P1' };
    let resolve!: (detail: ReturnType<typeof archive>) => void;
    mocks.getAssistantConversation.mockReturnValue(new Promise((done) => { resolve = done; }));
    const view = mount();
    if (action === 'account change') {
      mocks.travel.currentPersona = { id: 'user-2', code: 'P1' };
      view.rerender(<AssistantProvider><Probe /></AssistantProvider>);
    } else if (action === 'unmount') {
      view.unmount();
      mocks.travel.currentPersona = null;
      mount();
    } else fireEvent.click(screen.getByText(action));
    await act(async () => resolve(archive('restored-id')));
    expect(screen.getByTestId('transcript').textContent).not.toContain('Bạn đi ngày nào?');
    if (action !== 'send' && action !== 'unmount') expect(screen.getByTestId('conversation').textContent).toBe('none');
  });

  it('clears an unavailable saved conversation', async () => {
    sessionStorage.setItem('vota.assistant.conversationId', 'missing-id');
    mocks.travel.currentPersona = { id: 'user-1', code: 'P1' };
    mocks.getAssistantConversation.mockRejectedValue(new ApiError('Missing', 'CONVERSATION_NOT_FOUND', 404, false));
    mount();
    await waitFor(() => expect(sessionStorage.getItem('vota.assistant.conversationId')).toBeNull());
    expect(screen.getByTestId('conversation').textContent).toBe('none');
  });

  it('keeps the saved ID and reports a temporary history failure', async () => {
    sessionStorage.setItem('vota.assistant.conversationId', 'restored-id');
    mocks.travel.currentPersona = { id: 'user-1', code: 'P1' };
    mocks.getAssistantConversation.mockRejectedValue(new ApiError('Offline', 'NETWORK_ERROR', 0, true));
    mount();
    await waitFor(() => expect(screen.getByTestId('error').textContent).toBe('NETWORK_ERROR'));
    expect(sessionStorage.getItem('vota.assistant.conversationId')).toBe('restored-id');
    mocks.getAssistantConversation.mockResolvedValue(archive('restored-id'));
    fireEvent.click(screen.getByText('retry'));
    await waitFor(() => expect(screen.getByTestId('transcript').textContent).toContain('Bạn đi ngày nào?'));
    expect(screen.getByTestId('error').textContent).toBe('none');
    expect(mocks.requestAssistantStream).not.toHaveBeenCalled();
  });

  it('hydrates and synchronizes only conversationId in tab-scoped sessionStorage', async () => {
    sessionStorage.setItem('vota.assistant.conversationId', 'restored-id');
    let onEvent: ((event: AssistantStreamEvent) => void) | undefined;
    mocks.requestAssistantStream.mockImplementation((_request, options) => {
      onEvent = options.onEvent;
      return Promise.resolve();
    });
    mount();

    await waitFor(() => expect(screen.getByTestId('conversation').textContent).toBe('restored-id'));
    fireEvent.click(screen.getByText('send'));
    expect(mocks.requestAssistantStream.mock.calls[0][0]).toEqual({
      message: 'Plan trip',
      conversationId: 'restored-id',
      intentOverride: null,
      context: { language: 'en' },
    });
    onEvent?.(completed({ status: 'NO_RESULTS', conversationId: 'backend-id', message: 'No matches', suggestions: [] }));

    await waitFor(() => expect(sessionStorage.getItem('vota.assistant.conversationId')).toBe('backend-id'));
    expect([...Array(sessionStorage.length)].map((_, index) => sessionStorage.key(index))).toEqual(['vota.assistant.conversationId']);
    expect(screen.getByTestId('transcript').textContent).toContain('Plan trip');
    expect(screen.getByTestId('transcript').textContent).toContain('No matches');

    cleanup();
    mount();
    await waitFor(() => expect(screen.getByTestId('conversation').textContent).toBe('backend-id'));
    expect(screen.getByTestId('transcript').textContent).toBe('');
    expect(mocks.getAssistantConversation).not.toHaveBeenCalled();
  });

  it('submits a clarification override with the current backend conversation', async () => {
    sessionStorage.setItem('vota.assistant.conversationId', 'clarification-id');
    mount();
    await waitFor(() => expect(screen.getByTestId('conversation').textContent).toBe('clarification-id'));
    fireEvent.click(screen.getByText('override'));

    expect(mocks.requestAssistantStream.mock.calls[0][0]).toEqual({
      message: null,
      conversationId: 'clarification-id',
      intentOverride: { days: 3 },
      context: { language: 'en' },
    });
  });

  it('loads an archived transcript and makes it the active conversation', async () => {
    mocks.getAssistantConversation.mockResolvedValue({
      conversation: {
        conversationId: 'archive-id', title: 'Nha Trang', status: 'open',
        createdAt: '2026-09-25T01:00:00Z', updatedAt: '2026-09-25T01:01:00Z', messageCount: 2,
      },
      messages: [
        { messageId: 1, role: 'user', content: 'Nha Trang 3 ngày', createdAt: '2026-09-25T01:00:00Z' },
        { messageId: 2, role: 'assistant', content: 'Bạn đi ngày nào?', createdAt: '2026-09-25T01:01:00Z',
          response: { status: 'NEEDS_CLARIFICATION', conversationId: 'archive-id', question: 'Bạn đi ngày nào?' } },
      ],
    });
    mount();
    fireEvent.click(screen.getByText('load'));

    await waitFor(() => expect(screen.getByTestId('conversation').textContent).toBe('archive-id'));
    expect(screen.getByTestId('transcript').textContent).toBe('Nha Trang 3 ngày|Bạn đi ngày nào?');
    // sessionStorage được ghi trong effect sau lần render có conversationId; chờ thay vì đọc ngay.
    await waitFor(() => expect(sessionStorage.getItem('vota.assistant.conversationId')).toBe('archive-id'));
  });

  it('resends an expired conversation once as a new conversation', async () => {
    const eventHandlers: Array<(event: AssistantStreamEvent) => void> = [];
    mocks.requestAssistantStream.mockImplementation((_request, options) => {
      eventHandlers.push(options.onEvent);
      return Promise.resolve();
    });
    sessionStorage.setItem('vota.assistant.conversationId', 'expired-id');
    mount();
    await waitFor(() => expect(screen.getByTestId('conversation').textContent).toBe('expired-id'));
    fireEvent.click(screen.getByText('send'));
    const originalRequest = mocks.requestAssistantStream.mock.calls[0][0];
    act(() => eventHandlers[0]({
      event: 'run.failed',
      data: { httpStatus: 404, error: { code: 'CONVERSATION_NOT_FOUND', message: 'Expired', retryable: false } },
    }));

    expect(mocks.requestAssistantStream).toHaveBeenCalledTimes(2);
    expect(mocks.requestAssistantStream.mock.calls[1][0]).toEqual({ ...originalRequest, conversationId: null });
    expect(screen.getByTestId('error').textContent).toBe('none');
    expect(screen.getByTestId('transcript').textContent).toBe('Plan trip|Đã bắt đầu cuộc trò chuyện mới.');
    await waitFor(() => expect(sessionStorage.getItem('vota.assistant.conversationId')).toBeNull());

    act(() => eventHandlers[1](completed({ status: 'NO_RESULTS', conversationId: 'fresh-id', message: 'None' })));
    await waitFor(() => expect(screen.getByTestId('conversation').textContent).toBe('fresh-id'));
    expect(mocks.requestAssistantStream).toHaveBeenCalledTimes(2);
  });

  it('shows an expired intent override instead of resending it without a conversation', async () => {
    let onEvent: ((event: AssistantStreamEvent) => void) | undefined;
    mocks.requestAssistantStream.mockImplementation((_request, options) => {
      onEvent = options.onEvent;
      return Promise.resolve();
    });
    sessionStorage.setItem('vota.assistant.conversationId', 'expired-id');
    mount();
    await waitFor(() => expect(screen.getByTestId('conversation').textContent).toBe('expired-id'));
    fireEvent.click(screen.getByText('override'));
    act(() => onEvent?.({
      event: 'run.failed',
      data: { httpStatus: 404, error: { code: 'CONVERSATION_NOT_FOUND', message: 'Expired', retryable: false } },
    }));

    await waitFor(() => expect(screen.getByTestId('error').textContent).toBe('CONVERSATION_NOT_FOUND'));
    expect(screen.getByTestId('conversation').textContent).toBe('none');
    expect(mocks.requestAssistantStream).toHaveBeenCalledTimes(1);
  });

  it('keeps backend conversation context for unsupported destinations', async () => {
    let onEvent: ((event: AssistantStreamEvent) => void) | undefined;
    mocks.requestAssistantStream.mockImplementation((_request, options) => {
      onEvent = options.onEvent;
      return Promise.resolve();
    });
    mount();
    fireEvent.click(screen.getByText('send'));
    onEvent?.({
      event: 'run.failed',
      data: {
        error: {
          code: 'UNSUPPORTED_DESTINATION',
          message: 'Destination is not supported',
          details: { conversationId: 'backend-context-id', supportedDestinations: ['Nha Trang'] },
        },
      },
    });

    await waitFor(() => expect(screen.getByTestId('conversation').textContent).toBe('backend-context-id'));
    // sessionStorage được ghi trong effect sau lần render có conversationId; chờ thay vì đọc ngay.
    await waitFor(() => expect(sessionStorage.getItem('vota.assistant.conversationId')).toBe('backend-context-id'));
    expect(screen.getByTestId('error').textContent).toBe('UNSUPPORTED_DESTINATION');
    expect(screen.getByTestId('transcript').textContent).toBe('Plan trip');
  });

  it('offers explicit retry after a network error without fabricating an assistant response', async () => {
    mocks.requestAssistantStream
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(undefined);
    mount();
    fireEvent.click(screen.getByText('send'));
    await waitFor(() => expect(screen.getByTestId('phase').textContent).toBe('failed'));

    expect(screen.getByTestId('error').textContent).toBe('NETWORK_ERROR');
    expect(screen.getByTestId('transcript').textContent).toBe('Plan trip');
    fireEvent.click(screen.getByText('retry'));
    expect(mocks.requestAssistantStream).toHaveBeenCalledTimes(2);
    expect(mocks.requestAssistantStream.mock.calls[1][0]).toEqual(mocks.requestAssistantStream.mock.calls[0][0]);
  });

  it('marks a request slow after twelve seconds without fabricating progress', async () => {
    vi.useFakeTimers();
    mocks.requestAssistantStream.mockImplementation(() => new Promise(() => undefined));
    mount();
    fireEvent.click(screen.getByText('send'));

    act(() => vi.advanceTimersByTime(11_999));
    expect(screen.getByTestId('slow').textContent).toBe('false');
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByTestId('slow').textContent).toBe('true');
    expect(screen.getByTestId('transcript').textContent).toBe('Plan trip');
    expect(screen.getByTestId('phase').textContent).toBe('connecting');
    vi.useRealTimers();
  });

  it('measures slowness per node: each completed node clears the warning and restarts the clock', async () => {
    vi.useFakeTimers();
    let onEvent: (event: AssistantStreamEvent) => void = () => undefined;
    mocks.requestAssistantStream.mockImplementation((_request, options) => {
      onEvent = options.onEvent;
      return new Promise(() => undefined);
    });
    mount();
    fireEvent.click(screen.getByText('send'));

    act(() => vi.advanceTimersByTime(10_000));
    act(() => onEvent({ event: 'node.completed', data: { sequence: 1, nodeId: 'extract' } }));
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.getByTestId('slow').textContent).toBe('false');
    act(() => vi.advanceTimersByTime(2_000));
    expect(screen.getByTestId('slow').textContent).toBe('true');
    act(() => onEvent({ event: 'node.completed', data: { sequence: 2, nodeId: 'tool' } }));
    expect(screen.getByTestId('slow').textContent).toBe('false');
    vi.useRealTimers();
  });

  it('ignores callbacks from aborted, reset, or superseded runs', async () => {
    const eventHandlers: Array<(event: AssistantStreamEvent) => void> = [];
    const signals: AbortSignal[] = [];
    mocks.requestAssistantStream.mockImplementation((_request, options) => {
      eventHandlers.push(options.onEvent);
      signals.push(options.signal);
      return Promise.resolve();
    });
    mount();
    fireEvent.click(screen.getByText('send'));
    const abortedHandler = eventHandlers[0];
    fireEvent.click(screen.getByText('abort'));
    expect(signals[0].aborted).toBe(true);
    abortedHandler(completed({ status: 'NO_RESULTS', conversationId: 'aborted-id', message: 'Aborted result', suggestions: [] }));
    expect(screen.getByTestId('phase').textContent).toBe('aborted');
    expect(screen.getByTestId('transcript').textContent).toBe('Plan trip');

    fireEvent.click(screen.getByText('reset'));
    abortedHandler(completed({ status: 'NO_RESULTS', conversationId: 'stale-id', message: 'Stale', suggestions: [] }));
    expect(screen.getByTestId('conversation').textContent).toBe('none');
    expect(screen.getByTestId('transcript').textContent).toBe('');

    fireEvent.click(screen.getByText('send'));
    abortedHandler(completed({ status: 'NO_RESULTS', conversationId: 'stale-id', message: 'Stale', suggestions: [] }));
    eventHandlers[1](completed({ status: 'NO_RESULTS', conversationId: 'fresh-id', message: 'Fresh', suggestions: [] }));
    await waitFor(() => expect(screen.getByTestId('conversation').textContent).toBe('fresh-id'));
    expect(screen.getByTestId('transcript').textContent).not.toContain('Stale');
    expect(screen.getByTestId('transcript').textContent).toContain('Fresh');
  });
});


describe('stream activity timing', () => {
  afterEach(() => { cleanup(); vi.useRealTimers(); });
  it('resets the slow timer on activity', async () => {
    vi.useFakeTimers(); sessionStorage.clear();
    mocks.travel.authReady=true; mocks.travel.currentPersona=null;
    let emit: ((event:AssistantStreamEvent)=>void) | undefined;
    mocks.requestAssistantStream.mockImplementation((_request,options)=>{emit=options.onEvent;return new Promise(()=>{});});
    mount();fireEvent.click(screen.getByText('send'));
    await act(async()=>{await vi.advanceTimersByTimeAsync(11000);});
    act(()=>{emit!({event:'node.activity',data:{nodeId:'tool',code:'SEARCHING'}});});
    await act(async()=>{await vi.advanceTimersByTimeAsync(11000);});
    expect(screen.getByTestId('slow').textContent).toBe('false');
  });
  it('ignores run.preview from an older server: no cards before the answer (chốt 2026-10-14)', async () => {
    vi.useFakeTimers(); sessionStorage.clear();
    mocks.travel.authReady=true; mocks.travel.currentPersona=null;
    let emit: ((event:AssistantStreamEvent)=>void) | undefined;
    mocks.requestAssistantStream.mockImplementation((_request,options)=>{emit=options.onEvent;return new Promise(()=>{});});
    mount();fireEvent.click(screen.getByText('send'));
    act(()=>{emit!({event:'run.preview',data:{runId:'r',products:[]}});});
    await act(async()=>{await vi.advanceTimersByTimeAsync(6000);});
    act(()=>{emit!(completed({status:'NEEDS_CLARIFICATION',conversationId:'c',question:'Xong'}));});
    expect(screen.getByTestId('transcript').textContent).toContain('Xong');
  });
});
