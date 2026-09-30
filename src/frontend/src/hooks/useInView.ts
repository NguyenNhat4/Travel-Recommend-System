'use client';

import { useEffect, useRef, useState } from 'react';

export interface UseInViewOptions {
  /** Vào vùng nhìn sớm hơn viền màn hình một đoạn, để dữ liệu kịp về trước khi người dùng cuộn tới. */
  rootMargin?: string;
  /** true: đã vào vùng nhìn một lần thì giữ nguyên (dùng cho tải lười). */
  once?: boolean;
}

/**
 * `inView` = true khi phần tử gắn `ref` nằm trong vùng nhìn cộng `rootMargin`.
 * Không có IntersectionObserver (server render, jsdom) thì coi như đã vào vùng nhìn để nội dung vẫn tải.
 */
export function useInView<T extends Element = HTMLDivElement>({ rootMargin = '300px', once = true }: UseInViewOptions = {}) {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (typeof IntersectionObserver === 'undefined') {
      setInView(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          setInView(true);
          if (once) observer.disconnect();
        } else if (!once) {
          setInView(false);
        }
      }
    }, { rootMargin });
    observer.observe(element);
    return () => observer.disconnect();
  }, [rootMargin, once]);

  return [ref, inView] as const;
}
