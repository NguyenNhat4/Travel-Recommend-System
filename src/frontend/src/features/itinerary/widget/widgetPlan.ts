import { productFromApi } from '../../../services/catalog';
import type { components } from '../../../types/api.gen';
import type { Product, ItineraryDay, ItinerarySlot } from '../../../types/travel';
import { itineraryCartItems, itineraryStays } from '../../../components/assistant/AssistantResultPanel';
import { ACTIVITY_TYPE_LABEL, PARTY_TYPE_LABEL } from '../../../components/assistant/assistantLabels';
import { SLOT_TIME_FROM_API } from '../../../services/assistant';
import type { StayOptionCard, WidgetBudgetSummary, WidgetPlan } from './widgetTypes';

/**
 * Điểm tham quan tự do: điểm tham quan/golf có `ticketed=false` hoặc chưa có giá. Backend tính 0 đ vào tổng
 * (`docs/prd/architecture.md` §3), nên Web ghi "Tham quan tự do" thay vì để trống hay ghi 0 ₫.
 */
export function isFreeToVisit(product: Pick<Product, 'taxonomy' | 'unitPrice' | 'attributes'>): boolean {
  if (product.attributes?.ticketed === false) return true;
  return product.unitPrice == null && (product.taxonomy === 'attraction' || product.taxonomy === 'golf');
}

function adaptProductSummaryToProduct(summary: components['schemas']['ProductSummary']): Product {
  // Toạ độ chỉ lấy từ `attributes` của catalog; thiếu thì không có điểm trên bản đồ, không đặt giả ở tâm thành phố.
  return {
    ...productFromApi(summary),
    priceString: summary.unitPrice != null ? new Intl.NumberFormat('vi-VN').format(summary.unitPrice) + ' ₫' : undefined,
  };
}

/**
 * productId → sản phẩm của response `COMPLETED`/`FALLBACK` (chỗ ở, các slot, `searchResults`): nguồn duy nhất
 * của thẻ trong lời diễn giải (PRD user-flow.md §4.2). Id không có ở đây thì không dựng thẻ.
 */
export function narrationProducts(
  response: components['schemas']['ItineraryCompleted'] | components['schemas']['ItineraryFallback'],
): Record<string, Product> {
  const itinerary = 'itinerary' in response ? response.itinerary : null;
  const summaries = [
    ...(itinerary?.flights ?? []).map((flight) => flight.product),
    ...(itinerary ? itineraryStays(itinerary) : []).map((stay) => stay.product),
    ...(itinerary?.days ?? []).flatMap((day) => day.slots.flatMap((slot) => (slot.product ? [slot.product] : []))),
    ...Object.values(response.searchResults ?? {}).flatMap((products) => products ?? []),
    // Khách sạn của các phương án (contract 1.20.0): sau khi bấm thẻ đổi khách sạn, lời diễn giải cũ vẫn nhắc khách sạn
    // trước đó; nó vẫn là sản phẩm thật của response nên tên vẫn mở được chi tiết (thẻ gọn của khách sạn thì hàng thẻ
    // "Phương án khác" thay).
    ...('stayOptions' in response ? response.stayOptions?.options ?? [] : [])
      .flatMap((option) => itineraryStays(option.itinerary))
      .map((stay) => stay.product),
  ];
  const products: Record<string, Product> = {};
  for (const summary of summaries) {
    if (!Object.prototype.hasOwnProperty.call(products, summary.productId)) {
      products[summary.productId] = adaptProductSummaryToProduct(summary);
    }
  }
  return products;
}

/** Nhãn đoàn khách từ `intent.party` thật; không có thì `null` để ẩn, không đoán là gia đình hay cặp đôi. */
export function partyLabel(party: components['schemas']['Party'] | null | undefined): string | null {
  if (!party) return null;
  if (party.adults > 0) return party.children > 0 ? `${party.adults} người lớn, ${party.children} trẻ em` : `${party.adults} người lớn`;
  return party.type ? PARTY_TYPE_LABEL[party.type] : null;
}

