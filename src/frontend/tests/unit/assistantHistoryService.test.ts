import { afterEach, describe, expect, it, vi } from 'vitest';
import { getAssistantConversation, listAssistantConversations } from '../../src/services/assistantHistory';

describe('assistant history service', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('lists and loads conversations through the authenticated BFF', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ data: [], pagination: {
        page: 2, pageSize: 10, totalItems: 0, totalPages: 0,
      } }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({
        conversation: { conversationId: 'id', title: 'Trip', status: 'open', createdAt: 'x', updatedAt: 'x', messageCount: 0 },
        messages: [],
      }) });

    await listAssistantConversations(2, 10);
    await getAssistantConversation('id with spaces');

    expect(vi.mocked(global.fetch).mock.calls[0][0]).toBe('/api/v1/assistant/conversations?page=2&pageSize=10');
    expect(vi.mocked(global.fetch).mock.calls[1][0]).toBe('/api/v1/assistant/conversations/id%20with%20spaces');
    expect(vi.mocked(global.fetch).mock.calls[0][1]).toMatchObject({ credentials: 'same-origin', cache: 'no-store' });
  });
});
