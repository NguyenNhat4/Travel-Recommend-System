// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AssistantConversation } from '../../src/components/assistant/AssistantConversation';
import { createInitialAssistantState, type AssistantState } from '../../src/context/assistantState';

const mocks = vi.hoisted(() => ({
  state: {} as AssistantState,
  sendMessage: vi.fn(),
  setCurrentLang: vi.fn(),
}));

vi.mock('next/image', () => ({ default: () => null }));
vi.mock('../../src/context/AssistantProvider', () => ({
  useAssistant: () => ({
    state: mocks.state,
    sendMessage: mocks.sendMessage,
    submitIntentOverride: vi.fn(),
    retry: vi.fn(),
    abort: vi.fn(),
    resetConversation: vi.fn(),
    consumeFloatingInitialMessage: vi.fn(),
  }),
}));
vi.mock('../../src/context/TravelContext', () => ({
  useTravel: () => ({ currentLocale: 'vi', showToast: vi.fn() }),
}));
vi.mock('../../src/hooks/useSpeechRecognition', () => ({
  useSpeechRecognition: () => ({
    isSupported: false,
    isListening: false,
    interimTranscript: '',
    currentLang: 'vi-VN',
    setCurrentLang: mocks.setCurrentLang,
    toggleListening: vi.fn(),
  }),
}));
vi.mock('../../src/hooks/useAssistantCart', () => ({ useAssistantCart: () => vi.fn() }));

describe('AssistantConversation initial trip starter', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    mocks.state = { ...createInitialAssistantState(), isHydrated: true };
    mocks.sendMessage.mockReset();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ destinations: [{ destination: 'Nha Trang', productCount: 34 }] }),
    });
  });

  afterEach(() => {
    cleanup();
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('renders only before the first request starts', async () => {
    const view = render(<AssistantConversation inputId="assistant-test-input" />);
    expect(screen.getByText(/Hãy cung cấp thông tin đầy đủ nhất có thể.*để đề xuất chính xác và sát nhu cầu của bạn hơn/)).toBeTruthy();
    await screen.findByRole('button', { name: 'Nha Trang' });

    fireEvent.click(screen.getByRole('button', { name: 'Tạo lịch trình' }));
    expect(mocks.sendMessage).toHaveBeenCalledWith(
      'Tôi chọn đi Nha Trang trong 3 ngày cho gia đình có trẻ nhỏ, ưu tiên nghỉ dưỡng sang trọng.',
    );

    mocks.state = {
      ...mocks.state,
      phase: 'connecting',
      transcript: [{ id: 'user-1', sender: 'user', text: 'Request đầu tiên', createdAt: Date.now() }],
    };
    view.rerender(<AssistantConversation inputId="assistant-test-input" />);

    expect(screen.queryByText('Tương tác cùng AI')).toBeNull();
  });

  it.each([
    {
      phase: 'needs_clarification' as const,
      text: 'Bạn muốn đi trong bao nhiêu ngày?',
      cardLabel: 'Cần làm rõ yêu cầu',
      response: {
        status: 'NEEDS_CLARIFICATION' as const,
        conversationId: 'conversation-1',
        question: 'Bạn muốn đi trong bao nhiêu ngày?',
        missingFields: ['days' as const],
        suggestedValues: { days: [2, 3] },
      },
    },
    {
      phase: 'no_results' as const,
      text: 'Không tìm thấy sản phẩm đáp ứng điều kiện bắt buộc.',
      cardLabel: 'Không tìm thấy kết quả',
      response: {
        status: 'NO_RESULTS' as const,
        conversationId: 'conversation-1',
        message: 'Không tìm thấy sản phẩm đáp ứng điều kiện bắt buộc.',
        suggestions: ['Nới lỏng điều kiện'],
      },
    },
  ])('renders $phase as one normal assistant message without a result card', ({ phase, text, cardLabel, response }) => {
    mocks.state = {
      ...mocks.state,
      phase,
      response,
      transcript: [{ id: 'assistant-1', sender: 'assistant', text, response, createdAt: Date.now() }],
    };

    render(<AssistantConversation inputId="assistant-test-input" />);

    expect(screen.getAllByText(text)).toHaveLength(1);
    expect(screen.queryByRole('region', { name: cardLabel })).toBeNull();
  });

  it('renders no-results suggestions as chips under the last message and sends the tapped one', () => {
    const response = { status: 'NO_RESULTS' as const, conversationId: 'conversation-1',
      message: 'Hiện chưa có sản phẩm.', suggestions: ['Đi Huế 3 ngày'] };
    mocks.state = { ...mocks.state, phase: 'no_results', response, transcript: [
      { id: 'assistant-1', sender: 'assistant', text: response.message, response, createdAt: Date.now() },
    ] };
    render(<AssistantConversation inputId="assistant-test-input" />);
    fireEvent.click(screen.getByRole('button', { name: 'Đi Huế 3 ngày' }));
    expect(mocks.sendMessage).toHaveBeenCalledWith('Đi Huế 3 ngày');
  });
});