/** Hậu tố số phòng sau giá một đêm (AC-AGT-04, chốt 2026-10-09): chỉ ghi khi đoàn ở từ 2 phòng. */
export function roomsSuffix(rooms: number | undefined): string {
  return rooms != null && rooms > 1 ? ` × ${rooms} phòng` : '';
}

export function convertItineraryCompletedToGroundedPlan(
  response: components['schemas']['ItineraryCompleted']
): WidgetPlan {
  const dest = (response.intent?.destination ?? '') as any;
  const daysCount = response.intent?.days || response.itinerary.days.length || 3;

  // Khách sạn theo đêm (contract 1.19.0, AC-AGT-04); response cũ chỉ có `stay`, coi như từ đêm 1.
  const apiStays = itineraryStays(response.itinerary);
  const stayItems = apiStays.map((stay) => {
    const nights = stay.nights || (daysCount > 1 ? daysCount - 1 : 1);
    const fromNight = stay.fromNight ?? 1;
    const lastNight = fromNight + nights - 1;
    return {
      productId: stay.product.productId,
      product: adaptProductSummaryToProduct(stay.product),
      nights,
      fromNight,
      rooms: stay.rooms ?? 1,
      dayRange: lastNight > fromNight ? `Đêm ${fromNight}–${lastNight}` : `Đêm ${fromNight}`,
      note: stay.note ?? '',
      source: (stay.source as any) || 'search',
      because: stay.because as any,
    };
  });
  const stayItem = stayItems[0];

  const flights = (response.itinerary.flights ?? []).map((flight) => ({
    productId: flight.product.productId,
    product: adaptProductSummaryToProduct(flight.product),
    direction: flight.direction,
    date: flight.date,
    returnDate: flight.returnDate ?? null,
    passengers: flight.passengers,
  }));

  const days: ItineraryDay[] = response.itinerary.days.map((d) => {
    const slots: ItinerarySlot[] = d.slots.map((s) => {
      const product = s.product ? adaptProductSummaryToProduct(s.product) : undefined;
      const title = s.product?.name ?? (s.activityType ? ACTIVITY_TYPE_LABEL[s.activityType] : 'Hoạt động tự do');

      return {
        time: SLOT_TIME_FROM_API[s.time],
        activityTitle: title,
        locationName: product?.address || dest,
        productId: s.product?.productId,
        product,
        note: s.note || '',
        source: (s.source as any) || 'curated',
        coordinates: product?.coordinates,
        address: product?.address || dest,
        transitInfo: '',
        transitMode: 'driving',
        isActivityNote: !s.product,
        activityType: s.activityType ?? undefined,
        because: s.because as any,
      };
    });

    return {
      day: d.day,
      title: d.title || `Ngày ${d.day} tại ${dest}`,
      slots,
    };
  });

  return {
    intent: {
      destination: dest,
      days: daysCount,
      // Party của API là object, không phải nhãn: Web hiển thị `partyLabel`, giỏ hàng đọc `response.intent.party`.
      party: response.intent?.party as any,
      interests: response.intent?.interests || [],
    },
    partyLabel: partyLabel(response.intent?.party),
    budgetSummary: budgetSummary(response),
    title: response.itinerary.title || `Lịch trình ${daysCount} ngày tại ${dest}`,
    stay: stayItem,
    stays: stayItems.length > 0 ? stayItems : undefined,
    flights: flights.length > 0 ? flights : undefined,
    days,
    totalEstimatedPrice: response.itinerary.estimatedTotal ?? null,
    bookableProductsCount: response.itinerary.bookableCount ?? days.reduce((acc, cur) => acc + cur.slots.filter(s => !!s.product).length, 0),
    cartItems: itineraryCartItems(response.itinerary, response.intent?.party),
  };
}

/** Khối "Ngân sách dự tính" của lịch: chỉ khi backend gửi `costBreakdown` (tổng đã biết) và trạng thái ngân sách đã rõ. */
function budgetSummary(response: components['schemas']['ItineraryCompleted']): WidgetBudgetSummary | null {
  const { costBreakdown, estimatedTotal, budgetStatus } = response.itinerary;
  if (!costBreakdown || estimatedTotal == null || budgetStatus === 'UNKNOWN') return null;
  return {
    total: estimatedTotal,
    flights: costBreakdown.flights,
    stays: costBreakdown.stays,
    activities: costBreakdown.activities,
    budget: response.intent?.budget ?? null,
    status: budgetStatus,
  };
}

