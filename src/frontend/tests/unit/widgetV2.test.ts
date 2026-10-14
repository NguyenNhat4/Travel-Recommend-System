import { describe, expect, it } from 'vitest';
import answer30 from '../../../shared/mocks/assistant-v2/answer-30.json';
import over from '../../../shared/mocks/assistant-v2/itinerary-over.json';
import unknown from '../../../shared/mocks/assistant-v2/itinerary-unknown.json';
import type { components as V2 } from '../../src/types/assistant-v2.gen';
import { v2Actions, v2AsV1Response, v2Timeline } from '../../src/features/itinerary/widget/widgetV2';
import { convertItineraryCompletedToGroundedPlan, narrationProducts } from '../../src/features/itinerary/widget/widgetPlan';

import { emptyProgress, mergeTimeline } from '../../src/features/itinerary/widget/progressModel';
import { progressView } from '../../src/features/itinerary/widget/widgetProgressView';

type Final = V2['schemas']['AssistantV2Final'];

describe('assistant v2 answer in the widget', () => {
  it('keeps every card the orc chose: 30 cards across taxonomies, none cut', () => {
    const response = v2AsV1Response(answer30 as unknown as Final);
    expect(response.status).toBe('NEEDS_CLARIFICATION');
    if (response.status !== 'NEEDS_CLARIFICATION') return;
    expect(Object.keys(narrationProducts(response))).toHaveLength(30);
    expect(response.question).toBe(answer30.message);
  });

  it('shows a zero-night, four-activity day with exact times and the over-budget total', () => {
    const response = v2AsV1Response(over as unknown as Final);
    expect(response.status).toBe('COMPLETED');
    if (response.status !== 'COMPLETED') return;
    const plan = convertItineraryCompletedToGroundedPlan(response);
    expect(plan.days[0].slots).toHaveLength(4);
    expect(plan.days[0].slots[0].note).toMatch(/^08:00–09:00/);
    expect(plan.stays).toBeUndefined();
    expect(plan.totalEstimatedPrice).toBe(2_300_000);
    expect(response.itinerary.budgetStatus).toBe('OVER_BUDGET');
    expect(response.warnings.map((w) => w.code)).toContain('OVER_TRIP_BUDGET');
  });

  it('keeps an unknown total unknown, never zero', () => {
    const response = v2AsV1Response(unknown as unknown as Final);
    if (response.status !== 'COMPLETED') throw new Error('expected a plan');
    expect(response.itinerary.estimatedTotal).toBeNull();
    expect(response.itinerary.budgetStatus).toBe('UNKNOWN');
    expect(convertItineraryCompletedToGroundedPlan(response).totalEstimatedPrice).toBeNull();
  });

  it('maps button labels to the server-issued actions they send', () => {
    const final = {
      ...(answer30 as unknown as Final),
      suggestions: [{ label: 'Đắt nhất thì sao?', message: null, uiAction: { type: 'fare_query', actionId: 'a1' } },
        { label: 'Lên lịch Huế', message: 'Lên lịch Huế', uiAction: null }],
      alternatives: [{ alternativeId: 'x', product: answer30.recommendations.hotel[0], violates: [], disclosures: ['Gần biển'],
        itinerary: null, uiAction: { type: 'select_alternative', actionId: 'a2', alternativeId: 'x' } }],
    } as unknown as Final;
    const actions = v2Actions(final);
    expect(actions.get('Đắt nhất thì sao?')).toEqual({ type: 'fare_query', actionId: 'a1' });
    expect(actions.has('Lên lịch Huế')).toBe(false);
    expect(actions.get(`Chọn ${answer30.recommendations.hotel[0].name}`)?.actionId).toBe('a2');
  });

  it('shows real rounds as plain sentences, merging each call with its result and updating counts in place', () => {
    const data = { groupId: 'c3', kind: 'search', status: 'running', taxonomy: 'hotel', destination: 'Huế',
      counts: { found: 0, eligible: 0, selected: 0, displayed: 0 } } as const;
    const thought = { ...data, groupId: 'think:1', kind: 'think', status: 'completed', taxonomy: null,
      explanation: 'Mình sẽ tìm khách sạn phù hợp.' } as const;
    let model = mergeTimeline(emptyProgress(), v2Timeline(thought));
    model = mergeTimeline(model, v2Timeline(data));
    const running = progressView(model);
    expect(running.steps.map((step) => step.label)).toEqual(['Phân tích yêu cầu', 'Đang tìm khách sạn ở Huế…']);
    expect(running.steps[0].lines).toEqual(['Mình sẽ tìm khách sạn phù hợp.']);
    expect(running.steps[1].status).toBe('active');
    const observation = { ...data, status: 'completed', outcome: 'ok',
      counts: { found: 20, eligible: 14, selected: 0, displayed: 0 } } as const;
    model = mergeTimeline(model, v2Timeline(observation, true));
    model = mergeTimeline(model, v2Timeline({ ...thought, groupId: 'think:2', explanation: 'Đã có lựa chọn để trả lời.' }));
    model = mergeTimeline(model, v2Timeline({ ...observation, counts: { ...observation.counts, selected: 3, displayed: 3 } }, true));
    const view = progressView(model, undefined, true);
    expect(view.steps.map((step) => step.label)).toEqual(['Phân tích yêu cầu', 'Tìm khách sạn ở Huế', 'Đánh giá kết quả']);
    expect(view.steps[2].lines).toEqual(['Đã có lựa chọn để trả lời.']);
    expect(view.steps.map((step) => step.tone)).toEqual(['think', 'action', 'think']);
    expect(view.steps[1].status).toBe('done');
    expect(view.steps[1].lines).toEqual(['14/20 kết quả phù hợp, chọn 3 để giới thiệu.']);
    expect(view.summary).toBe('Tìm khách sạn ở Huế');
    expect(view.steps.some((step) => /Think|Act|Observe|Hiểu yêu cầu/.test(step.label))).toBe(false);
  });

  it('shows how many candidates the assistant picked and why on the answering thought', () => {
    const pick = { groupId: 'think:2', kind: 'think', status: 'completed', taxonomy: null,
      explanation: 'Chọn mỗi kiểu trải nghiệm một nơi.', counts: { found: 40, eligible: 40, selected: 3, displayed: 3 } } as const;
    const step = progressView(mergeTimeline(emptyProgress(), v2Timeline(pick)), undefined, true).steps[0];
    expect(step.label).toBe('Chọn gợi ý');
    expect(step.lines).toEqual(['Chọn 3 trong 40 ứng viên đã xem.', 'Chọn mỗi kiểu trải nghiệm một nơi.']);
  });

  it('labels a repeated search of the same kind and place as seeing more, not a new task', () => {
    const first = { groupId: 'c1', kind: 'catalog', status: 'completed', outcome: 'ok', taxonomy: 'attraction',
      destination: 'TP. Hồ Chí Minh', counts: { found: 20, eligible: 20, selected: 0, displayed: 0 } } as const;
    let model = mergeTimeline(emptyProgress(), v2Timeline(first, true));
    model = mergeTimeline(model, v2Timeline({ ...first, groupId: 'c3', taxonomy: 'hotel' }, true));
    model = mergeTimeline(model, v2Timeline({ ...first, groupId: 'c4', status: 'running', outcome: undefined }));
    expect(progressView(model).steps.map((step) => step.label)).toEqual([
      'Tìm điểm tham quan ở TP. Hồ Chí Minh', 'Tìm khách sạn ở TP. Hồ Chí Minh',
      'Đang xem thêm điểm tham quan ở TP. Hồ Chí Minh…']);
  });

  it('keeps source errors distinct from empty results', () => {
    const data = { groupId: 'c1', kind: 'catalog', status: 'failed', taxonomy: null,
      outcome: 'error', counts: { found: 0, eligible: 0, selected: 0, displayed: 0 } } as const;
    const error = progressView(mergeTimeline(emptyProgress(), v2Timeline(data, true)));
    const empty = progressView(mergeTimeline(emptyProgress(), v2Timeline({ ...data, status: 'completed', outcome: 'empty' }, true)));
    expect(error.steps[0].lines.join(' ')).toContain('Chưa tra được');
    expect(empty.steps[0].lines.join(' ')).toContain('Chưa có kết quả phù hợp');
    expect(error.steps[0].status).toBe('pending');
  });

  it('preserves morning and afternoon times instead of assigning every activity to morning', () => {
    const final = JSON.parse(JSON.stringify(over)) as Final;
    final.itinerary!.days[0].activities[0].startMinute = 840;
    final.itinerary!.days[0].activities[0].endMinute = 900;
    const response = v2AsV1Response(final);
    if (response.status !== 'COMPLETED') throw new Error('expected a plan');
    expect(response.itinerary.days[0].slots[0].time).toBe('AFTERNOON');
    expect(convertItineraryCompletedToGroundedPlan(response).days[0].slots[0].note).toMatch(/^14:00–15:00/);
  });

  it('keeps unknown room counts unknown through the widget adapter', () => {
    const final = JSON.parse(JSON.stringify(over)) as Final;
    final.itinerary!.stays = [{ product: (answer30 as unknown as Final).recommendations.hotel[0], checkIn: '2026-10-24',
      checkOut: '2026-10-25', nights: 1, rooms: null }];
    const response = v2AsV1Response(final);
    if (response.status !== 'COMPLETED') throw new Error('expected a plan');
    expect(response.itinerary.stays![0].rooms).toBeUndefined();
    expect(response.itinerary.stays![0].note).toContain('Chưa xác định');
    expect(convertItineraryCompletedToGroundedPlan(response).stays![0].rooms).toBeUndefined();
  });
});
