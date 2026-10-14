'use client';

import React, { useId } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useInView } from '../../../hooks/useInView';
import { coverFor } from './destinationCovers';
import { topDestinations, useDestinations } from './useDestinations';

interface DestinationTilesProps {
  title?: string;
  /** Route đích của mỗi ô: `{route}?destination={tên}`. Là dữ liệu thuần (không phải hàm) để truyền được từ Server Component. */
  route: string;
  /** Query cố định thêm vào mọi ô, ví dụ `{ type: 'golf' }`. */
  query?: Record<string, string>;
  limit?: number;
}

function tileHref(route: string, query: Record<string, string> | undefined, destination: string): string {
  const params = new URLSearchParams(query);
  params.set('destination', destination);
  return `${route}?${params.toString()}`;
}

/** Điểm đến phổ biến: `GET /destinations` chỉ gọi khi khối vào vùng nhìn, dùng chung bộ đệm với menu header. */
export function DestinationTiles({ title = 'Bạn muốn đi đâu?', route, query, limit = 5 }: DestinationTilesProps) {
  const headingId = useId();
  const [ref, inView] = useInView<HTMLElement>();
  const destinations = useDestinations(inView);
  const tiles = topDestinations(destinations.data, limit);

  if (!destinations.loading && inView && tiles.length === 0) return null;

  return (
    <section ref={ref} aria-labelledby={headingId} className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <h2 id={headingId} className="type-title mb-6 text-slate-900">{title}</h2>
      <div className="no-scrollbar snap-row -mx-4 flex gap-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
        {tiles.length === 0
          ? [0, 1, 2, 3, 4].map((i) => (
            <div key={i} aria-hidden="true" className="skeleton-wave h-64 w-44 shrink-0 rounded-xl sm:w-52 lg:w-[calc((100%-64px)/5)]" />
          ))
          : tiles.map((d) => {
            const cover = coverFor(d.destination);
            return (
              <Link
                key={d.destination}
                href={tileHref(route, query, d.destination)}
                className="group relative h-64 w-44 shrink-0 overflow-hidden rounded-xl bg-gradient-to-br from-brand-700 to-brand-900 shadow-md transition-shadow hover:shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 sm:w-52 lg:w-[calc((100%-64px)/5)]"
              >
                {cover && (
                  <Image
                    src={cover}
                    fill
                    sizes="176px"
                    alt=""
                    className="object-cover transition-transform duration-700 group-hover:scale-110"
                  />
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-slate-950/15 to-transparent" />
                <div className="absolute inset-x-0 bottom-4 px-3 text-center">
                  <h3 className="text-xl font-bold text-white drop-shadow-md">{d.destination}</h3>
                  <p className="mt-0.5 text-xs font-medium text-slate-200">{d.productCount.toLocaleString('vi-VN')} dịch vụ</p>
                </div>
              </Link>
            );
          })}
      </div>
    </section>
  );
}
