// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import answer from '../../../shared/mocks/assistant-v2/answer.json';
import answer30 from '../../../shared/mocks/assistant-v2/answer-30.json';
import legacyCompleted from '../../../shared/mocks/itinerary-agent/completed.json';

const mocks = vi.hoisted(() => {
  delete process.env.NEXT_PUBLIC_ASSISTANT_API;
  return {
    requestAssistantV2Stream: vi.fn(), getAssistantConversation: vi.fn(), turn: 0,
    travel: { currentLocale: 'vi', authReady: true, currentPersona: null },
  };
});

vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => mocks.travel }));
vi.mock('../../src/services/assistantV2Stream', () => ({
  requestAssistantV2Stream: mocks.requestAssistantV2Stream,
  newAssistantV2TurnId: () => `turn${++mocks.turn}`,
}));
vi.mock('../../src/services/assistantHistory', () => ({ getAssistantConversation: mocks.getAssistantConversation }));
vi.mock('next/navigation', () => ({ usePathname: () => '/', useRouter: () => ({ push: vi.fn() }) }));

import { AssistantProvider, useAssistant } from '../../src/context/AssistantProvider';
import { ApiError } from '../../src/services/http';

function Probe() {
  const assistant = useAssistant();
  return <div>
    <output data-testid="phase">{assistant.state.phase}</output>
    <output data-testid="transcript">{assistant.state.transcript.map((message) => message.text).join('|')}</output>
    <button onClick={() => assistant.sendMessage('Khách sạn Huế')}>send</button>
    <button onClick={() => assistant.sendMessage('Đắt nhất thì sao?')}>fare</button>
    <button onClick={assistant.retry}>retry</button>
    <button onClick={() => void assistant.loadConversation('legacy-conv')}>loadLegacy</button>
    <button onClick={() => void assistant.selectStayOption(1)}>selectLegacyStay</button>
  </div>;
}

const final = (fields: Record<string, unknown> = {}) => ({ ...answer, conversationId: 'conv-1', ...fields });

describe('AssistantProvider defaults to assistant v2 without an environment override', () => {
  beforeEach(() => {
    mocks.turn = 0;
    mocks.requestAssistantV2Stream.mockReset();
    mocks.getAssistantConversation.mockReset();
    sessionStorage.clear();
  });
  afterEach(cleanup);
  afterAll(() => { delete process.env.NEXT_PUBLIC_ASSISTANT_API; });

  it('sends turn id and the shown plan revision, then the next turn continues the conversation', async () => {
    mocks.requestAssistantV2Stream.mockResolvedValueOnce(final({ planRevision: 2, message: 'Xin chào' }))
      .mockResolvedValueOnce(final());
    render(<AssistantProvider><Probe /></AssistantProvider>);
    fireEvent.click(screen.getByText('send'));
    await waitFor(() => expect(screen.getByTestId('transcript').textContent).toBe('Khách sạn Huế|Xin chào'));
    expect(mocks.requestAssistantV2Stream.mock.calls[0][0]).toMatchObject({ clientTurnId: 'turn1', basePlanRevision: null,
      conversationId: null, message: 'Khách sạn Huế', uiAction: null });
    fireEvent.click(screen.getByText('send'));
    await waitFor(() => expect(mocks.requestAssistantV2Stream).toHaveBeenCalledTimes(2));
    expect(mocks.requestAssistantV2Stream.mock.calls[1][0]).toMatchObject({ clientTurnId: 'turn2', basePlanRevision: 2,
      conversationId: 'conv-1' });
  });

  it('a button with a server action sends the action, not the label', async () => {
    mocks.requestAssistantV2Stream.mockResolvedValueOnce(final({ suggestions: [
      { label: 'Đắt nhất thì sao?', message: null, uiAction: { type: 'fare_query', actionId: 'a1' } }] }))
      .mockResolvedValueOnce(final());
    render(<AssistantProvider><Probe /></AssistantProvider>);
    fireEvent.click(screen.getByText('send'));
    await waitFor(() => expect(screen.getByTestId('phase').textContent).toBe('needs_clarification'));
    fireEvent.click(screen.getByText('fare'));
    await waitFor(() => expect(mocks.requestAssistantV2Stream).toHaveBeenCalledTimes(2));
    expect(mocks.requestAssistantV2Stream.mock.calls[1][0]).toMatchObject({ message: null,
      uiAction: { type: 'fare_query', actionId: 'a1' } });
  });

  it('retry after a failure keeps the same turn id; blocked input reads as a refusal', async () => {
    mocks.requestAssistantV2Stream.mockRejectedValueOnce(new ApiError('Bận', 'LLM_UNAVAILABLE', 503, true))
      .mockResolvedValueOnce(final({ message: 'Đã xong' }))
      .mockRejectedValueOnce(new ApiError('Mình chưa thể hỗ trợ yêu cầu này', 'VALIDATION_ERROR', 400, false));
    render(<AssistantProvider><Probe /></AssistantProvider>);
    fireEvent.click(screen.getByText('send'));
    await waitFor(() => expect(screen.getByTestId('phase').textContent).toBe('failed'));
    fireEvent.click(screen.getByText('retry'));
    await waitFor(() => expect(screen.getByTestId('transcript').textContent).toContain('Đã xong'));
    expect(mocks.requestAssistantV2Stream.mock.calls[1][0].clientTurnId).toBe('turn1');
    fireEvent.click(screen.getByText('send'));
    await waitFor(() => expect(screen.getByTestId('transcript').textContent).toContain('Mình chưa thể hỗ trợ'));
  });

  it('sends an archived hotel choice to v2 instead of the old v1 mutation', async () => {
    const hotel = answer30.recommendations.hotel[0];
    mocks.getAssistantConversation.mockResolvedValue({
      conversation: { conversationId: 'legacy-conv' },
      messages: [{ messageId: 1, role: 'assistant', content: 'Lịch cũ', createdAt: '2026-10-13T00:00:00Z',
        response: { ...legacyCompleted, conversationId: 'legacy-conv',
          stayOptions: { distanceKm: 0, options: [{ index: 1, kmDelta: 0, moneyDelta: 0,
            itinerary: { ...legacyCompleted.itinerary, stay: { product: hotel, nights: 1 } } }] } } }],
    });
    mocks.requestAssistantV2Stream.mockResolvedValue(final());
    render(<AssistantProvider><Probe /></AssistantProvider>);
    fireEvent.click(screen.getByText('loadLegacy'));
    await waitFor(() => expect(screen.getByTestId('phase').textContent).toBe('completed'));
    fireEvent.click(screen.getByText('selectLegacyStay'));
    await waitFor(() => expect(mocks.requestAssistantV2Stream).toHaveBeenCalledTimes(1));
    expect(mocks.requestAssistantV2Stream.mock.calls[0][0]).toMatchObject({
      conversationId: 'legacy-conv', message: `Chọn khách sạn ${hotel.name}`, uiAction: null,
    });
  });
});
