'use client';

import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { visiblePages } from './historyModel';

interface HistoryPaginationProps {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
  onPage: (page: number) => void;
}

const BUTTON = 'grid h-11 min-w-11 place-items-center rounded-xl px-2 text-sm font-medium tabular-nums transition-colors';

/** Phân trang đánh số: trang đầu, trang cuối, các trang sát trang hiện tại; ẩn khi chỉ có một trang (FR-BKG-14). */
export const HistoryPagination: React.FC<HistoryPaginationProps> = ({ page, pageSize, totalItems, totalPages, onPage }) => {
  if (totalPages <= 1) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, totalItems);
  return (
    <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
      <p className="text-[13px] text-slate-500 tabular-nums">Hiển thị {from}–{to} trong {totalItems} đơn</p>
      <nav aria-label="Phân trang" className="flex flex-wrap items-center gap-1">
        <button
          type="button" aria-label="Trang trước" disabled={page <= 1} onClick={() => onPage(page - 1)}
          className={`${BUTTON} text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-transparent`}
        >
          <ChevronLeft className="h-[18px] w-[18px]" aria-hidden="true" />
        </button>
        {visiblePages(page, totalPages).map((item, index) => item === 'gap' ? (
          <span key={`gap-${index}`} aria-hidden="true" className="w-6 text-center text-slate-400">…</span>
        ) : (
          <button
            key={item} type="button" aria-label={`Trang ${item}`} aria-current={item === page ? 'page' : undefined}
            onClick={() => onPage(item)}
            className={`${BUTTON} ${item === page ? 'bg-brand-600 text-white' : 'text-slate-700 hover:bg-slate-100'}`}
          >
            {item}
          </button>
        ))}
        <button
          type="button" aria-label="Trang sau" disabled={page >= totalPages} onClick={() => onPage(page + 1)}
          className={`${BUTTON} text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-transparent`}
        >
          <ChevronRight className="h-[18px] w-[18px]" aria-hidden="true" />
        </button>
      </nav>
    </div>
  );
};
