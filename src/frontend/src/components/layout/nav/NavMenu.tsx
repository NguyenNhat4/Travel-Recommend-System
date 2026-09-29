'use client';

import React, { useId } from 'react';
import Link from 'next/link';
import { ChevronDown } from 'lucide-react';
import { MenuShell } from './MenuShell';
import { NavIcon } from './NavIcon';
import { NAV_GROUPS, isItemActive, itemsOf, type NavGroup, type NavItem } from './navConfig';
import { PANEL_LABEL_CLASS, controlClass, type NavTone } from './headerStyles';

type ParamSource = { get(name: string): string | null };

/** Một dịch vụ trong menu: ô icon 40 px, tên (Cal Sans 15 px) và một dòng mô tả tĩnh (Inter 13 px). */
function MenuItemLink({ item, active, onNavigate }: { item: NavItem; active: boolean; onNavigate: () => void }) {
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? 'page' : undefined}
      className={`flex items-center gap-3 rounded-2xl p-3 transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-blue-600 ${
        active ? 'bg-blue-50' : 'hover:bg-slate-100'
      }`}
    >
      <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl text-blue-600 ${active ? 'bg-white shadow-xs' : 'bg-blue-50'}`}>
        <NavIcon name={item.icon} className="h-5 w-5" />
      </span>
      <span className="min-w-0">
        <span className="block font-display text-[15px] leading-5 text-slate-900">{item.label}</span>
        <span className="block text-[13px] leading-[18px] text-slate-500">{item.description}</span>
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
  align?: 'left' | 'center' | 'right';
  pathname: string;
  params?: ParamSource;
}

/** Nút nhóm trên header và menu con chỉ liệt kê dịch vụ của nhóm (không có điểm đến: điểm đến nằm ở tấm tìm kiếm và trang danh mục). */
export function NavMenu({ group, active, tone, open, onOpenChange, align, pathname, params }: NavMenuProps) {
  return (
    <MenuShell
      open={open}
      onOpenChange={onOpenChange}
      align={align}
      panelLabel={group.label}
      buttonClassName={controlClass(tone, { active: active || open })}
      button={(
        <>
          {group.label}
          <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
        </>
      )}
    >
      <ul className="space-y-1">
        {itemsOf(group).map((item) => (
          <li key={item.id}>
            <MenuItemLink item={item} active={isItemActive(item, pathname, params)} onNavigate={() => onOpenChange(false)} />
          </li>
        ))}
      </ul>
    </MenuShell>
  );
}

interface AllServicesMenuProps {
  tone: NavTone;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pathname: string;
  params?: ParamSource;
  className?: string;
}

/** Nút lưới bốn chấm của mẫu: mọi dịch vụ trong một panel, xếp theo bốn nhóm của header. */
export function AllServicesMenu({ tone, open, onOpenChange, pathname, params, className }: AllServicesMenuProps) {
  const uid = useId();
  return (
    <MenuShell
      open={open}
      onOpenChange={onOpenChange}
      align="right"
      panelLabel="Tất cả dịch vụ"
      buttonLabel="Tất cả dịch vụ"
      panelWidthClass="w-[min(calc(100vw-1.5rem),38rem)]"
      wrapperClassName={className}
      buttonClassName={controlClass(tone, { active: open, iconOnly: true })}
      button={(
        <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
          <circle cx="6.5" cy="6.3" r="4.2" />
          <circle cx="6.5" cy="17.3" r="4.2" />
          <circle cx="17.5" cy="6.3" r="4.2" />
          <rect x="13.4" y="13.2" width="8.2" height="8.2" rx="2.2" transform="rotate(45 17.5 17.3)" opacity="0.55" />
        </svg>
      )}
    >
      <div className="grid gap-x-2 gap-y-1 sm:grid-cols-2">
        {NAV_GROUPS.map((group) => (
          <div key={group.id}>
            <p id={`${uid}-${group.id}`} className={PANEL_LABEL_CLASS}>{group.label}</p>
            <ul aria-labelledby={`${uid}-${group.id}`} className="space-y-1">
              {itemsOf(group).map((item) => (
                <li key={item.id}>
                  <MenuItemLink item={item} active={isItemActive(item, pathname, params)} onNavigate={() => onOpenChange(false)} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </MenuShell>
  );
}
