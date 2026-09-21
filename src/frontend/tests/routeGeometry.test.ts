import { describe, expect, it } from 'vitest';
import {
  buildRouteRequests,
  normalizeGeoJsonCoordinates,
  MultimodalRouteProvider,
  OsrmRouteProvider,
  resolveRouteRequests,
} from '../src/services/routeGeometry';
import { GroundedPlan } from '../src/types/travel';
import osrmFixture from './fixtures/route-geometry.osrm.json';

describe('route geometry helpers', () => {
  it('normalizes GeoJSON coordinates from [lng, lat] to Leaflet coordinates', () => {
    expect(normalizeGeoJsonCoordinates([
      [109.197, 12.2472],
      [109.198, 12.2482],
    ])).toEqual([
      { lat: 12.2472, lng: 109.197 },
      { lat: 12.2482, lng: 109.198 },
    ]);
  });

  it('builds daily segments in stay-to-stop order and returns to the active stay', () => {
    const plan = makePlan({
      stay: {
        productId: 'hotel-a',
        product: product('hotel-a', 12.2, 109.2),
        note: '',
        source: 'search',
      },
      days: [{
        day: 1,
        title: 'Ngày 1',
        slots: [
          slot('morning', 'stop-a', 12.21, 109.21),
          slot('noon', 'stop-b', 12.22, 109.22),
        ],
      }],
    });

    expect(buildRouteRequests(plan, 1).map(({ fromPointId, toPointId }) => [fromPointId, toPointId])).toEqual([
      ['stay-hotel-a', 'day-1-slot-morning-1'],
      ['day-1-slot-morning-1', 'day-1-slot-noon-2'],
      ['day-1-slot-noon-2', 'stay-hotel-a'],
    ]);
  });

  it('keeps route point ids contiguous when an earlier slot has no coordinates', () => {
    const plan = makePlan({
      stay: {
        productId: 'hotel-a',
        product: product('hotel-a', 12.2, 109.2),
        note: '',
        source: 'search',
      },
      days: [{
        day: 1,
        title: 'Ngày 1',
        slots: [
          { time: 'morning', note: 'missing coordinates' },
          slot('noon', 'stop-b', 12.22, 109.22),
        ],
      }],
    });

    expect(buildRouteRequests(plan, 1)[0].toPointId).toBe('day-1-slot-noon-1');
  });

  it('uses the correct stay for each day in a multi-hotel plan', () => {
    const plan = makePlan({
      stays: [
        { productId: 'hotel-a', product: product('hotel-a', 12.2, 109.2), nights: 1 },
        { productId: 'hotel-b', product: product('hotel-b', 12.3, 109.3), nights: 1 },
      ],
      days: [
        { day: 1, title: 'Ngày 1', slots: [slot('morning', 'stop-a', 12.21, 109.21)] },
        { day: 2, title: 'Ngày 2', slots: [slot('morning', 'stop-b', 12.31, 109.31)] },
      ],
    });

    expect(buildRouteRequests(plan, 1)[0].fromPointId).toBe('stay-hotel-a');
    expect(buildRouteRequests(plan, 2)[0].fromPointId).toBe('stay-hotel-b');
  });

  it('requests an OSRM driving route and preserves GeoJSON geometry plus metrics', async () => {
    let requestUrl = '';
    let requestInit: RequestInit | undefined;
    const provider = new OsrmRouteProvider('https://osrm.test', async (input, init) => {
      requestUrl = String(input);
      requestInit = init;
      return {
        ok: true,
        status: 200,
        json: async () => osrmFixture,
      } as Response;
    }, 0);

    const result = await provider.getRoute({
      id: 'segment-1',
      fromPointId: 'from',
      toPointId: 'to',
      from: { lat: 12.2, lng: 109.2 },
      to: { lat: 12.21, lng: 109.21 },
      fromTitle: 'From',
      toTitle: 'To',
      mode: 'driving',
    });

    expect(result.status).toBe('routed');
    expect(result.geometry).toHaveLength(3);
    expect(result.geometry[1]).toEqual({ lat: 12.202, lng: 109.205 });
    expect(result.distanceMeters).toBe(1234);
    expect(result.durationSeconds).toBe(456);
    expect(result.maneuvers).toBeUndefined();
    const parsedUrl = new URL(requestUrl);
    expect(parsedUrl.pathname).toBe('/routed-car/route/v1/driving/109.2,12.2;109.21,12.21');
    expect(parsedUrl.searchParams.get('overview')).toBe('full');
    expect(parsedUrl.searchParams.get('geometries')).toBe('geojson');
    expect(parsedUrl.searchParams.get('steps')).toBe('false');
    expect(requestInit?.method).toBe('GET');
    expect(requestInit?.body).toBeUndefined();
  });

  it('calls the injected fetch implementation with the global receiver', async () => {
    let observedThis: unknown;
    const fetchImpl = function (this: unknown) {
      observedThis = this;
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => osrmFixture,
      } as Response);
    } as typeof fetch;
    const provider = new OsrmRouteProvider('https://osrm-receiver.test', fetchImpl, 0);

    const result = await provider.getRoute({
      id: 'segment-receiver',
      fromPointId: 'from',
      toPointId: 'to',
      from: { lat: 12.2, lng: 109.2 },
      to: { lat: 12.21, lng: 109.21 },
      fromTitle: 'From',
      toTitle: 'To',
      mode: 'driving',
    });

    expect(result.status).toBe('routed');
    expect(observedThis).toBe(globalThis);
  });

  it.each([
    ['driving', 'routed-car'],
    ['walking', 'routed-foot'],
    ['bicycle', 'routed-bike'],
  ] as const)('maps %s to the OSRM %s public profile', async (mode, profile) => {
    let requestUrl = '';
    const provider = new OsrmRouteProvider(`https://osrm-${mode}.test`, async (input) => {
      requestUrl = String(input);
      return { ok: true, status: 200, json: async () => osrmFixture } as Response;
    }, 0);

    const result = await provider.getRoute({
      id: `segment-${mode}`,
      fromPointId: 'from',
      toPointId: 'to',
      from: { lat: 12.2, lng: 109.2 },
      to: { lat: 12.21, lng: 109.21 },
      fromTitle: 'From',
      toTitle: 'To',
      mode,
    });

    expect(result.status).toBe('routed');
    expect(new URL(requestUrl).pathname).toContain(`/${profile}/route/v1/driving/`);
  });

  it('caches identical OSRM requests without calling the public server twice', async () => {
    let callCount = 0;
    const provider = new OsrmRouteProvider('https://osrm-cache.test', async () => {
      callCount += 1;
      return { ok: true, status: 200, json: async () => osrmFixture } as Response;
    }, 0);
    const request = {
      id: 'segment-cache',
      fromPointId: 'from',
      toPointId: 'to',
      from: { lat: 12.2, lng: 109.2 },
      to: { lat: 12.21, lng: 109.21 },
      fromTitle: 'From',
      toTitle: 'To',
      mode: 'driving' as const,
    };

    await provider.getRoute(request);
    await provider.getRoute({ ...request, id: 'segment-cache-again' });

    expect(callCount).toBe(1);
  });

  it('coalesces concurrent identical OSRM requests and preserves each request id', async () => {
    let callCount = 0;
    let releaseResponse!: (response: Response) => void;
    const provider = new OsrmRouteProvider('https://osrm-inflight.test', async () => {
      callCount += 1;
      return new Promise<Response>((resolve) => {
        releaseResponse = resolve;
      });
    }, 0);
    const request = {
      id: 'segment-inflight-1',
      fromPointId: 'from',
      toPointId: 'to',
      from: { lat: 12.2, lng: 109.2 },
      to: { lat: 12.21, lng: 109.21 },
      fromTitle: 'From',
      toTitle: 'To',
      mode: 'driving' as const,
    };

    const first = provider.getRoute(request);
    const second = provider.getRoute({ ...request, id: 'segment-inflight-2' });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(callCount).toBe(1);

    releaseResponse({ ok: true, status: 200, json: async () => osrmFixture } as Response);
    const [firstResult, secondResult] = await Promise.all([first, second]);
    expect(firstResult.status).toBe('routed');
    expect(secondResult.status).toBe('routed');
    expect(firstResult.id).toBe('segment-inflight-1');
    expect(secondResult.id).toBe('segment-inflight-2');
  });

  it('serializes cache misses with the configured minimum interval', async () => {
    const startedAt: number[] = [];
    const provider = new OsrmRouteProvider('https://osrm-throttle.test', async () => {
      startedAt.push(Date.now());
      return { ok: true, status: 200, json: async () => osrmFixture } as Response;
    }, 25);
    const request = (id: string, offset: number) => ({
      id,
      fromPointId: 'from',
      toPointId: 'to',
      from: { lat: 12.2 + offset, lng: 109.2 },
      to: { lat: 12.21 + offset, lng: 109.21 },
      fromTitle: 'From',
      toTitle: 'To',
      mode: 'driving' as const,
    });

    await Promise.all([
      provider.getRoute(request('segment-throttle-1', 0)),
      provider.getRoute(request('segment-throttle-2', 0.001)),
    ]);

    expect(startedAt).toHaveLength(2);
    expect(startedAt[1] - startedAt[0]).toBeGreaterThanOrEqual(20);
  });

  it('marks HTTP, NoRoute, and malformed geometry responses unavailable', async () => {
    const responses = [
      { ok: false, status: 503, json: async () => ({}) },
      { ok: true, status: 200, json: async () => ({ code: 'NoRoute', routes: [] }) },
      { ok: true, status: 200, json: async () => ({ code: 'Ok', routes: [{ distance: 1, duration: 2, geometry: { coordinates: [[109.2, 12.2]] } }] }) },
    ];

    for (const [index, response] of responses.entries()) {
      const provider = new OsrmRouteProvider(`https://osrm-error-${index}.test`, async () => response as Response, 0);
      const result = await provider.getRoute({
        id: `segment-error-${index}`,
        fromPointId: 'from',
        toPointId: 'to',
        from: { lat: 12.2, lng: 109.2 },
        to: { lat: 12.21, lng: 109.21 },
        fromTitle: 'From',
        toTitle: 'To',
        mode: 'driving',
      });

      expect(result.status).toBe('unavailable');
      expect(result.geometry).toEqual([]);
    }
  });

  it('marks network and malformed JSON failures unavailable', async () => {
    const request = {
      id: 'segment-payload-error',
      fromPointId: 'from',
      toPointId: 'to',
      from: { lat: 12.2, lng: 109.2 },
      to: { lat: 12.21, lng: 109.21 },
      fromTitle: 'From',
      toTitle: 'To',
      mode: 'driving' as const,
    };

    const malformedProvider = new OsrmRouteProvider('https://osrm-malformed.test', async () => ({
      ok: true,
      status: 200,
      json: async () => { throw new Error('invalid json'); },
    } as unknown as Response), 0);
    const networkProvider = new OsrmRouteProvider('https://osrm-network.test', async () => {
      throw new Error('network down');
    }, 0);

    await expect(malformedProvider.getRoute(request)).resolves.toMatchObject({ status: 'unavailable', geometry: [] });
    await expect(networkProvider.getRoute(request)).resolves.toMatchObject({ status: 'unavailable', geometry: [] });
  });

  it('marks unsupported transit modes unavailable instead of calling OSRM', async () => {
    let called = false;
    const provider = new OsrmRouteProvider('https://osrm.test', async () => {
      called = true;
      return {} as Response;
    }, 0);

    const result = await provider.getRoute({
      id: 'segment-boat',
      fromPointId: 'from',
      toPointId: 'to',
      from: { lat: 12.2, lng: 109.2 },
      to: { lat: 12.21, lng: 109.21 },
      fromTitle: 'From',
      toTitle: 'To',
      mode: 'ferry',
    });

    expect(called).toBe(false);
    expect(result.status).toBe('unavailable');
    expect(result.geometry).toEqual([]);
  });

  it('emits each resolved route result while resolving a batch', async () => {
    const provider = new OsrmRouteProvider('https://osrm-progress.test', async () => (
      { ok: true, status: 200, json: async () => osrmFixture } as Response
    ), 0);
    const request = (id: string, offset: number) => ({
      id,
      fromPointId: 'from',
      toPointId: 'to',
      from: { lat: 12.2 + offset, lng: 109.2 },
      to: { lat: 12.21 + offset, lng: 109.21 },
      fromTitle: 'From',
      toTitle: 'To',
      mode: 'driving' as const,
    });
    const emitted: string[] = [];

    const results = await resolveRouteRequests(
      [request('segment-progress-1', 0), request('segment-progress-2', 0.001)],
      provider,
      (result) => emitted.push(result.id),
    );

    expect(results).toHaveLength(2);
    expect(emitted).toHaveLength(2);
    expect(emitted).toEqual(expect.arrayContaining(['segment-progress-1', 'segment-progress-2']));
  });

  it('draws curved routes for ferry, cable, and flight via MultimodalRouteProvider', async () => {
    let roadCalls = 0;
    const mockRoadProvider = {
      getRoute: async () => {
        roadCalls += 1;
        return {
          id: 'road',
          fromPointId: 'from',
          toPointId: 'to',
          from: { lat: 12.2, lng: 109.2 },
          to: { lat: 12.21, lng: 109.21 },
          fromTitle: 'From',
          toTitle: 'To',
          mode: 'driving' as const,
          status: 'routed' as const,
          geometry: [{ lat: 12.2, lng: 109.2 }, { lat: 12.21, lng: 109.21 }],
        };
      },
    };

    const multimodal = new MultimodalRouteProvider(mockRoadProvider);

    for (const mode of ['ferry', 'cable', 'flight'] as const) {
      const result = await multimodal.getRoute({
        id: `segment-${mode}`,
        fromPointId: 'from',
        toPointId: 'to',
        from: { lat: 12.2, lng: 109.2 },
        to: { lat: 12.21, lng: 109.21 },
        fromTitle: 'From',
        toTitle: 'To',
        mode,
      });

      expect(result.status).toBe('routed');
      expect(result.geometry.length).toBeGreaterThanOrEqual(10);
      expect(result.distanceMeters).toBeGreaterThan(0);
    }
    expect(roadCalls).toBe(0);

    const drivingResult = await multimodal.getRoute({
      id: 'segment-car',
      fromPointId: 'from',
      toPointId: 'to',
      from: { lat: 12.2, lng: 109.2 },
      to: { lat: 12.21, lng: 109.21 },
      fromTitle: 'From',
      toTitle: 'To',
      mode: 'driving',
    });

    expect(drivingResult.status).toBe('routed');
    expect(drivingResult.geometry.length).toBe(2);
    expect(roadCalls).toBe(1);
  });
});

function product(id: string, lat: number, lng: number) {
  return {
    id,
    name: id,
    taxonomy: 'hotel' as const,
    destination: 'Nha Trang' as const,
    unitPrice: 1,
    currency: 'VND' as const,
    imageUrl: '',
    description: '',
    attributes: {},
    available: true,
    coordinates: { lat, lng },
  };
}

function slot(time: 'morning' | 'noon', id: string, lat: number, lng: number) {
  return {
    time,
    productId: id,
    note: id,
    coordinates: { lat, lng },
  };
}

function makePlan(overrides: Partial<GroundedPlan>): GroundedPlan {
  return {
    intent: {
      destination: 'Nha Trang',
      days: 2,
      party: 'solo',
      interests: [],
    },
    title: 'Test plan',
    days: [],
    totalEstimatedPrice: 0,
    bookableProductsCount: 0,
    ...overrides,
  };
}
