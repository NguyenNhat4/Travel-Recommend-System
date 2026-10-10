import type { Tone } from './historyModel';

/** Màu theo ý nghĩa của nhãn và ghi chú; chữ luôn đi kèm màu nên không dựa riêng vào màu. */
export const TONE_PILL: Record<Tone, string> = {
  ok: 'bg-emerald-50 text-emerald-700',
  warn: 'bg-amber-50 text-amber-800',
  bad: 'bg-rose-50 text-rose-700',
  off: 'bg-slate-100 text-slate-600',
};
