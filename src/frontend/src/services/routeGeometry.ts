import { Coordinates, GroundedPlan, ItinerarySlot, TransitMode } from '../types/travel';

export type RouteStatus = 'routed' | 'unavailable';

export interface RoutePoint {
  id: string;
  type: 'stay' | 'slot' | 'airport';
  coordinates: Coordinates;
  title: string;
  day?: number;
  transitMode?: TransitMode;
  transitInfo?: string;
  address?: string;
}

export interface RouteRequest {
  id: string;
  fromPointId: string;
  toPointId: string;
  from: Coordinates;
  to: Coordinates;
  fromTitle: string;
  toTitle: string;
  mode: TransitMode;
  transitInfo?: string;
}

export interface RouteResult extends RouteRequest {
  status: RouteStatus;
  geometry: Coordinates[];
  distanceMeters?: number;
  durationSeconds?: number;
  maneuvers?: RouteManeuver[];
  error?: string;
}

export interface RouteManeuver {
  instruction: string;
  lengthMeters?: number;
  durationSeconds?: number;
}

export interface RouteProvider {
  getRoute(request: RouteRequest): Promise<RouteResult>;
}

/** Convert GeoJSON [longitude, latitude] pairs into Leaflet-friendly points. */
export function normalizeGeoJsonCoordinates(value: unknown): Coordinates[] {
  if (!Array.isArray(value)) return [];

  return value.flatMap((coordinate) => {
    if (!Array.isArray(coordinate) || coordinate.length < 2) return [];
    const [lng, lat] = coordinate;
    if (typeof lng !== 'number' || typeof lat !== 'number' || !Number.isFinite(lng) || !Number.isFinite(lat)) {
      return [];
    }
    return [{ lat, lng }];
  });
}

function unavailable(request: RouteRequest, error: string): RouteResult {
  return {
    ...request,
    status: 'unavailable',
    geometry: [],
    error,
  };
}

function sameCoordinate(a: Coordinates, b: Coordinates): boolean {
  return Math.abs(a.lat - b.lat) < 0.00001 && Math.abs(a.lng - b.lng) < 0.00001;
}

function pointFromStay(stay: NonNullable<GroundedPlan['stays']>[number]): RoutePoint | null {
  if (!stay.product.coordinates) return null;
  return {
    id: `stay-${stay.productId}`,
    type: 'stay',
    coordinates: stay.product.coordinates,
    title: stay.product.name,
    address: stay.product.address,
  };
}

function pointFromSingleStay(plan: GroundedPlan): RoutePoint | null {
  if (!plan.stay?.product.coordinates) return null;
  return {
    id: `stay-${plan.stay.productId}`,
    type: 'stay',
    coordinates: plan.stay.product.coordinates,
    title: plan.stay.product.name,
    address: plan.stay.product.address,
  };
}

export function getStayPointForDay(plan: GroundedPlan, day: number): RoutePoint | null {
  const stays = plan.stays?.filter((stay) => stay.product.coordinates) ?? [];
  if (stays.length === 0) return pointFromSingleStay(plan);

  let elapsedNights = 0;
  let selectedStay = stays[stays.length - 1];

  for (const stay of stays) {
    const nights = Math.max(1, stay.nights);
    const startDay = elapsedNights + 1;
    const endDay = startDay + nights;
    if (day >= startDay && day <= endDay) selectedStay = stay;
    elapsedNights += nights;
  }

  return pointFromStay(selectedStay);
}

function pointFromSlot(slot: ItinerarySlot, day: number, order: number): RoutePoint | null {
  const coordinates = slot.coordinates ?? slot.product?.coordinates;
  if (!coordinates) return null;
  return {
    id: `day-${day}-slot-${slot.time}-${order}`,
    type: 'slot',
    coordinates,
    title: slot.product?.name ?? slot.activityTitle ?? slot.locationName ?? 'Điểm tham quan',
    day,
    transitMode: slot.transitMode,
    transitInfo: slot.transitInfo,
    address: slot.address ?? slot.product?.address,
  };
}

