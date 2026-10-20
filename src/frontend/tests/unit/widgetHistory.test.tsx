// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AiFloatingWidget } from '../../src/components/assistant/AiFloatingWidget';
import { createInitialAssistantState, type AssistantState } from '../../src/context/assistantState';

const mocks = vi.hoisted(() => ({
  state: {} as AssistantState,
  persona: null as { id: string } | null,
  sendMessage: vi.fn(), resetConversation: vi.fn(), loadConversation: vi.fn(),
  consumeFloatingInitialMessage: vi.fn(), retry: vi.fn(), abort: vi.fn(), showToast: vi.fn(),
  listAssistantConversations: vi.fn(),
}));

vi.mock('next/image', () => ({ default: () => null }));
vi.mock('next/dynamic', () => ({ default: () => () => null }));
vi.mock('../../src/context/AssistantProvider', () => ({
  useAssistant: () => ({ state: mocks.state, ...mocks }),
}));
vi.mock('../../src/context/TravelContext', () => ({
  useTravel: () => ({
    currentRoute: '/', currentPersona: mocks.persona, showToast: mocks.showToast, navigate: vi.fn(), addToCart: vi.fn(),
  }),
}));
vi.mock('../../src/hooks/useAssistantCart', () => ({ useAssistantCart: () => vi.fn(), useBookItinerary: () => vi.fn() }));
vi.mock('../../src/services/assistantHistory', () => ({
  listAssistantConversations: mocks.listAssistantConversations,
}));

const summary = (conversationId: string, title: string, updatedAt: string) => ({
  conversationId, title, status: 'open', createdAt: updatedAt, updatedAt, messageCount: 2,
});

function openHistory() {
  render(<AiFloatingWidget />);
  fireEvent.click(screen.getByRole('button', { name: 'Mở trợ lý du lịch AI' }));
  fireEvent.click(screen.getByRole('button', { name: 'Danh sách hội thoại & Tạo chat mới' }));
}

