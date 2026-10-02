// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import completed from '../../../shared/mocks/itinerary-agent/completed.json';
import { convertItineraryCompletedToGroundedPlan } from '../../src/features/itinerary/widget/widgetPlan';
import type { components } from '../../src/types/api.gen';
import { useWidgetCart } from '../../src/features/itinerary/widget/useWidgetCart';

const travel = vi.hoisted(() => ({
  addToCart: vi.fn(), currentPersona: { id: 'u1' } as { id: string } | null,
  openLoginModal: vi.fn(), showToast: vi.fn(), navigate: vi.fn(),
}));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

const plan = convertItineraryCompletedToGroundedPlan(completed as unknown as components['schemas']['ItineraryCompleted']);
const id = plan.cartItems[0].product.productId;

describe('widget cart feedback', () => {
  beforeEach(() => { vi.clearAllMocks(); vi.useFakeTimers(); travel.currentPersona = { id: 'u1' }; });
  afterEach(() => { cleanup(); vi.useRealTimers(); });

  it('blocks repeated clicks while pending and shows success only after the cart confirms it', async () => {
    let finish!: (ok: boolean) => void;
    travel.addToCart.mockReturnValue(new Promise<boolean>((resolve) => { finish = resolve; }));
    const { result } = renderHook(() => useWidgetCart());
    act(() => {
      result.current.addPlanItemToCart(plan, id);
      result.current.addPlanItemToCart(plan, id);
    });
    expect(travel.addToCart).toHaveBeenCalledTimes(1);
    expect(result.current.cartAddStates[id]).toBe('adding');
    await act(async () => { finish(true); });
    expect(result.current.cartAddStates[id]).toBe('added');
    act(() => result.current.addPlanItemToCart(plan, id));
    expect(travel.addToCart).toHaveBeenCalledTimes(1);
    act(() => vi.advanceTimersByTime(2500));
    expect(result.current.cartAddStates[id]).toBeUndefined();
  });

  it('does not show success for a failed request and lets the user retry', async () => {
    travel.addToCart.mockResolvedValue(false);
    const { result } = renderHook(() => useWidgetCart());
    await act(async () => result.current.addPlanItemToCart(plan, id));
    expect(result.current.cartAddStates[id]).toBeUndefined();
    await act(async () => result.current.addPlanItemToCart(plan, id));
    expect(travel.addToCart).toHaveBeenCalledTimes(2);
  });

  it('waits for login and the actual add before reporting success', async () => {
    travel.currentPersona = null;
    travel.addToCart.mockResolvedValue(true);
    const { result, rerender } = renderHook(() => useWidgetCart());
    await act(async () => result.current.addPlanItemToCart(plan, id));
    expect(travel.addToCart).not.toHaveBeenCalled();
    expect(result.current.cartAddStates[id]).toBeUndefined();
    travel.currentPersona = { id: 'u1' };
    rerender();
    await act(async () => travel.openLoginModal.mock.calls[0][0]());
    expect(travel.addToCart).toHaveBeenCalledTimes(1);
    expect(result.current.cartAddStates[id]).toBe('added');
  });
});
