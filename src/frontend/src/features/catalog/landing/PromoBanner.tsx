import React from 'react';
import Link from 'next/link';
import { Sparkles } from 'lucide-react';
import type { VerticalConfig } from './verticals';

/** Lời mời sang trợ lý AI (tính năng thật của V-OTA); không mang khuyến mãi hay số liệu. */
export function PromoBanner({ promo, destination }: { promo: VerticalConfig['promo']; destination?: string }) {
  const params = new URLSearchParams({ q: promo.prompt });
  if (destination) params.set('destination', destination);

  return (
    <section aria-label={promo.title} className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="relative flex min-h-64 items-center justify-between gap-6 overflow-hidden rounded-3xl bg-gradient-to-r from-blue-900 via-blue-800 to-indigo-800 p-8 text-white sm:p-10">
        <div className="relative z-10 max-w-xl space-y-3">
          <p className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-bold uppercase tracking-wider">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            Trợ lý AI
          </p>
          <h2 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{promo.title}</h2>
          <p className="text-sm leading-relaxed text-blue-100">{promo.body}</p>
          <Link
            href={`/assistant?${params.toString()}`}
            className="inline-flex h-11 items-center rounded-full bg-white px-5 text-sm font-bold text-blue-900 transition hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            {promo.cta}
          </Link>
        </div>
        <img
          src="/mascot_welcome.webp"
          alt=""
          loading="lazy"
          decoding="async"
          className="pointer-events-none relative z-10 hidden h-44 w-auto shrink-0 sm:block"
        />
      </div>
    </section>
  );
}
