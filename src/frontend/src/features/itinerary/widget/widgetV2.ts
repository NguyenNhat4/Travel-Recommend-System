import type { components as V2 } from '../../../types/assistant-v2.gen';
import type { components } from '../../../types/api.gen';
import type { AssistantResponse } from '../../../services/assistantStream';
import type { AssistantProgress } from '../../../context/assistantState';
import type { ProgressActivity } from './progressModel';

type Final = V2['schemas']['AssistantV2Final'];
type UiAction = V2['schemas']['UiAction'];
type V1 = components['schemas'];

const BUDGET_STATUS = { not_set: 'NO_BUDGET', within: 'WITHIN_BUDGET', over: 'OVER_BUDGET', unknown: 'UNKNOWN' } as const;

function period(minute: number): V1['SlotTime'] {
  return minute < 660 ? 'MORNING' : minute < 780 ? 'NOON' : minute < 1080 ? 'AFTERNOON' : 'EVENING';
}

function clock(minute: number): string {
  return `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;
}

function dayOffset(from: string, to: string): number {
  return Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000);
}

/** Chữ trên nút → lệnh server cấp: nút hỏi vé và nút chọn phương án khác. Bấm hoặc gõ đúng chữ đều gửi lệnh (AC-AGT-08). */
export function v2Actions(final: Final): Map<string, UiAction> {
  const actions = new Map<string, UiAction>();
  for (const suggestion of final.suggestions) if (suggestion.uiAction) actions.set(suggestion.label, suggestion.uiAction);
  for (const alternative of final.alternatives) actions.set(`Chọn ${alternative.product.name}`, alternative.uiAction);
  return actions;
}

function itinerary(plan: NonNullable<Final['itinerary']>): V1['ItineraryCompleted']['itinerary'] {
  const people = plan.party.adults + plan.party.children;
  return {
    title: `Lịch trình ${plan.days.length} ngày tại ${plan.destination}`,
    days: plan.days.map((day) => ({
      day: day.dayIndex,
      date: day.date,
      // Giờ chính xác và giả định thời gian của orc nằm ở ghi chú; buổi suy từ giờ bắt đầu.
      slots: day.activities.map((activity) => ({
        time: period(activity.startMinute),
        product: activity.product,
        note: [`${clock(activity.startMinute)}–${clock(activity.endMinute)}`, activity.assumption].filter(Boolean).join(' · '),
      })),
    })),
    stays: plan.stays.map((stay) => ({
      product: stay.product, nights: stay.nights, rooms: stay.rooms, fromNight: dayOffset(plan.startDate, stay.checkIn) + 1,
    })),
    flights: plan.flights.map((flight) => ({
      product: flight.product,
      direction: flight.role === 'return' ? 'RETURN' : 'OUTBOUND',
      date: flight.product.availableFrom ?? plan.startDate,
      passengers: people,
      source: 'SEARCH',
    })),
    estimatedTotal: plan.costs.estimatedTotalVnd,
    currency: 'VND',
    budgetStatus: BUDGET_STATUS[plan.costs.budgetStatus],
  };
}

/**
 * Câu trả lời v2 trong dạng dữ liệu widget đang hiển thị, để dùng lại thẻ đặt sau câu, khung lịch, bản đồ và giỏ.
 * Chỉ đổi cách đặt field: không thêm, bỏ hay xếp lại sản phẩm. Không có lịch mới thì lịch đang hiện giữ nguyên.
 */
export function v2AsV1Response(final: Final): AssistantResponse {
  const cards: Record<string, V1['ProductSummary'][]> = {};
  for (const [taxonomy, products] of Object.entries(final.recommendations)) if (products.length) cards[taxonomy] = [...products];
  for (const { product } of final.alternatives) (cards[product.taxonomy] ??= []).push(product);
  const suggestions = [...final.suggestions.map((s) => s.label), ...final.alternatives.map((a) => `Chọn ${a.product.name}`)];
  const searchResults = cards as V1['ItineraryNeedsClarification']['searchResults'];
  if (!final.itinerary) {
    const answer: V1['ItineraryNeedsClarification'] = {
      status: 'NEEDS_CLARIFICATION', conversationId: final.conversationId, question: final.message, searchResults, suggestions,
    };
    return answer;
  }
  const plan = final.itinerary;
  const completed: V1['ItineraryCompleted'] = {
    status: 'COMPLETED',
    conversationId: final.conversationId,
    message: final.message,
    suggestions,
    searchResults,
    warnings: final.warnings.map((w) => ({ code: w.code, message: w.message })),
    // Widget chỉ đọc điểm đến, số ngày và đoàn khách của intent; ngân sách v2 nằm ở costs (null khác 0), không chép sang.
    intent: { destination: plan.destination, days: plan.days.length, startDate: plan.startDate, interests: [],
      party: { adults: plan.party.adults, children: plan.party.children } } as V1['ItineraryCompleted']['intent'],
    itinerary: itinerary(plan),
  };
  return completed;
}

type ActivityData = V2['schemas']['ActivityData'];
const ACTIVITY_CODE: Partial<Record<ActivityData['kind'], ProgressActivity['code']>> = {
  flights: 'SEARCHING_FLIGHTS', itinerary: 'CHECKING_AVAILABILITY', detail: 'READING_SHOWN',
};

/** Một lời gọi tool orc vừa bắt đầu → dòng "đang làm" của khung tiến trình (AC-AGT-09). */
export function v2Activity(data: ActivityData): ProgressActivity {
  if (data.kind === 'answer') return { nodeId: 'gatekeep', code: 'STARTED' };
  return { nodeId: 'run_jobs', code: ACTIVITY_CODE[data.kind] ?? 'SEARCHING', groupId: `job:${data.groupId.slice(1)}`,
    ...(data.taxonomy ? { kinds: [data.taxonomy] } : {}) };
}

/** Lời gọi tool xong → nhóm tìm kiếm có số đếm của backend: tìm thấy (đủ điều kiện) và số đã giới thiệu. */
export function v2Progress(data: ActivityData): AssistantProgress {
  const status = data.status === 'failed' ? 'failed' : data.status === 'partial' ? 'partial'
    : data.counts.eligible ? 'ok' : 'empty';
  const search = data.taxonomy && data.kind !== 'itinerary' ? [{
    groupId: `job:${data.groupId.slice(1)}`, kind: data.taxonomy, status,
    counts: { inScope: data.counts.eligible, ...(data.counts.displayed ? { chosen: data.counts.displayed } : {}) },
  } as const] : [];
  return { nodeId: 'run_jobs', outcome: data.status,
    progress: { steps: ['understand', 'search', 'write'], ...(search.length ? { searches: search } : {}) } };
}
