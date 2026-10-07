'use client';

import React, { useEffect, useId, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { DAY_OPTIONS, type DaysFilter as DaysValue } from './historyModel';

interface DaysFilterProps {
  value: DaysValue;
  onChange: (value: DaysValue) => void;
}

/** Cần ít nhất chừng này chỗ trống bên dưới nút thì danh sách mở xuống; không thì lật lên. */
const PANEL_SPACE_PX = 300;

/**
 * Bộ lọc "Ngày đặt": nút và danh sách cùng một ngôn ngữ giao diện với các chip. Danh sách rộng bằng nút (tối thiểu 11 rem), mép phải
 * thẳng hàng với nút, mỗi dòng cao 44 px, dòng đang chọn có dấu tick và nền xanh. Bàn phím: Enter/Space/mũi tên mở; mũi tên, Home,
 * End di chuyển; Enter chọn; Esc đóng và trả focus; Tab ra ngoài thì đóng.
 */
export const DaysFilter: React.FC<DaysFilterProps> = ({ value, onChange }) => {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [openUp, setOpenUp] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const uid = useId();
  const listId = `${uid}-list`;
  const optionId = (index: number) => `${uid}-opt-${index}`;
  const selectedIndex = Math.max(0, DAY_OPTIONS.findIndex((option) => option.value === value));
  const selected = DAY_OPTIONS[selectedIndex];

  const show = () => {
    const rect = buttonRef.current?.getBoundingClientRect();
    setOpenUp(Boolean(rect) && window.innerHeight - rect!.bottom < PANEL_SPACE_PX && rect!.top > window.innerHeight - rect!.bottom);
    setActive(selectedIndex);
    setOpen(true);
  };
  const close = (returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) buttonRef.current?.focus();
  };
  const choose = (index: number) => {
    onChange(DAY_OPTIONS[index].value);
    close(true);
  };

  useEffect(() => {
    if (open) listRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  const onListKey = (event: React.KeyboardEvent) => {
    const last = DAY_OPTIONS.length - 1;
    switch (event.key) {
      case 'ArrowDown': event.preventDefault(); setActive((i) => Math.min(last, i + 1)); break;
      case 'ArrowUp': event.preventDefault(); setActive((i) => Math.max(0, i - 1)); break;
      case 'Home': event.preventDefault(); setActive(0); break;
      case 'End': event.preventDefault(); setActive(last); break;
      case 'Enter': case ' ': event.preventDefault(); choose(active); break;
      case 'Escape': event.preventDefault(); event.stopPropagation(); close(true); break;
      case 'Tab': setOpen(false); break;
      default:
    }
  };

  return (
    <div
      ref={wrapRef} className="relative flex items-center gap-2 text-[13px] text-slate-600 max-sm:w-full max-sm:justify-between"
      onBlur={(event) => { if (open && !wrapRef.current?.contains(event.relatedTarget as Node | null)) setOpen(false); }}
    >
      <span id={`${uid}-label`}>Ngày đặt</span>
      <button
        ref={buttonRef} type="button" aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? listId : undefined}
        aria-labelledby={`${uid}-label ${uid}-value`}
        onClick={() => (open ? close(false) : show())}
        onKeyDown={(event) => { if (!open && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) { event.preventDefault(); show(); } }}
        className={`inline-flex min-h-10 min-w-[8.5rem] items-center justify-between gap-2 rounded-full border bg-white px-3.5 text-[13px] font-medium text-slate-800 transition-colors hover:border-blue-600 ${
          open ? 'border-blue-600 ring-2 ring-blue-100' : 'border-slate-200'
        }`}
      >
        <span id={`${uid}-value`}>{selected.label}</span>
        <ChevronDown className={`h-4 w-4 flex-none text-slate-500 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>

      {open && (
        <ul
          ref={listRef} id={listId} role="listbox" tabIndex={-1} aria-labelledby={`${uid}-label`} aria-activedescendant={optionId(active)}
          onKeyDown={onListKey}
          className={`absolute right-0 z-20 w-[max(100%,11rem)] max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl outline-none ${
            openUp ? 'bottom-full mb-2' : 'top-full mt-2'
          } max-sm:w-full`}
        >
          {DAY_OPTIONS.map((option, index) => {
            const isSelected = option.value === value;
            return (
              <li
                key={option.value} id={optionId(index)} role="option" aria-selected={isSelected}
                onClick={() => choose(index)} onPointerEnter={() => setActive(index)}
                className={`flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-xl px-3 text-sm transition-colors ${
                  isSelected ? 'font-semibold text-blue-700' : 'font-medium text-slate-700'
                } ${index === active ? (isSelected ? 'bg-blue-100' : 'bg-slate-100') : isSelected ? 'bg-blue-50' : ''}`}
              >
                {option.label}
                {isSelected && <Check className="h-4 w-4 flex-none" aria-hidden="true" />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
