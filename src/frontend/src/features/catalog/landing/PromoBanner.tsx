'use client';

import React from 'react';
import { Sparkles } from 'lucide-react';
import { useAssistant } from '../../../context/AssistantProvider';
import type { VerticalConfig } from './verticals';

/** Lời mời sang trợ lý AI (tính năng thật của V-OTA); không mang khuyến mãi hay số liệu. */
export function PromoBanner({ promo, destination }: { promo: VerticalConfig['promo']; destination?: string }) {
  const { openFloatingWidget } = useAssistant();
  const message = destination ? `${promo.prompt} (${destination})` : promo.prompt;

  return (
    <section aria-label={promo.title} className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="relative flex min-h-64 items-center justify-between gap-6 overflow-hidden rounded-3xl bg-gradient-to-r from-brand-900 via-brand-800 to-brand-800 p-8 text-white sm:p-10">
        <div className="relative z-10 max-w-xl space-y-3">
          <p className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-bold uppercase tracking-wider">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            Trợ lý AI
          </p>
          <h2 className="type-title">{promo.title}</h2>
          <p className="text-sm leading-relaxed text-brand-100">{promo.body}</p>
          <button
            type="button"
            onClick={() => openFloatingWidget(message)}
            className="inline-flex h-11 items-center rounded-full bg-white px-5 text-sm font-bold text-brand-900 transition hover:bg-brand-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            {promo.cta}
          </button>
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
