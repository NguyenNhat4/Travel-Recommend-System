import { productFromApi } from '../../../services/catalog';
import type { components } from '../../../types/api.gen';
import type { Product, ItineraryDay, ItinerarySlot } from '../../../types/travel';
import { itineraryCartItems } from '../../../components/assistant/AssistantResultPanel';
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

  const timeRanges: Record<string, string> = {
    morning: '08:00 - 11:30',
    noon: '11:45 - 13:30',
    afternoon: '14:30 - 17:30',
    evening: '18:00 - 21:00',
  };

  const days: ItineraryDay[] = response.itinerary.days.map((d) => {
    const slots: ItinerarySlot[] = d.slots.map((s) => {
      const product = s.product ? adaptProductSummaryToProduct(s.product) : undefined;
      const title = s.product?.name || s.activityType || s.note || 'Hoạt động trải nghiệm';
      const locName = s.product?.name || s.product?.destination || dest;
      const timeRange = (s.startTime && s.endTime) ? `${s.startTime} - ${s.endTime}` : (timeRanges[s.time] || '08:00 - 11:30');
      const coords = product?.coordinates || defaultCoords;

      return {
        time: s.time as any,
        timeRange,
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
