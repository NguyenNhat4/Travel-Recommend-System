/**
 * Chuyển ItineraryResponse của backend sang kiểu hiển thị của giỏ hàng và bản đồ.
 * Lịch trình do Itinerary Agent ở backend dựng; frontend không tự lập lịch trình.
 */

import { CATALOG } from '../data/catalog';
import { TravelIntent, GroundedPlan, Destination, ItinerarySlot, ItineraryDay, Product } from '../types/travel';
import { detectTransitMode } from './routeGeometry';
import type { components } from '../types/api.gen';

const SLOT_TIME_FROM_API: Record<components['schemas']['SlotTime'], ItinerarySlot['time']> = {
  MORNING: 'morning',
  NOON: 'noon',
  AFTERNOON: 'afternoon',
  EVENING: 'evening',
};

/**
 * Chuyển ProductSummary của API sang Product của giỏ hàng/bản đồ.
 * Tên và giá luôn lấy từ response (grounding). CATALOG local chỉ bổ sung tọa độ/địa chỉ;
 * không có thì để trống, không đặt ghim giả ở tâm thành phố.
 */
export function mapProductSummaryToProduct(summary: components['schemas']['ProductSummary']): Product {
  const catalogItem = CATALOG.find((p) => p.id === summary.productId);
  return {
    id: summary.productId,
    name: summary.name,
    destination: summary.destination as Destination,
    taxonomy: summary.taxonomy as Product['taxonomy'],
    unitPrice: summary.unitPrice ?? 0,
    currency: 'VND',
    imageUrl: summary.imageUrl || catalogItem?.imageUrl || '/placeholders/hotel.webp',
    coordinates: catalogItem?.coordinates,
    address: catalogItem?.address || summary.destination,
    description: summary.name,
    attributes: (summary.attributes || {}) as Product['attributes'],
    available: summary.available,
  };
}

/** Số điểm trong lịch trình có/không có tọa độ để vẽ bản đồ. */
export function planLocationCoverage(plan: GroundedPlan) {
  const points = [plan.stay?.product, ...plan.days.flatMap((day) => day.slots.filter((slot) => slot.product).map((slot) => slot.product))];
  const located = points.filter((product) => product?.coordinates).length;
  return { located, missing: points.filter(Boolean).length - located };
}

export function convertItineraryResponseToGroundedPlan(
  response: components['schemas']['ItineraryResponse'] | null | undefined
): GroundedPlan | null {
  if (!response || response.status !== 'COMPLETED' || !response.itinerary) return null;
  const itinerary = response.itinerary;
  const intentDestination = (response.intent?.destination || itinerary.stay?.product.destination || '') as Destination;

  const stay = itinerary.stay?.product
    ? {
        productId: itinerary.stay.product.productId,
        product: mapProductSummaryToProduct(itinerary.stay.product),
        note: itinerary.stay.note || 'Khách sạn lưu trú',
        source: (itinerary.stay.source as 'recommendation' | 'search' | undefined) || 'search',
      }
    : undefined;

  const days: ItineraryDay[] = (itinerary.days || []).map((d) => {
    const slots: ItinerarySlot[] = (d.slots || []).map((slot) => {
      const product = slot.product ? mapProductSummaryToProduct(slot.product) : undefined;
      const slotTime = SLOT_TIME_FROM_API[slot.time] ?? 'morning';

      return {
        time: slotTime,
        timeRange: slot.startTime && slot.endTime ? `${slot.startTime} - ${slot.endTime}` : undefined,
        locationName: product?.name || slot.activityType || 'Điểm hoạt động',
        productId: product?.id,
        product,
        note: slot.note || '',
        activityTitle: product?.name || slot.activityType || slot.note || 'Hoạt động',
        coordinates: product?.coordinates,
        address: product?.address || intentDestination,
        transitMode: detectTransitMode({
          title: product?.name || slot.activityType,
          transitInfo: slot.note ?? undefined,
        }),
      };
    });

    return {
      day: d.day,
      title: d.title || `Ngày ${d.day}`,
      slots,
    };
  });

  let party: TravelIntent['party'] = 'family_with_kids';
  const rawParty = response.intent?.party as { type?: string } | string | undefined;
  const partyType = typeof rawParty === 'object' && rawParty !== null ? rawParty.type : rawParty;
  if (partyType === 'SOLO' || partyType === 'solo') party = 'solo';
  else if (partyType === 'COUPLE' || partyType === 'couple') party = 'couple';
  else if (partyType === 'FRIENDS' || partyType === 'friends') party = 'friends';
  else if (partyType === 'FAMILY_WITH_KIDS' || partyType === 'family_with_kids') party = 'family_with_kids';

  return {
    intent: {
      destination: intentDestination,
      days: response.intent?.days || days.length || 3,
      party,
      interests: response.intent?.interests || ['theme_park', 'beach'],
    },
    title: itinerary.title || `Lịch trình khám phá ${intentDestination}`,
    stay,
    days,
    totalEstimatedPrice: itinerary.estimatedTotal ?? 0,
    bookableProductsCount: itinerary.bookableCount ?? 0,
    fallback: false,
  };
}

