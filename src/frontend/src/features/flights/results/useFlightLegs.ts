'use client';

import { useEffect, useState } from 'react';
import { loadSection } from '../../../hooks/useLazySection';
import type { ProductSummary } from '../../../services/catalog';
import { listRouteFlights, listRoutesTo } from '../../../services/flights';
import {
  flightOptionsFromVariants, matchRoute, originChoices, routeOriginCity,
  type FlightOption, type OriginChoice,
} from './flightModel';

/** Một chặng: tuyến (tầng cha) và các hành trình một chiều của nó. */
export interface LegData {
  route: ProductSummary;
  options: FlightOption[];
}

export type OutboundState =
  | { status: 'loading' }
  | { status: 'error'; error: Error }
  | { status: 'no-route'; choices: OriginChoice[] }
  | { status: 'ready'; leg: LegData };

export type ReturnState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'none' }
  | { status: 'error'; error: Error }
  | { status: 'ready'; leg: LegData };

const asError = (error: unknown): Error => (error instanceof Error ? error : new Error('Không tải được chuyến bay.'));

const routesTo = (destination: string) => loadSection(`flights:routes:${destination}`, (signal) => listRoutesTo(destination, signal));

async function loadLeg(route: ProductSummary): Promise<LegData> {
  const variants = await loadSection(`flights:legs:${route.productId}`, (signal) => listRouteFlights(route.productId, signal));
  return { route, options: flightOptionsFromVariants(variants) };
}

/** Chặng đi: tuyến khớp điểm đi + điểm đến, rồi các chuyến của tuyến. Cả hai lời gọi đi qua bộ đệm 60 giây. */
export function useOutboundLeg(origin: string, destination: string, retryToken: number): OutboundState {
  const [state, setState] = useState<OutboundState>({ status: 'loading' });
  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading' });
    (async () => {
      const routes = await routesTo(destination);
      const route = matchRoute(routes, origin);
      if (!route) return { status: 'no-route', choices: originChoices(routes) } as const;
      return { status: 'ready', leg: await loadLeg(route) } as const;
    })()
      .then((next) => { if (!cancelled) setState(next); })
      .catch((error) => { if (!cancelled) setState({ status: 'error', error: asError(error) }); });
    return () => { cancelled = true; };
  }, [origin, destination, retryToken]);
  return state;
}

/**
 * Chặng về: tuyến ngược của chặng đi (điểm đi ↔ điểm đến). Chỉ tải khi `enabled` (khách chọn khứ hồi).
 * Không có tuyến ngược trong catalog thì `none`: khách vẫn đặt được vé một chiều.
 */
export function useReturnLeg(outbound: ProductSummary | null, enabled: boolean, retryToken: number): ReturnState {
  const [state, setState] = useState<ReturnState>({ status: 'idle' });
  const outboundId = outbound?.productId ?? null;
  useEffect(() => {
    if (!enabled || !outbound) {
      setState({ status: 'idle' });
      return;
    }
    let cancelled = false;
    setState({ status: 'loading' });
    (async () => {
      const routes = await routesTo(routeOriginCity(outbound));
      const route = matchRoute(routes, outbound.destination);
      return route ? ({ status: 'ready', leg: await loadLeg(route) } as const) : ({ status: 'none' } as const);
    })()
      .then((next) => { if (!cancelled) setState(next); })
      .catch((error) => { if (!cancelled) setState({ status: 'error', error: asError(error) }); });
    return () => { cancelled = true; };
    // `outbound` được xác định bởi productId của nó.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, outboundId, retryToken]);
  return state;
}
