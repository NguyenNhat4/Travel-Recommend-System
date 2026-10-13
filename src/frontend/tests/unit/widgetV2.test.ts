import { describe, expect, it } from 'vitest';
import answer30 from '../../../shared/mocks/assistant-v2/answer-30.json';
import over from '../../../shared/mocks/assistant-v2/itinerary-over.json';
import unknown from '../../../shared/mocks/assistant-v2/itinerary-unknown.json';
import type { components as V2 } from '../../src/types/assistant-v2.gen';
import { v2Actions, v2Activity, v2AsV1Response, v2Progress } from '../../src/features/itinerary/widget/widgetV2';
import { convertItineraryCompletedToGroundedPlan, narrationProducts } from '../../src/features/itinerary/widget/widgetPlan';

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

  it('turns real tool calls into progress with backend counts', () => {
    const data = { groupId: 'c3', kind: 'search', status: 'completed', taxonomy: 'hotel',
      counts: { found: 20, eligible: 14, selected: 3, displayed: 3 } } as const;
    expect(v2Activity({ ...data, status: 'running' })).toEqual({ nodeId: 'run_jobs', code: 'SEARCHING', groupId: 'job:3',
      kinds: ['hotel'] });
    expect(v2Progress(data).progress?.searches).toEqual([{ groupId: 'job:3', kind: 'hotel', status: 'ok',
      counts: { inScope: 14, chosen: 3 } }]);
    expect(v2Progress({ ...data, kind: 'itinerary' }).progress?.searches).toBeUndefined();
  });
});
