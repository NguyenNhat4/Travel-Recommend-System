'use client';

/** Các mảnh giao diện dùng chung của ba bước checkout (spec checkout-nhieu-buoc-hanh-khach.md §6.2, §6.3, §6.11). */
import React from 'react';
import { AlertTriangle, Check, CircleAlert, Loader2, Minus, Plus } from 'lucide-react';
import { STEPS, type CheckoutController } from './useCheckout';
import type { Step, SummaryEntry } from './serverErrors';

export const cardClass = 'bg-white p-5 sm:p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4';
export const inputClass = (invalid: boolean) =>
  `w-full px-3 h-10 text-sm rounded-lg border outline-hidden focus:ring-2 focus:ring-brand-500 transition-colors ${
    invalid ? 'border-rose-400 bg-rose-50' : 'border-slate-300 bg-white'}`;

export const SectionTitle: React.FC<{ title: string; extra?: React.ReactNode }> = ({ title, extra }) => (
  <div className="flex items-center justify-between gap-3 pb-3 border-b border-slate-100">
    <h3 className="text-sm font-bold text-slate-900 tracking-wide uppercase">{title}</h3>
    {extra}
  </div>
);

/** Ô nhập kèm nhãn, gợi ý và lỗi nối với ô qua `aria-describedby` (§6.11). */
export const Field: React.FC<{
  id: string; label: string; error?: string; hint?: string; children: (props: { id: string; 'aria-invalid': boolean; 'aria-describedby': string }) => React.ReactNode;
}> = ({ id, label, error, hint, children }) => (
  <div className="space-y-1">
    <label htmlFor={id} className="block text-xs font-semibold text-slate-700">{label}</label>
    {children({ id, 'aria-invalid': Boolean(error), 'aria-describedby': `h-${id} e-${id}` })}
    <p id={`h-${id}`} className="text-xs text-emerald-700" hidden={!hint}>{hint}</p>
    <p id={`e-${id}`} aria-live="polite" className="text-xs text-rose-600 font-medium" hidden={!error}>{error}</p>
  </div>
);

export const Skeleton: React.FC<{ width: number }> = ({ width }) => (
  <span className="inline-block h-4 align-middle rounded-md bg-slate-200 animate-pulse" style={{ width }} role="status" aria-label="Đang cập nhật giá" />
);

