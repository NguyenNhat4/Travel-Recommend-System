import { productFromApi } from '../../../services/catalog';
import type { components } from '../../../types/api.gen';
import type { Product, ItineraryDay, ItinerarySlot } from '../../../types/travel';
import { itineraryCartItems } from '../../../components/assistant/AssistantResultPanel';
import { SLOT_TIME_FROM_API } from '../../../services/assistant';
import type { WidgetPlan } from './widgetTypes';

const DESTINATION_COORDINATES: Record<string, { lat: number; lng: number }> = {
  'Nha Trang': { lat: 12.2388, lng: 109.1967 },
  'Phú Quốc': { lat: 10.2899, lng: 103.9840 },
  'Đà Nẵng': { lat: 16.0544, lng: 108.2022 },
  'Đà Lạt': { lat: 11.9404, lng: 108.4376 },
  'Hội An': { lat: 15.8801, lng: 108.3380 },
  'Hạ Long': { lat: 20.9501, lng: 107.0734 },
  'Hà Nội': { lat: 21.0285, lng: 105.8542 },
};

/**
 * Điểm tham quan tự do: điểm tham quan/golf có `ticketed=false` hoặc chưa có giá. Backend tính 0 đ vào tổng
 * (`docs/prd/architecture.md` §3), nên Web ghi "Tham quan tự do" thay vì để trống hay ghi 0 ₫.
 */
export function isFreeToVisit(product: Pick<Product, 'taxonomy' | 'unitPrice' | 'attributes'>): boolean {
  if (product.attributes?.ticketed === false) return true;
  return product.unitPrice == null && (product.taxonomy === 'attraction' || product.taxonomy === 'golf');
}

function adaptProductSummaryToProduct(summary: components['schemas']['ProductSummary']): Product {
  const product = productFromApi(summary);
  const defaultCoords = DESTINATION_COORDINATES[product.destination] || { lat: 12.2388, lng: 109.1967 };
  return {
    ...product,
    priceString: summary.unitPrice != null ? new Intl.NumberFormat('vi-VN').format(summary.unitPrice) + ' ₫' : undefined,
    coordinates: product.coordinates || defaultCoords,
  };
}

export function convertItineraryCompletedToGroundedPlan(
  response: components['schemas']['ItineraryCompleted']
): WidgetPlan {
  const dest = (response.intent?.destination || 'Nha Trang') as any;
  const daysCount = response.intent?.days || response.itinerary.days.length || 3;
  const party = (response.intent?.party as any) || 'family_with_kids';
  const defaultCoords = DESTINATION_COORDINATES[dest] || { lat: 12.2388, lng: 109.1967 };

  const stayItem = response.itinerary.stay ? {
    productId: response.itinerary.stay.product.productId,
    product: adaptProductSummaryToProduct(response.itinerary.stay.product),
    nights: response.itinerary.stay.nights || (daysCount > 1 ? daysCount - 1 : 1),
    note: response.itinerary.stay.note || 'Khách sạn lưu trú 5 sao',
    source: (response.itinerary.stay.source as any) || 'search',
    because: response.itinerary.stay.because as any,
  } : undefined;

  const days: ItineraryDay[] = response.itinerary.days.map((d) => {
    const slots: ItinerarySlot[] = d.slots.map((s) => {
      const product = s.product ? adaptProductSummaryToProduct(s.product) : undefined;
      const title = s.product?.name || s.activityType || s.note || 'Hoạt động trải nghiệm';
      const locName = s.product?.name || s.product?.destination || dest;
      const coords = product?.coordinates || defaultCoords;

      return {
        time: SLOT_TIME_FROM_API[s.time],
        activityTitle: title,
        locationName: locName,
        productId: s.product?.productId,
        product,
        note: s.note || '',
        source: (s.source as any) || 'curated',
        coordinates: coords,
        address: product?.address || dest,
        transitInfo: '',
        transitMode: 'driving',
        isActivityNote: !s.product,
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
      party,
      interests: response.intent?.interests || [],
    },
    title: response.itinerary.title || `Lịch trình ${daysCount} ngày tại ${dest}`,
    stay: stayItem,
    stays: stayItem ? [stayItem] : undefined,
    days,
    totalEstimatedPrice: response.itinerary.estimatedTotal ?? null,
    bookableProductsCount: response.itinerary.bookableCount ?? days.reduce((acc, cur) => acc + cur.slots.filter(s => !!s.product).length, 0),
    cartItems: itineraryCartItems(response.itinerary, response.intent?.party),
  };
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
  const stay = plan.stay;
  if (stay?.productId === productId) {
    return { day: plan.days[0]?.day ?? 1, pointId: `stay-${productId}`, coordinate: stay.product?.coordinates || null };
  }
  return null;
}
