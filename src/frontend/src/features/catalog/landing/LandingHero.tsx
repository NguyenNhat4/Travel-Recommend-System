import React from 'react';
import Link from 'next/link';
import { VerticalChips } from '../../../components/layout/nav/VerticalChips';
import type { NavGroupId } from '../../../components/layout/nav/navConfig';
import { LandingSearchSheet } from './LandingSearchSheet';
import type { VerticalConfig, VerticalTab } from './verticals';

interface LandingHeroProps {
  config: VerticalConfig;
  tab: VerticalTab;
  activeGroup: NavGroupId | null;
  destination?: string;
}

/**
 * Hero ~500 px: ảnh nền + lớp phủ tối 36%, tiêu đề, (tab loại dịch vụ), tấm tìm kiếm. Header nổi (fixed) đè lên phần đầu
 * nên hero chừa `pt-28`. Khối nội dung `z-30` để popover của tấm tìm kiếm nằm trên tờ nền trắng bên dưới.
 */
export function LandingHero({ config, tab, activeGroup, destination }: LandingHeroProps) {
  const tabHref = (taxonomy: string) => {
    const params = new URLSearchParams();
    if (taxonomy !== config.tabs[0].taxonomy) params.set('type', taxonomy);
    if (destination) params.set('destination', destination);
    const query = params.toString();
    return query ? `${config.route}?${query}` : config.route;
  };

  return (
    <section className="relative flex min-h-[520px] items-end pb-14 pt-28 lg:min-h-[500px] lg:pb-16">
      <div className="absolute inset-0 overflow-hidden bg-slate-800">
        <img src={config.heroImage} alt="" fetchPriority="high" loading="eager" decoding="async" className="h-full w-full object-cover object-center" />
        <div className="absolute inset-0 bg-black/36" />
      </div>

      <div className="relative z-30 mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 sm:px-6 lg:px-8">
        <VerticalChips activeGroup={activeGroup} />
        <div>
          <h1 className="type-hero text-white drop-shadow">{config.title}</h1>
          <p className="type-hero-sub mt-3 max-w-2xl text-white/90 drop-shadow">{config.subtitle}</p>
        </div>

        {config.tabs.length > 1 && (
          <nav aria-label="Loại dịch vụ">
            <ul className="flex flex-wrap gap-2">
              {config.tabs.map((item) => {
                const active = item.taxonomy === tab.taxonomy;
                return (
                  <li key={item.taxonomy}>
                    <Link
                      href={tabHref(item.taxonomy)}
                      aria-current={active ? 'page' : undefined}
                      className={`inline-flex h-11 items-center rounded-full border px-5 font-display text-sm tracking-[0.01em] transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${
                        active ? 'border-white bg-white text-slate-900' : 'border-white/40 bg-white/15 text-white backdrop-blur hover:bg-white/25'
                      }`}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        )}

        <LandingSearchSheet config={config} tab={tab} initialDestination={destination} />
      </div>
    </section>
  );
}