/**
 * Khoá của một thẻ trong hàng "Phương án khác": khách sạn và các đêm của lịch đó, như backend phân biệt phương án
 * (`routing._signature`: cùng hai khách sạn mà chia đêm khác là hai phương án). Số phương án đánh lại sau mỗi lần đổi
 * nên không dùng làm khoá; khoá theo khách sạn giữ được thứ tự và thẻ đang chọn qua lần đổi.
 */
export function stayCardKey(card: Pick<StayOptionCard, 'plan'>): string {
  return (card.plan.stays ?? []).map((stay) => `${stay.productId}:${stay.fromNight}:${stay.nights}`).join('+');
}

/**
 * Hàng thẻ "Phương án khác" của một response `COMPLETED` (contract 1.20.0, AC-AGT-04): thẻ đầu là lịch đang chọn,
 * sau đó các phương án theo thứ tự backend gửi. Mỗi thẻ mang lịch đầy đủ để xem trước ở cột phải; tên, ảnh, giá
 * lấy từ sản phẩm trong lịch đó (grounding), chênh tiền/km do backend tính. Không có `stayOptions` thì `undefined`.
 */
export function stayOptionCards(
  response: components['schemas']['ItineraryCompleted'],
  /** Lịch đang chọn đã chuyển sẵn (`convertItineraryCompletedToGroundedPlan(response)`); không có thì chuyển ở đây. */
  currentPlan: WidgetPlan = convertItineraryCompletedToGroundedPlan(response),
): StayOptionCard[] | undefined {
  const stayOptions = response.stayOptions;
  if (!stayOptions?.options.length) return undefined;
  const card = (plan: WidgetPlan, fields: Omit<StayOptionCard, 'hotels' | 'plan'>) =>
    ({ ...fields, plan, hotels: (plan.stays ?? []).map((stay) => stay.product) });
  return [
    card(currentPlan, { index: null, distanceKm: stayOptions.distanceKm, kmDelta: 0, moneyDelta: 0, overBudget: null }),
    ...stayOptions.options.map((option) => card(convertItineraryCompletedToGroundedPlan({ ...response, itinerary: option.itinerary }), {
      index: option.index,
      distanceKm: Math.round((stayOptions.distanceKm + option.kmDelta) * 10) / 10,
      kmDelta: option.kmDelta,
      moneyDelta: option.moneyDelta,
      overBudget: option.overBudget ?? null,
    })),
  ];
}

export interface ProductFocus {
  day: number;
  pointId: string;
  coordinate: { lat: number; lng: number } | null;
}

/**
 * Vị trí của một sản phẩm trong lịch trình để khung bên phải focus: ngày chứa nó, id điểm trên bản đồ
 * (cùng quy ước với `WidgetDays`) và toạ độ. Khách sạn lưu trú thuộc ngày đầu; không có thì `null`.
 */
export function locateProduct(plan: WidgetPlan, productId: string): ProductFocus | null {
  let step = 0;
  for (const day of plan.days) {
    const index = day.slots.findIndex((slot) => slot.productId === productId);
    if (index >= 0) {
      const slot = day.slots[index];
      return {
        day: day.day,
        pointId: `day-${day.day}-slot-${slot.time}-${step + index + 1}`,
        coordinate: slot.coordinates || slot.product?.coordinates || null,
      };
    }
    step += day.slots.length;
  }
  const flight = plan.flights?.find((item) => item.productId === productId);
  if (flight) {
    // Chặng đi (và vé khứ hồi) nằm ở ngày đầu, chặng về ở ngày cuối; vé không có điểm trên bản đồ.
    const day = flight.direction === 'RETURN' ? plan.days[plan.days.length - 1]?.day : plan.days[0]?.day;
    return { day: day ?? 1, pointId: `flight-${productId}`, coordinate: null };
  }
  const stay = plan.stay;
  if (stay?.productId === productId) {
    return { day: plan.days[0]?.day ?? 1, pointId: `stay-${productId}`, coordinate: stay.product?.coordinates || null };
  }
  return null;
}
