// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AiFloatingWidget } from '../../src/components/assistant/AiFloatingWidget';
import { createInitialAssistantState, type AssistantState } from '../../src/context/assistantState';

const mocks = vi.hoisted(() => ({
  state: {} as AssistantState,
  sendMessage: vi.fn(), resetConversation: vi.fn(), loadConversation: vi.fn(),
  consumeFloatingInitialMessage: vi.fn(), retry: vi.fn(), abort: vi.fn(), showToast: vi.fn(),
}));

vi.mock('next/image', () => ({ default: () => null }));
vi.mock('next/dynamic', () => ({ default: () => () => null }));
vi.mock('../../src/context/AssistantProvider', () => ({
  useAssistant: () => ({ state: mocks.state, ...mocks }),
}));
vi.mock('../../src/context/TravelContext', () => ({
  useTravel: () => ({ currentRoute: '/', showToast: mocks.showToast, navigate: vi.fn(), addToCart: vi.fn() }),
}));
vi.mock('../../src/hooks/useAssistantCart', () => ({ useAssistantCart: () => vi.fn() }));

describe('floating assistant opening', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.state = { ...createInitialAssistantState(), isHydrated: true };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ destinations: [{ destination: 'Hội An', productCount: 15 }] }),
    }));
    Element.prototype.scrollTo = vi.fn();
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  function open() {
    const view = render(<AiFloatingWidget />);
    fireEvent.click(screen.getByRole('button', { name: 'Mở trợ lý du lịch AI' }));
    return view;
  }

  it('starts with one empty composer and no request or trip form', () => {
    open();
    expect(screen.getByRole('heading', { name: 'Bạn muốn đi đâu tiếp theo?' })).toBeTruthy();
    expect(screen.getAllByRole('textbox')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Gửi yêu cầu' }).hasAttribute('disabled')).toBe(true);
    expect(screen.queryByText('Chọn nhanh nhu cầu chuyến đi')).toBeNull();
    expect(global.fetch).not.toHaveBeenCalled();
    expect(mocks.sendMessage).not.toHaveBeenCalled();
  });

  it('prefills a suggestion for editing before sending and switches to the transcript', () => {
    const view = open();
    fireEvent.click(screen.getByRole('button', { name: 'Gia đình' }));
    const input = screen.getByRole('textbox') as HTMLTextAreaElement;
    expect(input.value).toContain('gia đình');
    expect(mocks.sendMessage).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: 'Đi Hội An\n2 người, 3 ngày' } });
    fireEvent.submit(screen.getByRole('form', { name: 'Gửi yêu cầu du lịch' }));
    expect(mocks.sendMessage).toHaveBeenCalledWith('Đi Hội An\n2 người, 3 ngày');
    mocks.state = { ...mocks.state, phase: 'connecting', transcript: [{
      id: 'user-1', sender: 'user', text: 'Đi Hội An\n2 người, 3 ngày', createdAt: Date.now(),
    }] };
    view.rerender(<AiFloatingWidget />);
    expect(screen.queryByRole('heading', { name: 'Bạn muốn đi đâu tiếp theo?' })).toBeNull();
    expect(screen.getAllByRole('textbox')).toHaveLength(1);
    // Đang chạy: nút gửi thành nút Dừng ngay trong ô nhập; tiến trình là 3 bước, không có chuỗi debug của backend.
    expect(screen.queryByRole('button', { name: 'Gửi yêu cầu' })).toBeNull();
    expect(screen.getByRole('status').textContent).toBe('Đang hiểu yêu cầu của bạn…');
    fireEvent.click(screen.getByRole('button', { name: 'Dừng xử lý' }));
    expect(mocks.abort).toHaveBeenCalledOnce();
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Escape' });
    expect(mocks.abort).toHaveBeenCalledTimes(2);
    expect(screen.getByRole('textbox')).toBeTruthy();
  });

  it('offers to resend after the user stops a request', () => {
    const view = open();
    mocks.state = { ...mocks.state, phase: 'aborted', lastRequest: {
      message: 'Đi Hội An 3 ngày', conversationId: null, intentOverride: null, context: { language: 'vi' },
    }, transcript: [{ id: 'user-1', sender: 'user', text: 'Đi Hội An 3 ngày', createdAt: Date.now() }] };
    view.rerender(<AiFloatingWidget />);
    expect(screen.getByText('Đã dừng. Trợ lý chưa trả lời tin nhắn này.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Dừng xử lý' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Gửi lại' }));
    expect(mocks.retry).toHaveBeenCalledOnce();
  });

  it('loads real destination options only when the optional form is opened', async () => {
    open();
    const details = screen.getByRole('button', { name: 'Thêm thông tin chuyến đi' });
    fireEvent.click(details);
    expect(details.getAttribute('aria-expanded')).toBe('true');
    await screen.findByRole('button', { name: 'Hội An' });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo lịch trình' }));
    expect(mocks.sendMessage).toHaveBeenCalledWith('Tôi chọn đi Hội An trong 3 ngày cho gia đình có trẻ nhỏ, ưu tiên nghỉ dưỡng sang trọng.');
  });

  it('keeps an entry-point draft when expanded and when closed then reopened', () => {
    mocks.state.floatingInitialMessage = 'Đi Hội An 3 ngày';
    open();
    expect(mocks.consumeFloatingInitialMessage).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Mở rộng toàn màn hình' }));
    expect((screen.getByRole('textbox') as HTMLTextAreaElement).value).toBe('Đi Hội An 3 ngày');
    fireEvent.click(screen.getByRole('button', { name: 'Đóng' }));
    fireEvent.click(screen.getByRole('button', { name: 'Mở trợ lý du lịch AI' }));
    expect((screen.getByRole('textbox') as HTMLTextAreaElement).value).toBe('Đi Hội An 3 ngày');
  });

  it('clears the draft and restores the opening for a new conversation', () => {
    const view = open();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Bản nháp' } });
    fireEvent.click(screen.getByRole('button', { name: 'Danh sách hội thoại & Tạo chat mới' }));
    fireEvent.click(screen.getByRole('button', { name: 'Đoạn chat mới' }));
    expect(mocks.resetConversation).toHaveBeenCalledOnce();
    view.rerender(<AiFloatingWidget />);
    expect((screen.getByRole('textbox') as HTMLTextAreaElement).value).toBe('');
    expect(screen.getByRole('heading', { name: 'Bạn muốn đi đâu tiếp theo?' })).toBeTruthy();
  });

  it('opens the actual saved conversation and reports load failures', async () => {
    mocks.state.conversationId = 'saved-1';
    mocks.state.transcript = [{ id: 'user-1', sender: 'user', text: 'Đi Hội An', createdAt: Date.now() }];
    const view = open();
    fireEvent.click(screen.getByRole('button', { name: 'Danh sách hội thoại & Tạo chat mới' }));
    fireEvent.click(screen.getByRole('button', { name: 'Đoạn chat mới' }));
    mocks.state = { ...createInitialAssistantState(), isHydrated: true };
    view.rerender(<AiFloatingWidget />);
    fireEvent.click(screen.getByRole('button', { name: 'Danh sách hội thoại & Tạo chat mới' }));
    mocks.loadConversation.mockRejectedValueOnce(new Error('Unavailable'));
    fireEvent.click(screen.getByRole('button', { name: 'Mở hội thoại Đi Hội An' }));
    await waitFor(() => expect(mocks.showToast).toHaveBeenCalledWith('Không thể mở lại hội thoại. Vui lòng thử lại.'));
    expect(mocks.loadConversation).toHaveBeenCalledWith('saved-1');
  });

  it('preserves retry for errors instead of sending a duplicate request', () => {
    mocks.state.phase = 'failed';
    mocks.state.error = { code: 'NETWORK_ERROR', message: 'Chưa kết nối được', retryable: true };
    mocks.state.transcript = [{ id: 'user-1', sender: 'user', text: 'Đi Hội An', createdAt: Date.now() }];
    open();
    expect(screen.getByRole('alert').textContent).toContain('Chưa kết nối được');
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    expect(mocks.retry).toHaveBeenCalledOnce();
    expect(mocks.sendMessage).not.toHaveBeenCalled();
  });

  it('shows no-results suggestions as chips on the latest message and sends the tapped one', () => {
    const response = { status: 'NO_RESULTS' as const, conversationId: 'c1', message: 'Hiện chưa có sản phẩm.',
      suggestions: ['Đi Hà Nội 3 ngày từ ngày 24/10/2026', 'Đi Huế 3 ngày'] };
    mocks.state = { ...mocks.state, phase: 'no_results', response, transcript: [
      { id: 'user-1', sender: 'user', text: 'Hà Nội 3 ngày', createdAt: 1 },
      { id: 'assistant-1', sender: 'assistant', text: response.message, response, createdAt: 2 },
    ] };
    open();
    expect(screen.getAllByText('Hiện chưa có sản phẩm.')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Đi Hà Nội 3 ngày từ ngày 24/10/2026' }));
    expect(mocks.sendMessage).toHaveBeenCalledWith('Đi Hà Nội 3 ngày từ ngày 24/10/2026');
  });

  it('shows chips when a required hotel has no product and explains why', () => {
    const question = '**Khách sạn ở Hà Nội chưa mở bán cho ngày đi**\nMình tìm thấy 10 khách sạn ở Hà Nội.';
    const response = { status: 'NEEDS_CLARIFICATION' as const, conversationId: 'c1', question,
      suggestions: ['Đổi ngày khởi hành sang 15/10/2026', 'Đi Hà Nội 3 ngày, không cần khách sạn'] };
    mocks.state = { ...mocks.state, phase: 'needs_clarification', response, transcript: [
      { id: 'user-1', sender: 'user', text: 'không có hotel à', createdAt: 1 },
      { id: 'assistant-1', sender: 'assistant', text: question, response, createdAt: 2 },
    ] };
    open();
    fireEvent.click(screen.getByRole('button', { name: 'Đi Hà Nội 3 ngày, không cần khách sạn' }));
    expect(mocks.sendMessage).toHaveBeenCalledWith('Đi Hà Nội 3 ngày, không cần khách sạn');
  });

  it('drops the chips once a later message exists', () => {
    const response = { status: 'NO_RESULTS' as const, conversationId: 'c1', message: 'Hiện chưa có sản phẩm.',
      suggestions: ['Đi Huế 3 ngày'] };
    mocks.state = { ...mocks.state, transcript: [
      { id: 'assistant-1', sender: 'assistant', text: response.message, response, createdAt: 1 },
      { id: 'user-2', sender: 'user', text: 'Đi Huế 3 ngày', createdAt: 2 },
    ] };
    open();
    expect(screen.queryByRole('button', { name: 'Đi Huế 3 ngày' })).toBeNull();
  });
});
