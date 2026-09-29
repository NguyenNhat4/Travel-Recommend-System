import type { components } from '../types/api.gen';
import { apiJson } from './http';

export type AssistantConversationList = components['schemas']['AssistantConversationList'];
export type AssistantConversationDetail = components['schemas']['AssistantConversationDetail'];

export function listAssistantConversations(page = 1, pageSize = 20) {
  const query = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
  return apiJson<AssistantConversationList>(`/api/v1/assistant/conversations?${query}`, {
    cache: 'no-store',
  });
}

export function getAssistantConversation(conversationId: string) {
  return apiJson<AssistantConversationDetail>(
    `/api/v1/assistant/conversations/${encodeURIComponent(conversationId)}`,
    { cache: 'no-store' },
  );
}
