'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

/** Đã cuộn tới đầu / cuối hàng chưa. `tolerance` bù sai số làm tròn của trình duyệt (px). */
export function scrollEdges(scrollLeft: number, clientWidth: number, scrollWidth: number, tolerance = 2) {
  return {
    atStart: scrollLeft <= tolerance,
    atEnd: scrollLeft + clientWidth >= scrollWidth - tolerance,
  };
}

interface HScrollerProps {
  children: React.ReactNode;
  /** Số phần tử con; đổi thì đo lại vì nội dung tràn hay không có thể đổi. */
  count: number;
  label: string;
}

/**
 * Hàng cuộn ngang, hai nút trái/phải nằm giữa chiều cao hàng ở hai bên. Nút trái ẩn khi đang ở đầu hàng,
 * nút phải ẩn khi đã tới cuối hoặc hàng không tràn. Trên màn hình cảm ứng (dưới `md`) chỉ vuốt.
 */
export const HScroller: React.FC<HScrollerProps> = ({ children, count, label }) => {
  const trackRef = useRef<HTMLDivElement>(null);
  // Chưa đo thì ẩn cả hai nút, tránh nháy.
  const [edges, setEdges] = useState({ atStart: true, atEnd: true });

  const measure = useCallback(() => {
    const track = trackRef.current;
    if (!track) return;
    const next = scrollEdges(track.scrollLeft, track.clientWidth, track.scrollWidth);
    setEdges((prev) => (prev.atStart === next.atStart && prev.atEnd === next.atEnd ? prev : next));
  }, []);

  useEffect(() => {
    measure();
    const track = trackRef.current;
    if (!track || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(measure);
    observer.observe(track);
    return () => observer.disconnect();
  }, [measure, count]);

  const scrollBy = (direction: -1 | 1) => {
    const track = trackRef.current;
    if (track) track.scrollBy({ left: direction * track.clientWidth * 0.9, behavior: 'smooth' });
  };

  const buttonClass = 'absolute top-1/2 z-10 hidden h-10 w-10 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full border border-slate-200 bg-white text-slate-700 shadow-md transition hover:text-blue-600 active:scale-95 md:flex';

  return (
    <div className="relative" role="group" aria-label={label}>
      {!edges.atStart && (
        <button type="button" onClick={() => scrollBy(-1)} aria-label="Cuộn sang trái" className={`${buttonClass} left-2 lg:-left-5`}>
          <ChevronLeft className="h-5 w-5" aria-hidden="true" />
        </button>
      )}
      <div ref={trackRef} onScroll={measure} className="no-scrollbar flex snap-x gap-4 overflow-x-auto scroll-smooth pb-2">
        {children}
      </div>
      {!edges.atEnd && (
        <button type="button" onClick={() => scrollBy(1)} aria-label="Cuộn sang phải" className={`${buttonClass} right-2 lg:-right-5`}>
          <ChevronRight className="h-5 w-5" aria-hidden="true" />
        </button>
      )}
    </div>
  );
};
