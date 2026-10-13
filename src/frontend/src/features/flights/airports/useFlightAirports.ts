'use client';

import { listFlightAirports, type FlightAirport } from '../../../services/flights';
import { useLazySection } from '../../../hooks/useLazySection';

/**
 * Sân bay hiện hành của catalog (tuyến còn bán), dùng cho hai ô của `/flights`. Bộ đệm 5 phút; một request cho cả hai ô.
 */
export function useFlightAirports(enabled: boolean) {
  return useLazySection<FlightAirport[]>('flight-airports', (signal) => listFlightAirports(signal), { enabled, ttlMs: 5 * 60_000 });
}
