'use client';

import React, { useEffect, useId, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import type { SortOption } from '../../services/search';

export const SORT_LABELS: Record<SortOption, string> = {
  relevance: 'Phù hợp nhất',
  price_asc: 'Giá thấp → cao',
  price_desc: 'Giá cao → thấp',
};

/** Nút "Sắp xếp" mở popup chọn một kiểu; đóng khi chọn, bấm ra ngoài hoặc nhấn Esc. */
export const SortMenu: React.FC<{ value: SortOption; onChange: (value: SortOption) => void }> = ({ value, onChange }) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-slate-300"
      >
        Sắp xếp: <span className="text-blue-700">{SORT_LABELS[value]}</span>
        <ChevronDown className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
      </button>
      {open && (
        <div id={menuId} role="menu" className="absolute right-0 top-full z-30 mt-1.5 w-56 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl">
          {(Object.keys(SORT_LABELS) as SortOption[]).map((option) => (
            <button
              key={option}
              type="button"
              role="menuitemradio"
              aria-checked={value === option}
              onClick={() => { onChange(option); setOpen(false); buttonRef.current?.focus(); }}
              className={`flex w-full cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-xs hover:bg-slate-100 ${value === option ? 'font-semibold text-blue-700' : 'text-slate-700'}`}
            >
              {SORT_LABELS[option]}
              {value === option && <Check className="h-3.5 w-3.5" aria-hidden="true" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
