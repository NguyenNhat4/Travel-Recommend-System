'use client';

import React from 'react';
import Link from 'next/link';
import { ChevronDown } from 'lucide-react';
import { topDestinations, useDestinations } from '../../../features/catalog/landing/useDestinations';
import { MenuShell } from './MenuShell';
import { NavIcon } from './NavIcon';
import { NAV_ITEMS, isItemActive, itemsOf, type NavGroup, type NavItem } from './navConfig';

export type NavTone = 'overlay' | 'solid';
type ParamSource = { get(name: string): string | null };

/** Nút nhóm trên header: viên tròn, tô nền khi nhóm đang chọn. */
export function groupButtonClass(tone: NavTone, active: boolean): string {
  const base = 'inline-flex items-center gap-1 rounded-full px-3.5 py-2 text-sm font-semibold whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 cursor-pointer';
  if (tone === 'overlay') {
    return `${base} text-white focus-visible:outline-white ${active ? 'bg-white/25' : 'hover:bg-white/15'}`;
  }
  return `${base} focus-visible:outline-blue-600 ${active ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'}`;
}

function MenuItemLink({ item, active, onNavigate }: { item: NavItem; active: boolean; onNavigate: () => void }) {
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? 'page' : undefined}
      className={`flex items-start gap-3 rounded-2xl p-2.5 transition-colors hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-blue-600 ${active ? 'bg-blue-50' : ''}`}
    >
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-600">
        <NavIcon name={item.icon} />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-bold text-slate-900">{item.label}</span>
        <span className="block text-xs leading-snug text-slate-500">{item.description}</span>
      </span>
    </Link>
  );
}

interface NavMenuProps {
  group: NavGroup;
  active: boolean;
  tone: NavTone;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  align?: 'left' | 'right';
  pathname: string;
  params?: ParamSource;
}

export function NavMenu({ group, active, tone, open, onOpenChange, align, pathname, params }: NavMenuProps) {
  const destinations = useDestinations(open);
  const chips = topDestinations(destinations.data, 6);
  const showDestinations = destinations.loading || chips.length > 0;

  return (
    <MenuShell
      open={open}
      onOpenChange={onOpenChange}
      align={align}
      panelLabel={group.label}
      buttonClassName={groupButtonClass(tone, active)}
      button={(
        <>
          {group.label}
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
        </>
      )}
    >
      <div className={`grid gap-4 ${showDestinations ? 'md:grid-cols-[minmax(0,1fr)_minmax(0,13rem)]' : ''}`}>
        <ul className="space-y-1">
          {itemsOf(group).map((item) => (
            <li key={item.id}>
              <MenuItemLink item={item} active={isItemActive(item, pathname, params)} onNavigate={() => onOpenChange(false)} />
            </li>
          ))}
        </ul>
        {showDestinations && (
          <div className="border-t border-slate-200 pt-3 md:border-l md:border-t-0 md:pl-4 md:pt-0">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">Điểm đến phổ biến</p>
            <div className="flex flex-wrap gap-1.5">
              {destinations.loading && chips.length === 0
                ? [0, 1, 2, 3].map((i) => <span key={i} aria-hidden="true" className="skeleton-wave h-8 w-20 rounded-full" />)
                : chips.map((d) => (
                  <Link
                    key={d.destination}
                    href={`${group.destinationRoute}?destination=${encodeURIComponent(d.destination)}`}
                    onClick={() => onOpenChange(false)}
                    className="inline-flex h-8 items-center rounded-full border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition-colors hover:border-blue-300 hover:text-blue-700 focus-visible:outline-2 focus-visible:outline-blue-600"
                  >
                    {d.destination}
                  </Link>
                ))}
            </div>
          </div>
        )}
      </div>
    </MenuShell>
  );
}

interface AllServicesMenuProps {
  tone: NavTone;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pathname: string;
  params?: ParamSource;
}

/** Nút lưới bốn chấm của mẫu: mọi dịch vụ trong một panel. */
export function AllServicesMenu({ tone, open, onOpenChange, pathname, params }: AllServicesMenuProps) {
  const buttonClass = `grid h-10 w-10 place-items-center rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 cursor-pointer ${
    tone === 'overlay' ? 'text-white hover:bg-white/15 focus-visible:outline-white' : 'text-slate-700 hover:bg-slate-100 focus-visible:outline-blue-600'
  }`;
  return (
    <MenuShell
      open={open}
      onOpenChange={onOpenChange}
      align="right"
      panelLabel="Tất cả dịch vụ"
      buttonLabel="Tất cả dịch vụ"
      buttonClassName={buttonClass}
      button={(
        <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
          <circle cx="6.5" cy="6.3" r="4.2" />
          <circle cx="6.5" cy="17.3" r="4.2" />
          <circle cx="17.5" cy="6.3" r="4.2" />
          <rect x="13.4" y="13.2" width="8.2" height="8.2" rx="2.2" transform="rotate(45 17.5 17.3)" opacity="0.55" />
        </svg>
      )}
    >
      <ul className="grid gap-1 sm:grid-cols-2">
        {NAV_ITEMS.map((item) => (
          <li key={item.id}>
            <MenuItemLink item={item} active={isItemActive(item, pathname, params)} onNavigate={() => onOpenChange(false)} />
          </li>
        ))}
      </ul>
    </MenuShell>
  );
}
