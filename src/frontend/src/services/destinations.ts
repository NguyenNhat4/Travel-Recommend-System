import type { components } from '../types/api.gen';
import { apiFetch } from './http';

export type DestinationOption = components['schemas']['DestinationListResponse']['destinations'][number];

function isDestinationOption(value: unknown): value is DestinationOption {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const option = value as Record<string, unknown>;
  return typeof option.destination === 'string'
    && option.destination.trim().length > 0
    && typeof option.productCount === 'number'
    && Number.isInteger(option.productCount)
    && option.productCount >= 0;
}

export async function listDestinations(signal?: AbortSignal): Promise<DestinationOption[]> {
  const response = await apiFetch('/api/v1/destinations', {
    method: 'GET',
    cache: 'no-store',
    signal,
  });
  if (!response.ok) throw new Error(`Destination API returned status: ${response.status}`);

  const payload: unknown = await response.json();
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Danh sách điểm đến không hợp lệ.');
  }
  const destinations = (payload as Record<string, unknown>).destinations;
  if (!Array.isArray(destinations) || !destinations.every(isDestinationOption)) {
    throw new Error('Danh sách điểm đến không hợp lệ.');
  }
  return destinations.map((option) => ({
    destination: option.destination.trim(),
    productCount: option.productCount,
  }));
}