function coordinatesAt(attributes: Record<string, unknown> | undefined, latKey: string, lngKey: string): Coordinates | null {
  const lat = attributes?.[latKey];
  const lng = attributes?.[lngKey];
  if (typeof lat !== 'number' || typeof lng !== 'number' || !Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  return { lat, lng };
}

export interface AirportPoints {
  /** Sân bay đến ở điểm đến: chặng đi hoặc vé khứ hồi. */
  arrival: RoutePoint | null;
  /** Sân bay đi khi về: chặng về, hoặc chính sân bay đến với vé khứ hồi. */
  departure: RoutePoint | null;
}

/**
 * Sân bay của lịch trình, theo đúng luật backend tính km (`flights.airports`, AC-AGT-04, chốt 2026-10-09): catalog ghi sân
 * bay đến của chuyến ở `latitude`/`longitude` và sân bay đi ở `originLatitude`/`originLongitude`. Chỉ có một chiều thì dùng
 * sân bay đó cho cả hai đầu; không có chặng bay hoặc toạ độ thì không có sân bay.
 */
export function getAirportPoints(plan: GroundedPlan): AirportPoints {
  let arrival: { coordinates: Coordinates; code?: unknown } | null = null;
  let departure: { coordinates: Coordinates; code?: unknown } | null = null;
  for (const leg of plan.flights ?? []) {
    const attributes = leg.product.attributes as Record<string, unknown> | undefined;
    if (leg.direction === 'OUTBOUND' || leg.direction === 'ROUND_TRIP') {
      const coordinates = coordinatesAt(attributes, 'latitude', 'longitude');
      arrival = coordinates ? { coordinates, code: attributes?.destinationAirport } : null;
      if (leg.direction === 'ROUND_TRIP') departure = arrival;
    }
    if (leg.direction === 'RETURN') {
      const coordinates = coordinatesAt(attributes, 'originLatitude', 'originLongitude');
      departure = coordinates ? { coordinates, code: attributes?.originAirport } : null;
    }
  }
  const point = (id: string, found: { coordinates: Coordinates; code?: unknown } | null): RoutePoint | null => found && {
    id,
    type: 'airport',
    coordinates: found.coordinates,
    title: typeof found.code === 'string' && found.code ? `Sân bay ${found.code}` : 'Sân bay',
  };
  return { arrival: point('airport-arrival', arrival ?? departure), departure: point('airport-departure', departure ?? arrival) };
}

function isAirportPoint(point: RoutePoint): boolean {
  const text = `${point.title} ${point.address ?? ''}`.toLowerCase();
  return text.includes('sân bay') || text.includes('airport') || text.includes('cam ranh');
}

export function calculateHaversineDistanceMeters(a: Coordinates, b: Coordinates): number {
  const R = 6371e3;
  const phi1 = (a.lat * Math.PI) / 180;
  const phi2 = (b.lat * Math.PI) / 180;
  const deltaPhi = ((b.lat - a.lat) * Math.PI) / 180;
  const deltaLambda = ((b.lng - a.lng) * Math.PI) / 180;

  const sinPhi = Math.sin(deltaPhi / 2);
  const sinLambda = Math.sin(deltaLambda / 2);
  const val = sinPhi * sinPhi + Math.cos(phi1) * Math.cos(phi2) * sinLambda * sinLambda;
  return R * 2 * Math.atan2(Math.sqrt(val), Math.sqrt(1 - val));
}

export function estimateDurationSeconds(distanceMeters: number, mode: TransitMode): number {
  switch (mode) {
    case 'walking':
      return Math.round(distanceMeters / 1.2); // ~4.3 km/h
    case 'cable':
      return Math.round(300 + distanceMeters / 6.0); // 5 min buffer + ~21 km/h
    case 'ferry':
      return Math.round(300 + distanceMeters / 8.0); // 5 min buffer + ~29 km/h
    case 'flight':
      return Math.round(1800 + distanceMeters / 150.0); // buffer + ~540 km/h
    case 'driving':
    default:
      return Math.round(120 + distanceMeters / 9.5); // ~35 km/h
  }
}

export function generateCurvedCoordinates(
  from: Coordinates,
  to: Coordinates,
  curvature = 0.15,
  pointsCount = 20,
): Coordinates[] {
  const points: Coordinates[] = [];
  const dx = to.lng - from.lng;
  const dy = to.lat - from.lat;

  // Midpoint
  const midLat = (from.lat + to.lat) / 2;
  const midLng = (from.lng + to.lng) / 2;

  // Control point perpendicularly offset from chord
  const ctrlLat = midLat - dx * curvature;
  const ctrlLng = midLng + dy * curvature;

  for (let i = 0; i <= pointsCount; i += 1) {
    const t = i / pointsCount;
    // Quadratic Bezier interpolation
    const lat = (1 - t) * (1 - t) * from.lat + 2 * (1 - t) * t * ctrlLat + t * t * to.lat;
    const lng = (1 - t) * (1 - t) * from.lng + 2 * (1 - t) * t * ctrlLng + t * t * to.lng;
    points.push({ lat, lng });
  }

  return points;
}

export function detectTransitMode(point: { title?: string; transitInfo?: string; transitMode?: TransitMode }): TransitMode {
  if (point.transitMode) return point.transitMode;
  const text = `${point.title ?? ''} ${point.transitInfo ?? ''}`.toLowerCase();
  if (text.includes('cáp treo') || text.includes('cable')) return 'cable';
  if (text.includes('cano') || text.includes('tàu') || text.includes('phà') || text.includes('thuyền') || text.includes('vượt biển') || text.includes('biển đảo') || text.includes('kayak') || text.includes('lặn')) return 'ferry';
  if (text.includes('sân bay') || text.includes('airport') || text.includes('chuyến bay') || text.includes('máy bay') || text.includes('tiễn sân bay')) return 'flight';
  if (text.includes('đi bộ') || text.includes('tản bộ') || text.includes('dạo ngắm') || text.includes('dạo biển')) return 'walking';
  if (text.includes('xe đạp') || text.includes('đạp xe') || text.includes('bicycle') || text.includes('cycling')) return 'bicycle';
  return 'driving';
}

/**
 * Các chặng cần vẽ, theo thứ tự đi. Mỗi ngày: khách sạn → các điểm → khách sạn. Có chặng bay thì như backend tính km
 * (AC-AGT-04, chốt 2026-10-09): ngày đầu bắt đầu ở sân bay đến rồi về khách sạn (sân bay → khách sạn → các điểm → khách
 * sạn), ngày cuối (chuyến từ 2 ngày) đi từ khách sạn qua các điểm rồi ra sân bay; ngày không có điểm vẫn có chặng sân bay.
 */
export function buildRouteRequests(plan: GroundedPlan, filterDay = 0): RouteRequest[] {
  const days = filterDay === 0 ? plan.days.map((day) => day.day) : [filterDay];
  const requests: RouteRequest[] = [];
  const { arrival, departure } = getAirportPoints(plan);
  const firstDay = plan.days[0]?.day;
  const lastDay = plan.days.length > 1 ? plan.days[plan.days.length - 1].day : undefined;

  for (const dayNumber of days) {
    const day = plan.days.find((candidate) => candidate.day === dayNumber);
    if (!day) continue;

    const stayPoint = getStayPointForDay(plan, dayNumber);
    let slotOrder = 0;
    const slotPoints = day.slots.flatMap((slot) => {
      const point = pointFromSlot(slot, dayNumber, slotOrder + 1);
      if (!point) return [];
      slotOrder += 1;
      return [point];
    });
    const start = dayNumber === firstDay && arrival ? arrival : null;
    const end = dayNumber === lastDay && departure ? departure : null;
    if (slotPoints.length === 0 && !start && !end) continue;

    const orderedPoints = [...(start ? [start] : []), ...(stayPoint ? [stayPoint] : []), ...slotPoints];
    const lastPoint = slotPoints[slotPoints.length - 1];
    if (end) {
      orderedPoints.push(end);
    } else if (stayPoint && lastPoint && !isAirportPoint(lastPoint) && !sameCoordinate(lastPoint.coordinates, stayPoint.coordinates)) {
      orderedPoints.push(stayPoint);
    }

    for (let index = 0; index < orderedPoints.length - 1; index += 1) {
      const from = orderedPoints[index];
      const to = orderedPoints[index + 1];
      if (sameCoordinate(from.coordinates, to.coordinates)) continue;

      // Ưu tiên transitMode chỉ định, hoặc detect từ thông tin chặng
      // Chặng sân bay đi bằng xe như mọi chặng về khách sạn.
      const inferredMode = to.type === 'slot'
        ? (to.transitMode ?? detectTransitMode(to))
        : (from.transitMode === 'cable' || from.transitMode === 'ferry' ? from.transitMode : 'driving');

      requests.push({
        id: `day-${dayNumber}-${from.id}-to-${to.id}`,
        fromPointId: from.id,
        toPointId: to.id,
        from: from.coordinates,
        to: to.coordinates,
        fromTitle: from.title,
        toTitle: to.title,
        mode: inferredMode,
        transitInfo: to.transitInfo,
      });
    }
  }

  return requests;
}

export async function resolveRouteRequests(
  requests: RouteRequest[],
  provider: RouteProvider,
  onResult?: (result: RouteResult) => void,
): Promise<RouteResult[]> {
  return Promise.all(requests.map(async (request) => {
    let result: RouteResult;
    try {
      result = await provider.getRoute(request);
    } catch (error) {
      result = unavailable(request, error instanceof Error ? error.message : 'Không thể tải dữ liệu tuyến');
    }
    onResult?.(result);
    return result;
  }));
}

interface OsrmRouteResponse {
  code?: string;
  routes?: Array<{
    distance?: number;
    duration?: number;
    geometry?: {
      type?: string;
      coordinates?: unknown;
    };
  }>;
}

type OsrmProfile = 'routed-car' | 'routed-foot' | 'routed-bike';

const DEFAULT_OSRM_BASE_URL = 'https://routing.openstreetmap.de';
const DEFAULT_OSRM_MIN_INTERVAL_MS = 1000;
const osrmRouteCache = new Map<string, RouteResult>();
const osrmRouteInflight = new Map<string, Promise<RouteResult>>();
let osrmRequestQueue: Promise<void> = Promise.resolve();
let lastOsrmRequestStartedAt = 0;

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function enqueueOsrmRequest<T>(task: () => Promise<T>, minimumIntervalMs: number): Promise<T> {
  let run!: Promise<T>;
  run = osrmRequestQueue.then(async () => {
    // setTimeout có thể đánh thức sớm vài mili giây so với Date.now(): chờ lại đến khi đủ khoảng tối thiểu.
    let wait = Math.max(0, minimumIntervalMs - (Date.now() - lastOsrmRequestStartedAt));
    while (wait > 0) {
      await delay(wait);
      wait = Math.max(0, minimumIntervalMs - (Date.now() - lastOsrmRequestStartedAt));
    }
    lastOsrmRequestStartedAt = Date.now();
    return task();
  });
  osrmRequestQueue = run.then(() => undefined, () => undefined);
  return run;
}

function osrmProfileFor(mode: TransitMode): OsrmProfile | null {
  switch (mode) {
    case 'driving':
      return 'routed-car';
    case 'walking':
      return 'routed-foot';
    case 'bicycle':
      return 'routed-bike';
    default:
      return null;
  }
}

function withRequestIdentity(result: RouteResult, request: RouteRequest): RouteResult {
  return {
    ...result,
    id: request.id,
    fromPointId: request.fromPointId,
    toPointId: request.toPointId,
    fromTitle: request.fromTitle,
    toTitle: request.toTitle,
    transitInfo: request.transitInfo,
  };
}

export class OsrmRouteProvider implements RouteProvider {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly minimumIntervalMs: number;

  constructor(
    baseUrl = process.env.NEXT_PUBLIC_OSRM_BASE_URL ?? DEFAULT_OSRM_BASE_URL,
    fetchImpl: typeof fetch = fetch,
    minimumIntervalMs = DEFAULT_OSRM_MIN_INTERVAL_MS,
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.fetchImpl = fetchImpl;
    this.minimumIntervalMs = minimumIntervalMs;
  }

  async getRoute(request: RouteRequest): Promise<RouteResult> {
    const profile = osrmProfileFor(request.mode);
    if (!profile) return unavailable(request, `Route provider chưa hỗ trợ phương tiện: ${request.mode}`);

    const cacheKey = `${this.baseUrl}:${request.mode}:${request.from.lat.toFixed(5)},${request.from.lng.toFixed(5)}->${request.to.lat.toFixed(5)},${request.to.lng.toFixed(5)}`;
    const cached = osrmRouteCache.get(cacheKey);
    if (cached) {
      return withRequestIdentity(cached, request);
    }

    const inflight = osrmRouteInflight.get(cacheKey);
    if (inflight) {
      return inflight.then((result) => withRequestIdentity(result, request));
    }

    const routePromise = enqueueOsrmRequest(async () => {
      const coordinatePath = `${request.from.lng},${request.from.lat};${request.to.lng},${request.to.lat}`;
      const url = `${this.baseUrl}/${profile}/route/v1/driving/${coordinatePath}?overview=full&geometries=geojson&steps=false`;
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
      const timeoutId = controller ? setTimeout(() => controller.abort(), 6000) : null;

      try {
        const response = await this.fetchImpl.call(globalThis, url, {
          method: 'GET',
          headers: { accept: 'application/json' },
          signal: controller?.signal,
        });
        if (!response.ok) return unavailable(request, `Route provider trả về HTTP ${response.status}`);

        let payload: OsrmRouteResponse;
        try {
          payload = await response.json() as OsrmRouteResponse;
        } catch {
          return unavailable(request, 'OSRM trả về payload không hợp lệ');
        }

        const route = payload.code === 'Ok' ? payload.routes?.[0] : undefined;
        const rawCoordinates = route?.geometry?.coordinates;
        const geometry = normalizeGeoJsonCoordinates(rawCoordinates);
        const geometryIsValid = Array.isArray(rawCoordinates)
          && rawCoordinates.length >= 2
          && geometry.length === rawCoordinates.length
          && (!route?.geometry?.type || route.geometry.type === 'LineString');
        const metricsAreValid = typeof route?.distance === 'number'
          && Number.isFinite(route.distance)
          && typeof route.duration === 'number'
          && Number.isFinite(route.duration);
        if (!route || !geometryIsValid || !metricsAreValid) {
          return unavailable(request, payload.code === 'NoRoute'
            ? 'Không tìm thấy tuyến OSRM phù hợp'
            : 'Không tìm thấy route geometry phù hợp');
        }

        const result: RouteResult = {
          ...request,
          status: 'routed',
          geometry,
          distanceMeters: route.distance,
          durationSeconds: route.duration,
        };
        osrmRouteCache.set(cacheKey, result);
        return result;
      } catch (error) {
        return unavailable(request, error instanceof Error ? `Không thể kết nối OSRM: ${error.message}` : 'Không thể kết nối OSRM');
      } finally {
        if (timeoutId) clearTimeout(timeoutId);
      }
    }, this.minimumIntervalMs);
    osrmRouteInflight.set(cacheKey, routePromise);
    void routePromise.then(
      () => {
        if (osrmRouteInflight.get(cacheKey) === routePromise) osrmRouteInflight.delete(cacheKey);
      },
      () => {
        if (osrmRouteInflight.get(cacheKey) === routePromise) osrmRouteInflight.delete(cacheKey);
      },
    );
    return routePromise.then((result) => withRequestIdentity(result, request));
  }
}

/**
 * Multimodal Route Provider:
 * - Cano / tàu (ferry), Cáp treo (cable), Chuyến bay (flight): vẽ curved route bám trên biển/không gian.
 * - Ô tô (driving), Đi bộ (walking) và Xe đạp (bicycle): lấy route geometry thực tế từ OSRM,
 *   KHÔNG fallback.
 */
export class MultimodalRouteProvider implements RouteProvider {
  constructor(private readonly roadProvider: RouteProvider = new OsrmRouteProvider()) {}

  async getRoute(request: RouteRequest): Promise<RouteResult> {
    if (request.mode === 'ferry' || request.mode === 'cable' || request.mode === 'flight') {
      const isReturn = request.toPointId.startsWith('stay-');
      const curvature = isReturn ? -0.16 : 0.15;
      const geometry = generateCurvedCoordinates(request.from, request.to, curvature, 20);
      const distanceMeters = Math.round(calculateHaversineDistanceMeters(request.from, request.to));
      const durationSeconds = estimateDurationSeconds(distanceMeters, request.mode);
      return {
        ...request,
        status: 'routed',
        geometry,
        distanceMeters,
        durationSeconds,
      };
    }

    // Ô tô, đi bộ và xe đạp: bắt buộc lấy geometry thực tế từ OSRM, không fake fallback
    return this.roadProvider.getRoute(request);
  }
}

export const defaultRouteProvider: RouteProvider = new MultimodalRouteProvider();
