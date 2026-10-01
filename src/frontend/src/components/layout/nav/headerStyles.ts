/**
 * Kích thước và hình dạng dùng chung cho mọi điều khiển trên header (nhóm dịch vụ, nút lưới, ngôn ngữ, giỏ, tài khoản,
 * đăng nhập) để không có cái to cái nhỏ không chủ đích. Không import React: chỉ chuỗi class, test được trong môi trường node.
 *
 * - Cao 40 px (44 px trên màn cảm ứng, `pointer-coarse`), bo tròn hoàn toàn, chữ Cal Sans 14 px, khoảng cách bậc 4/8 px.
 * - Đệm ngang 12 px, 16 px từ 1280 px. Khoảng 1024–1279 px chật (bốn nhóm dịch vụ chiếm ~510 px) nên Header ẩn thêm chữ V-OTA,
 *   nút lưới và mã tiền tệ ở khoảng đó.
 * - Viên header cao 64 px (56 px trên mobile) nên điều khiển cách mép 12 px (8 px): bo đồng tâm với viên ngoài.
 * - Ba mức nhấn: mặc định (trong suốt, chỉ đổi nền khi rê), chip (nền nhạt, dành cho tài khoản) và chính (nền xanh, Đăng ký).
 */
export type NavTone = 'overlay' | 'solid';

const BASE =
  'inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-full font-display text-sm leading-none tracking-[0.01em] whitespace-nowrap ' +
  'transition-colors duration-200 cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 pointer-coarse:h-11';

interface ControlOptions {
  /** Đang ở nhóm/route này hoặc menu của nó đang mở. */
  active?: boolean;
  /** Chỉ có icon: hình tròn 40 px. */
  iconOnly?: boolean;
  /** Đệm ngang 12 px ở mọi cỡ, cho nút gồm nhiều phần nhỏ (cờ + mã tiền tệ + mũi tên). */
  compact?: boolean;
}

/** Mức mặc định: nút nhóm dịch vụ, nút lưới, ngôn ngữ, giỏ, Đăng nhập. */
export function controlClass(tone: NavTone, { active = false, iconOnly = false, compact = false }: ControlOptions = {}): string {
  const size = iconOnly ? 'w-10 pointer-coarse:w-11' : compact ? 'px-3' : 'px-3 xl:px-4';
  if (tone === 'overlay') {
    return `${BASE} ${size} text-white focus-visible:outline-white ${active ? 'bg-white/25' : 'hover:bg-white/15'}`;
  }
  return `${BASE} ${size} focus-visible:outline-blue-600 ${active ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'}`;
}

/** Chip nền nhạt có avatar bên trái (đệm trái 4 px để avatar 32 px cách mép đều 4 px). */
export function chipClass(tone: NavTone): string {
  if (tone === 'overlay') return `${BASE} pl-1 pr-3 bg-white/15 text-white hover:bg-white/25 focus-visible:outline-white`;
  return `${BASE} pl-1 pr-3 bg-slate-100 text-slate-900 hover:bg-slate-200 focus-visible:outline-blue-600`;
}

/** Hành động chính duy nhất trên header khi chưa đăng nhập. */
export function primaryClass(): string {
  return `${BASE} px-5 bg-blue-600 text-white hover:bg-blue-700 focus-visible:outline-blue-600`;
}

/** Vỏ chung của mọi panel thả xuống từ header: bo 24 px, đệm 8 px, hàng con bo 16 px. */
export const PANEL_CLASS =
  'glass-panel max-w-[calc(100vw-1.5rem)] rounded-3xl border border-white/60 p-2 text-slate-800 shadow-2xl ring-1 ring-slate-900/5';

const ROW_BASE =
  'flex min-h-11 w-full cursor-pointer rounded-2xl px-3 py-2 text-left text-sm transition-colors duration-200 ' +
  'focus-visible:outline-2 focus-visible:outline-blue-600';

const ROW_VARIANT = {
  default: 'text-slate-700 hover:bg-slate-100',
  selected: 'bg-blue-50 text-blue-800',
  accent: 'font-semibold text-blue-600 hover:bg-blue-50',
  danger: 'font-semibold text-rose-600 hover:bg-rose-50',
} as const;

/** Hàng trong panel (menu ngôn ngữ, đặt chỗ, tài khoản): cao ≥ 44 px, chữ 14 px. `stacked`: hai dòng chữ xếp dọc. */
export function rowClass(variant: keyof typeof ROW_VARIANT = 'default', { stacked = false } = {}): string {
  return `${ROW_BASE} ${stacked ? 'flex-col items-stretch gap-0.5' : 'items-center gap-3'} ${ROW_VARIANT[variant]}`;
}

/** Nhãn nhóm nhỏ trong panel: chữ Inter 12 px in hoa, không dùng Cal Sans ở cỡ này. */
export const PANEL_LABEL_CLASS = 'px-3 pb-1 pt-2 font-sans text-xs font-semibold uppercase tracking-wider text-slate-400';
