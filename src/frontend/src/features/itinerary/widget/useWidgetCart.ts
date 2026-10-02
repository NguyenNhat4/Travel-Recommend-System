import { useEffect, useRef, useState } from 'react';
import { useAssistantCart } from '../../../hooks/useAssistantCart';
import type { WidgetPlan } from './widgetTypes';

export type CartAddState = 'adding' | 'added';

/** Phản hồi trên các nút của cùng sản phẩm, chỉ báo thành công sau response giỏ hàng. */
export function useWidgetCart() {
  const addItineraryToCart = useAssistantCart();
  const [cartAddStates, setCartAddStates] = useState<Record<string, CartAddState>>({});
  const states = useRef<Record<string, CartAddState>>({});
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const mounted = useRef(true);

  const update = (id: string, status?: CartAddState) => {
    if (!mounted.current) return;
    const next = { ...states.current };
    if (status) next[id] = status;
    else delete next[id];
    states.current = next;
    setCartAddStates(next);
  };

  useEffect(() => {
    mounted.current = true;
    const activeTimers = timers.current;
    return () => { mounted.current = false; activeTimers.forEach(clearTimeout); };
  }, []);

  const addPlanItemToCart = (plan: WidgetPlan, productId: string) => {
    if (states.current[productId]) return;
    const items = plan.cartItems.filter((item) => item.product.productId === productId);
    if (!items.length) return;
    void addItineraryToCart(items, undefined, {
      onStart: () => update(productId, 'adding'),
      onSettled: (added) => {
        if (!mounted.current) return;
        update(productId, added > 0 ? 'added' : undefined);
        if (added > 0) {
          const previous = timers.current.get(productId);
          if (previous) clearTimeout(previous);
          timers.current.set(productId, setTimeout(() => {
            update(productId);
            timers.current.delete(productId);
          }, 2500));
        }
      },
    });
  };

  return { addPlanItemToCart, cartAddStates };
}
