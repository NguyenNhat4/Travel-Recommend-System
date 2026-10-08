'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Calendar } from 'lucide-react';

const isoToDmy = (iso: string) => (iso ? iso.split('-').reverse().join('/') : '');

/** "dd/mm/yyyy" → ISO; null nếu chưa đủ hoặc không phải ngày có thật. */
function dmyToIso(text: string): string | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text);
  if (!m) return null;
  const iso = `${m[3]}-${m[2]}-${m[1]}`;
  const d = new Date(`${iso}T12:00:00Z`);
  return Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== iso ? null : iso;
}

/** Ô ngày dd/mm/yyyy (không phụ thuộc locale trình duyệt) kèm nút mở lịch; min/max chỉ ràng buộc trong lịch, lỗi do validateDates báo. */
export const DateInput: React.FC<{ label: string; value: string; min?: string; max?: string; onChange: (v: string) => void }> = ({
  label, value, min, max, onChange,
}) => {
  const [text, setText] = useState(isoToDmy(value));
  const picker = useRef<HTMLInputElement>(null);
  // Đồng bộ khi giá trị đổi từ ngoài (ngày mặc định, tự dời ngày trả); không ghi đè khi đang gõ dở.
  useEffect(() => { if (value !== (dmyToIso(text) ?? '')) setText(isoToDmy(value)); }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  const handleText = (raw: string) => {
    const digits = raw.replace(/\D/g, '').slice(0, 8);
    const masked = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)].filter(Boolean).join('/');
    setText(masked);
    onChange(dmyToIso(masked) ?? '');
  };
  return (
    <div>
      <label className="block text-[11px] font-bold text-slate-600 mb-1">{label}</label>
      <div className="relative">
        <input type="text" inputMode="numeric" placeholder="dd/mm/yyyy" value={text} maxLength={10} aria-label={label}
          onChange={(e) => handleText(e.target.value)}
          className="w-full pl-2.5 pr-8 py-1.5 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-brand-500" />
        <button type="button" aria-label={`Mở lịch ${label.toLowerCase()}`} onClick={() => picker.current?.showPicker?.()}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-brand-600">
          <Calendar className="w-4 h-4" />
        </button>
        <input ref={picker} type="date" tabIndex={-1} aria-hidden value={value} min={min} max={max}
          onChange={(e) => e.target.value && onChange(e.target.value)}
          className="absolute right-0 bottom-0 w-0 h-0 opacity-0 pointer-events-none" />
      </div>
    </div>
  );
};
