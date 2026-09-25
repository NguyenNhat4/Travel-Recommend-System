// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ requestAssistantStream: vi.fn() }));

vi.mock('../../src/services/assistantStream', () => ({
  AssistantStreamError: class AssistantStreamError extends Error {
    code = 'TEST_ERROR';
    retryable = false;
  },
  requestAssistantStream: mocks.requestAssistantStream,
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({ push: vi.fn() }),
}));

import { AssistantProvider, useAssistant } from '../../src/context/AssistantProvider';
import { TravelProvider } from '../../src/context/TravelContext';
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
  </div>;
}

function mount() {
  return render(<TravelProvider><AssistantProvider><Probe /></AssistantProvider></TravelProvider>);
}

function completed(response: Record<string, unknown>): AssistantStreamEvent {
  return { event: 'run.completed', data: { response } };
}

describe('AssistantProvider', () => {
  beforeEach(() => {
    sessionStorage.clear();
    mocks.requestAssistantStream.mockReset();
    mocks.requestAssistantStream.mockResolvedValue(undefined);
  });
  afterEach(cleanup);

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
    expect(sessionStorage.getItem('vota.assistant.conversationId')).toBe('backend-context-id');
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

  it('marks a request slow after eight seconds without fabricating progress', async () => {
    vi.useFakeTimers();
    mocks.requestAssistantStream.mockImplementation(() => new Promise(() => undefined));
    mount();
    fireEvent.click(screen.getByText('send'));

    act(() => vi.advanceTimersByTime(8_000));
    expect(screen.getByTestId('slow').textContent).toBe('true');
    expect(screen.getByTestId('transcript').textContent).toBe('Plan trip');
    expect(screen.getByTestId('phase').textContent).toBe('connecting');
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
