import type { components } from '../types/api.gen';

export type AssistantResponse = components['schemas']['ItineraryResponse'];

const VALID_STATUSES = new Set(['COMPLETED', 'NEEDS_CLARIFICATION', 'NO_RESULTS', 'FALLBACK']);

export function encodeAssistantResponse(response: AssistantResponse): string {
  const encoded = btoa(encodeURIComponent(JSON.stringify(response)));
  return encoded.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function decodeAssistantResponse(encoded: string): AssistantResponse | null {
  try {
    const base64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=');
    const value: unknown = JSON.parse(decodeURIComponent(atob(padded)));
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;

    const response = value as Record<string, unknown>;
    if (!VALID_STATUSES.has(String(response.status)) || typeof response.conversationId !== 'string') return null;
    if (response.status === 'COMPLETED' && (!response.itinerary || typeof response.itinerary !== 'object')) return null;
    if (response.status === 'NEEDS_CLARIFICATION' && typeof response.question !== 'string') return null;
    if ((response.status === 'NO_RESULTS' || response.status === 'FALLBACK') && typeof response.message !== 'string') return null;
    if (response.status === 'FALLBACK' && (!response.searchResults || typeof response.searchResults !== 'object')) return null;
    return response as AssistantResponse;
  } catch {
    return null;
  }
}

export function createAssistantShareUrl(response: AssistantResponse, origin: string) {
  const parameters = new URLSearchParams({ share: 'client', data: encodeAssistantResponse(response) });
  return `${origin}/assistant?${parameters.toString()}`;
}
