import { describe, expect, it } from 'vitest';
import { decodeAssistantResponse, encodeAssistantResponse } from '../../src/services/assistantShare';
import type { components } from '../../src/types/api.gen';

describe('assistant client share links', () => {
  it('round-trips an API response without deriving itinerary content', () => {
    const response: components['schemas']['ItineraryResponse'] = {
      status: 'NO_RESULTS',
      conversationId: 'backend-session',
      message: 'Backend chưa tìm được kết quả.',
      suggestions: ['Thử lại với ba ngày'],
    };
    expect(decodeAssistantResponse(encodeAssistantResponse(response))).toEqual(response);
  });

  it('rejects values that are not a valid backend response envelope', () => {
    expect(decodeAssistantResponse('not-encoded')).toBeNull();
    expect(decodeAssistantResponse(encodeAssistantResponse({ status: 'COMPLETED' } as components['schemas']['ItineraryResponse']))).toBeNull();
  });
});
