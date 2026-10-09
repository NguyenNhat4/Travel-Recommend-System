'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ListChecks, UserRound } from 'lucide-react';
import { useTravel } from '../../context/TravelContext';
import { initialsOf } from './profileModel';

export const PROFILE_PATH = '/profile';
export const BOOKING_HISTORY_PATH = '/profile/booking_history';

const ITEMS = [
  { href: PROFILE_PATH, label: 'Hồ sơ cá nhân', Icon: UserRound },
  { href: BOOKING_HISTORY_PATH, label: 'Lịch sử đặt chỗ', Icon: ListChecks },
] as const;

/**
 * Khung chung của hai trang tài khoản: menu trái (thẻ người dùng, hai mục) trên máy tính, hai tab ngang trên điện thoại.
 * Mục đang mở dựa vào địa chỉ trang; `/profile/booking_history` không làm sáng `/profile`.
 */
export const AccountShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const pathname = usePathname() ?? PROFILE_PATH;
  const { currentPersona } = useTravel();
  return (
    <div className="mx-auto grid max-w-5xl gap-4 px-4 py-6 sm:px-6 md:grid-cols-[15rem_minmax(0,1fr)] md:gap-6 md:py-8">
      <aside className="grid content-start gap-3 md:sticky md:top-4">
        {currentPersona && (
          <div className="hidden items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3.5 md:flex">
            <span aria-hidden="true" className="grid h-11 w-11 flex-none place-items-center rounded-full bg-brand-600 text-[17px] font-bold text-white">
              {initialsOf(currentPersona.name)}
            </span>
            <div className="min-w-0">
              <b className="block break-words text-sm font-semibold text-slate-900">{currentPersona.name}</b>
              <span className="block break-words text-xs text-slate-500">{currentPersona.email}</span>
            </div>
          </div>
        )}
        <nav aria-label="Tài khoản" className="grid auto-cols-fr grid-flow-col gap-1 rounded-2xl border border-slate-200 bg-white p-1.5 md:grid-flow-row md:auto-cols-auto">
          {ITEMS.map(({ href, label, Icon }) => {
            const current = pathname === href;
            return (
              <Link
                key={href} href={href} aria-current={current ? 'page' : undefined}
                className={`flex min-h-11 items-center justify-center gap-2.5 rounded-xl px-3 text-sm transition-colors md:justify-start ${
                  current ? 'bg-brand-50 font-semibold text-brand-700' : 'font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <Icon className="h-[18px] w-[18px] flex-none" aria-hidden={true} />
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="min-w-0">{children}</main>
    </div>
  );
};