/** Thanh bước: bước đã xong có dấu ✓ và bấm được để quay lại; bước hiện tại tô đậm; bước chưa tới không bấm được. */
export const Stepper: React.FC<{ ctl: CheckoutController }> = ({ ctl }) => {
  const current = STEPS.findIndex((s) => s.key === ctl.step);
  const isDone = (key: Step) => (key === 'travelers' ? ctl.done.travelers : key === 'services' ? ctl.done.services : false);
  return (
    <nav aria-label="Các bước thanh toán">
      <div className="text-[11px] font-semibold text-slate-500 mb-2 lg:hidden">Bước {current + 1}/{STEPS.length}</div>
      <ol className="flex items-center gap-2">
        {STEPS.map(({ key, label }, i) => {
          const isCurrent = i === current;
          const done = !isCurrent && isDone(key);
          const reachable = !isCurrent && (i < current || STEPS.slice(0, i).every((s) => isDone(s.key)));
          const dot = done ? (
            <span className="w-7 h-7 rounded-full bg-emerald-500 text-white flex items-center justify-center shrink-0"><Check className="w-4 h-4" aria-hidden="true" /></span>
          ) : (
            <span className={`w-7 h-7 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ${isCurrent ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500'}`}>{i + 1}</span>
          );
          const text = (
            <span className={`${isCurrent ? '' : 'sr-only lg:not-sr-only'} text-xs sm:text-sm whitespace-nowrap ${isCurrent ? 'font-bold text-slate-900' : done ? 'font-semibold text-slate-700' : 'text-slate-500'}`}>
              {label}
            </span>
          );
          return (
            <li key={key} className={`flex items-center gap-2 ${i < STEPS.length - 1 ? 'flex-1' : ''}`} aria-current={isCurrent ? 'step' : undefined}>
              {reachable ? (
                <button type="button" onClick={() => ctl.goto(key)} className="flex items-center gap-2 rounded-lg hover:bg-slate-50 pr-2">{dot}{text}</button>
              ) : (
                <span className="flex items-center gap-2">{dot}{text}</span>
              )}
              {i < STEPS.length - 1 && <span className={`flex-1 h-0.5 rounded min-w-4 ${isDone(key) ? 'bg-emerald-400' : 'bg-slate-200'}`} aria-hidden="true" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};

/** Hộp tóm tắt lỗi ở đầu bước: "Còn n thông tin cần sửa", mỗi dòng là một link tới trường lỗi (AC-BKG-07). */
export const ErrorSummaryBox: React.FC<{ entries: SummaryEntry[]; onJump: (targetId: string) => void }> = ({ entries, onJump }) => {
  if (!entries.length) return null;
  return (
    <div id="error-summary" role="alert" tabIndex={-1} className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm">
      <div className="font-bold text-rose-800 flex items-center gap-2"><CircleAlert className="w-4 h-4" aria-hidden="true" />Còn {entries.length} thông tin cần sửa</div>
      <ul className="mt-2 space-y-1 list-disc pl-6 text-rose-700 text-xs sm:text-sm">
        {entries.map((entry, i) => (
          <li key={`${entry.targetId}-${i}`}>
            <a href={`#${entry.targetId}`} onClick={(e) => { e.preventDefault(); onJump(entry.targetId); }} className="underline underline-offset-2 hover:text-rose-900">
              {entry.where ? `${entry.where}: ` : ''}{entry.message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
};

export const Notice: React.FC<{ tone?: 'info' | 'warn'; children: React.ReactNode }> = ({ tone = 'warn', children }) => (
  <div role="status" className={`rounded-xl border px-4 py-3 text-sm flex items-start gap-2 ${tone === 'warn' ? 'border-amber-300 bg-amber-50 text-amber-900' : 'border-brand-100 bg-brand-50 text-brand-900'}`}>
    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
    <span>{children}</span>
  </div>
);

/** Bộ đếm − n +. Nút có nhãn đọc được, số hiện tại đọc qua `aria-live` (§6.11). */
export const CounterRow: React.FC<{
  label: string; hint: string; value: number; canDec: boolean; canInc: boolean; decLabel: string; incLabel: string;
  onDec: () => void; onInc: () => void; id?: string;
}> = ({ label, hint, value, canDec, canInc, decLabel, incLabel, onDec, onInc, id }) => {
  const button = 'w-9 h-9 rounded-full border border-slate-300 text-slate-700 flex items-center justify-center hover:border-brand-500 hover:text-brand-600 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-slate-300 disabled:hover:text-slate-700';
  return (
    <div className="flex items-center justify-between gap-4 py-3" id={id}>
      <div>
        <div className="text-sm font-semibold text-slate-900">{label}</div>
        <div className="text-xs text-slate-500">{hint}</div>
      </div>
      <div className="flex items-center gap-3">
        <button type="button" onClick={onDec} disabled={!canDec} aria-label={decLabel} className={button}><Minus className="w-4 h-4" aria-hidden="true" /></button>
        <span className="w-6 text-center text-base font-bold tabular-nums" aria-live="polite">{value}</span>
        <button type="button" onClick={onInc} disabled={!canInc} aria-label={incLabel} className={button}><Plus className="w-4 h-4" aria-hidden="true" /></button>
      </div>
    </div>
  );
};

export const PrimaryButton: React.FC<{
  onClick: () => void; disabled?: boolean; busy?: string | null; children: React.ReactNode; full?: boolean; type?: 'button' | 'submit';
}> = ({ onClick, disabled, busy, children, full, type = 'button' }) => (
  <button
    type={type} onClick={onClick} disabled={disabled || Boolean(busy)}
    className={`${full ? 'w-full' : 'px-6'} py-3 bg-brand-600 hover:bg-brand-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white font-bold text-sm rounded-xl shadow-md transition-colors inline-flex items-center justify-center gap-2`}
  >
    {busy ? (<><Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /><span>{busy}</span></>) : children}
  </button>
);
