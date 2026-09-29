import React from 'react';
import Link from 'next/link';
import { NavIcon } from './NavIcon';
import { categoryShortcuts, type NavGroupId } from './navConfig';

interface VerticalChipsProps {
  /** Nhóm đang xem; null ở Home. */
  activeGroup: NavGroupId | null;
  /** overlay: chip kính mờ trên ảnh hero. solid: chip trên nền sáng. */
  tone?: 'overlay' | 'solid';
}

/** Lối vào danh mục ở dưới 1024 px, nơi thanh nhóm của header bị ẩn (product.md §7.2 giữ tab bar dưới 5 mục). */
export function VerticalChips({ activeGroup, tone = 'overlay' }: VerticalChipsProps) {
  const chipClass = (active: boolean) => {
    const base = 'inline-flex h-11 items-center gap-1.5 rounded-full border px-4 text-sm font-semibold whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2';
    if (tone === 'overlay') {
      return `${base} focus-visible:outline-white ${active ? 'border-white bg-white text-slate-900' : 'border-white/40 bg-white/15 text-white backdrop-blur'}`;
    }
    return `${base} focus-visible:outline-blue-600 ${active ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white text-slate-700'}`;
  };

  return (
    <nav aria-label="Danh mục dịch vụ" className="no-scrollbar snap-row -mx-4 overflow-x-auto px-4 lg:hidden">
      <ul className="flex w-max gap-2">
        {categoryShortcuts().map((shortcut) => (
          <li key={shortcut.id}>
            <Link href={shortcut.href} aria-current={activeGroup === shortcut.id ? 'page' : undefined} className={chipClass(activeGroup === shortcut.id)}>
              <NavIcon name={shortcut.icon} />
              {shortcut.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