describe('assistant widget history (FR-AGT-01)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.state = { ...createInitialAssistantState(), isHydrated: true };
    mocks.persona = { id: 'user-1' };
    mocks.loadConversation.mockResolvedValue(undefined);
    Element.prototype.scrollTo = vi.fn();
  });
  afterEach(() => { cleanup(); });

  it('lists the signed-in user\'s conversations from the backend, newest first', async () => {
    mocks.listAssistantConversations.mockResolvedValue({
      data: [summary('c-2', 'Đi Hội An 3 ngày', '2026-10-07T04:00:00Z'), summary('c-1', 'Đà Lạt cuối tuần', '2026-10-06T04:00:00Z')],
      pagination: { page: 1, pageSize: 20, totalItems: 2, totalPages: 1 },
    });
    openHistory();
    const items = await screen.findAllByRole('button', { name: /^Mở hội thoại / });
    expect(items.map((item) => item.getAttribute('aria-label'))).toEqual([
      'Mở hội thoại Đi Hội An 3 ngày', 'Mở hội thoại Đà Lạt cuối tuần',
    ]);
    expect(mocks.listAssistantConversations).toHaveBeenCalledWith(1, 20);
    expect(screen.queryByRole('button', { name: /^Xóa hội thoại/ })).toBeNull();
  });

  it('reopens a past conversation through the archive', async () => {
    mocks.listAssistantConversations.mockResolvedValue({
      data: [summary('c-1', 'Đà Lạt cuối tuần', '2026-10-06T04:00:00Z')],
      pagination: { page: 1, pageSize: 20, totalItems: 1, totalPages: 1 },
    });
    openHistory();
    fireEvent.click(await screen.findByRole('button', { name: 'Mở hội thoại Đà Lạt cuối tuần' }));
    await waitFor(() => expect(mocks.loadConversation).toHaveBeenCalledWith('c-1'));
    await waitFor(() => expect(screen.queryByText('Lịch sử trò chuyện')).toBeNull());
  });

  it('reports a conversation that cannot be reopened and keeps the panel open', async () => {
    mocks.listAssistantConversations.mockResolvedValue({
      data: [summary('saved-1', 'Đi Hội An', '2026-10-06T04:00:00Z')],
      pagination: { page: 1, pageSize: 20, totalItems: 1, totalPages: 1 },
    });
    mocks.loadConversation.mockRejectedValueOnce(new Error('Unavailable'));
    openHistory();
    fireEvent.click(await screen.findByRole('button', { name: 'Mở hội thoại Đi Hội An' }));
    await waitFor(() => expect(mocks.showToast).toHaveBeenCalledWith('Không thể mở lại hội thoại. Vui lòng thử lại.'));
    expect(mocks.loadConversation).toHaveBeenCalledWith('saved-1');
    expect(screen.getByText('Lịch sử trò chuyện')).toBeTruthy();
  });

  it('keeps the active chat on top while the archive has not caught up', async () => {
    mocks.state = { ...mocks.state, conversationId: 'c-new', transcript: [
      { id: 'u-1', sender: 'user', text: 'Phú Quốc 4 ngày cho 2 người', createdAt: Date.now() },
    ] };
    mocks.listAssistantConversations.mockResolvedValue({
      data: [summary('c-1', 'Đà Lạt cuối tuần', '2026-10-06T04:00:00Z')],
      pagination: { page: 1, pageSize: 20, totalItems: 1, totalPages: 1 },
    });
    openHistory();
    await screen.findByRole('button', { name: 'Mở hội thoại Đà Lạt cuối tuần' });
    const items = screen.getAllByRole('button', { name: /^Mở hội thoại / });
    expect(items[0].getAttribute('aria-label')).toBe('Mở hội thoại Phú Quốc 4 ngày cho 2 người');
    fireEvent.click(items[0]);
    expect(mocks.loadConversation).not.toHaveBeenCalled();
  });

  it('while the archive loads, shows skeleton conversation rows; the real list replaces them', async () => {
    let answer!: (value: unknown) => void;
    mocks.listAssistantConversations.mockReturnValue(new Promise((resolve) => { answer = resolve; }));
    openHistory();
    const skeleton = await screen.findByRole('status', { name: 'Đang tải lịch sử…' });
    expect(skeleton.querySelectorAll(':scope > div')).toHaveLength(4);
    expect(screen.queryByText('Chưa có lịch sử hội thoại nào')).toBeNull();

    answer({
      data: [summary('c-1', 'Đà Lạt cuối tuần', '2026-10-06T04:00:00Z')],
      pagination: { page: 1, pageSize: 20, totalItems: 1, totalPages: 1 },
    });
    expect(await screen.findByRole('button', { name: 'Mở hội thoại Đà Lạt cuối tuần' })).toBeTruthy();
    expect(screen.queryByRole('status', { name: 'Đang tải lịch sử…' })).toBeNull();
  });

  it('an empty archive ends on the empty message, not on the skeleton', async () => {
    mocks.listAssistantConversations.mockResolvedValue({ data: [], pagination: { page: 1, pageSize: 20, totalItems: 0, totalPages: 0 } });
    openHistory();
    expect(await screen.findByText('Chưa có lịch sử hội thoại nào')).toBeTruthy();
    expect(screen.queryByRole('status', { name: 'Đang tải lịch sử…' })).toBeNull();
  });

  it('does not call the archive for guests and asks them to sign in', () => {
    mocks.persona = null;
    openHistory();
    expect(mocks.listAssistantConversations).not.toHaveBeenCalled();
    expect(screen.getByText('Đăng nhập để lưu và xem lại lịch sử hội thoại.')).toBeTruthy();
  });

  it('shows an error with retry when the list fails', async () => {
    mocks.listAssistantConversations.mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce({
      data: [summary('c-1', 'Đà Lạt cuối tuần', '2026-10-06T04:00:00Z')],
      pagination: { page: 1, pageSize: 20, totalItems: 1, totalPages: 1 },
    });
    openHistory();
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại' }));
    expect(await screen.findByRole('button', { name: 'Mở hội thoại Đà Lạt cuối tuần' })).toBeTruthy();
    expect(mocks.listAssistantConversations).toHaveBeenCalledTimes(2);
  });
});
