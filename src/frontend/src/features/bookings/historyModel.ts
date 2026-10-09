/**
 * Mô hình của trang "Lịch sử đặt chỗ" (`/profile/booking_history`, FR-BKG-14): bộ lọc nằm trên URL, nhãn và ghi chú của thẻ đơn.
 * Toàn bộ là hàm thuần; Backend quyết định tab, lọc và đếm (`GET /bookings`), Web chỉ chọn cách hiển thị.
 */
import {
  FAILURE_REASON_TEXT, formatDateTimeVn, formatVnd,
} from '../../components/confirmation/bookingLabels';
import type { BookingSummary, BookingTab } from '../../services/booking';

export const HISTORY_PAGE_SIZE = 5;

export const BOOKING_TABS: ReadonlyArray<{ id: BookingTab; label: string }> = [
  { id: 'upcoming', label: 'Sắp đến' },
  { id: 'done', label: 'Hoàn thành' },
  { id: 'cancelled', label: 'Đã huỷ' },
];

/** Năm loại dịch vụ của V-OTA; nhãn khớp `TAXONOMY_TAG` ở trang tìm kiếm. */
export const SERVICE_FILTERS = [
  { id: 'ALL', label: 'Tất cả' },
  { id: 'hotel', label: 'Khách sạn' },
  { id: 'flight', label: 'Vé máy bay' },
  { id: 'attraction', label: 'Vé tham quan' },
  { id: 'combo', label: 'Combo' },
  { id: 'golf', label: 'Sân Golf' },
] as const;

export const SERVICE_LABEL: Record<string, string> = Object.fromEntries(SERVICE_FILTERS.map((f) => [f.id, f.label]));

export const DAY_OPTIONS = [
  { value: 0, label: 'Tất cả' },
  { value: 1, label: '1 ngày qua' },
  { value: 7, label: '7 ngày qua' },
  { value: 30, label: '30 ngày qua' },
  { value: 60, label: '60 ngày qua' },
] as const;

export type DaysFilter = (typeof DAY_OPTIONS)[number]['value'];

export interface HistoryFilters {
  tab: BookingTab;
  /** `ALL` hoặc một taxonomy. */
  taxonomy: string;
  days: DaysFilter;
  page: number;
}

export const DEFAULT_FILTERS: HistoryFilters = { tab: 'upcoming', taxonomy: 'ALL', days: 0, page: 1 };

/** Đọc bộ lọc từ URL; giá trị lạ về mặc định để một đường dẫn hỏng không làm trang lỗi. */
export function parseFilters(params: { get(name: string): string | null }): HistoryFilters {
  const tab = BOOKING_TABS.find((t) => t.id === params.get('tab'))?.id ?? DEFAULT_FILTERS.tab;
  const taxonomy = SERVICE_FILTERS.find((f) => f.id === params.get('taxonomy'))?.id ?? DEFAULT_FILTERS.taxonomy;
  const days = DAY_OPTIONS.find((d) => String(d.value) === params.get('days'))?.value ?? DEFAULT_FILTERS.days;
  const page = Number(params.get('page'));
  return { tab, taxonomy, days, page: Number.isInteger(page) && page >= 1 ? page : 1 };
}

/** Phần query của URL; bỏ mọi giá trị mặc định để đường dẫn mặc định gọn (`/profile/booking_history`). */
export function filtersToSearch(filters: HistoryFilters): string {
  const search = new URLSearchParams();
  if (filters.tab !== DEFAULT_FILTERS.tab) search.set('tab', filters.tab);
  if (filters.taxonomy !== 'ALL') search.set('taxonomy', filters.taxonomy);
  if (filters.days) search.set('days', String(filters.days));
  if (filters.page > 1) search.set('page', String(filters.page));
  const text = search.toString();
  return text ? `?${text}` : '';
}

export function isFiltered(filters: HistoryFilters): boolean {
  return filters.taxonomy !== 'ALL' || filters.days !== 0;
}

/** Số trang hiển thị: trang đầu, trang cuối và các trang sát trang hiện tại; chỗ hở là `'gap'`. */
export function visiblePages(current: number, total: number): Array<number | 'gap'> {
  const wanted = new Set([1, total, current - 1, current, current + 1].filter((p) => p >= 1 && p <= total));
  const out: Array<number | 'gap'> = [];
  let last = 0;
  for (const page of [...wanted].sort((a, b) => a - b)) {
    if (page - last > 1) out.push('gap');
    out.push(page);
    last = page;
  }
  return out;
}

export type Tone = 'ok' | 'warn' | 'bad' | 'off';

/** Đơn giữ chỗ đã quá hạn nằm ở tab Đã huỷ nhưng Backend vẫn để `status = PENDING_PAYMENT`; Web coi như hết hạn giữ chỗ. */
export function isHoldExpired(summary: BookingSummary): boolean {
  return summary.status === 'PENDING_PAYMENT' && summary.tab === 'cancelled';
}

export function cardStatus(summary: BookingSummary): { label: string; tone: Tone } {
  if (isHoldExpired(summary)) return { label: 'Hết hạn giữ chỗ', tone: 'off' };
  switch (summary.status) {
    case 'PENDING_PAYMENT': return { label: 'Chờ thanh toán', tone: 'warn' };
    case 'CONFIRMED': return summary.tab === 'done' ? { label: 'Hoàn thành', tone: 'ok' } : { label: 'Đã xác nhận', tone: 'ok' };
    case 'PAYMENT_FAILED': return { label: 'Thanh toán thất bại', tone: 'bad' };
    case 'EXPIRED': return { label: 'Hết hạn giữ chỗ', tone: 'off' };
    case 'CANCELLED': return { label: 'Đã huỷ', tone: 'off' };
  }
}

export interface CardNote { tone: Tone; title: string; text: string }

/** Dòng lý do dưới thẻ đơn; đơn đang bình thường không có ghi chú. */
export function cardNote(summary: BookingSummary): CardNote | null {
  if (isHoldExpired(summary) || summary.status === 'EXPIRED') {
    return { tone: 'off', title: 'Hết thời gian giữ chỗ', text: 'Đơn chưa thanh toán nên bạn không bị tính phí.' };
  }
  if (summary.status === 'PENDING_PAYMENT') {
    return {
      tone: 'warn', title: 'Đang giữ chỗ cho bạn',
      text: summary.holdExpiresAt
        ? `Giữ đến ${formatDateTimeVn(summary.holdExpiresAt)}. Thanh toán trước giờ này để giữ giá và chỗ.`
        : 'Thanh toán sớm để giữ giá và chỗ.',
    };
  }
  if (summary.status === 'PAYMENT_FAILED') {
    const reason = summary.paymentFailureReason ? FAILURE_REASON_TEXT[summary.paymentFailureReason] : 'Thanh toán không thành công.';
    return { tone: 'bad', title: 'Thanh toán không thành công', text: reason };
  }
  if (summary.status === 'CANCELLED') {
    switch (summary.paymentStatus) {
      case 'REFUNDED': return { tone: 'off', title: 'Bạn đã huỷ đơn này', text: `Khoản hoàn ${formatVnd(summary.total)} đã về thẻ của bạn.` };
      case 'REFUND_PENDING': return { tone: 'off', title: 'Bạn đã huỷ đơn này', text: `Đang hoàn ${formatVnd(summary.total)}. Tiền về thẻ trong 5–10 ngày làm việc.` };
      case 'REFUND_FAILED': return { tone: 'bad', title: 'Hoàn tiền đang gặp sự cố', text: 'X-OTA sẽ liên hệ với bạn để hoàn tất.' };
      default: return { tone: 'off', title: 'Bạn đã huỷ đơn này', text: 'Đơn chưa thanh toán nên không phát sinh hoàn tiền.' };
    }
  }
  return null;
}

/** Đơn có nút "Đặt lại" (FR-BKG-05): thanh toán thất bại hoặc hết hạn giữ chỗ. */
export function canRebook(summary: BookingSummary): boolean {
  return summary.status === 'PAYMENT_FAILED' || summary.status === 'EXPIRED' || isHoldExpired(summary);
}

export function itemSubtitle(item: BookingSummary['items'][number]): string {
  const dates = item.usingDateTo ? `${formatDay(item.usingDate)} – ${formatDay(item.usingDateTo)}` : formatDay(item.usingDate);
  const detail = item.nights ? `${item.nights} đêm` : item.taxonomy === 'combo' ? `${item.quantity} gói` : `${item.quantity} khách`;
  return `${SERVICE_LABEL[item.taxonomy] ?? item.taxonomy} · ${dates} · ${detail}`;
}

/** `2026-10-12` → `12/10/2026`, không qua `Date` để không lệch múi giờ. */
export function formatDay(iso: string): string {
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

export interface EmptyCopy { title: string; text: string; cta: { label: string; href: string } | null }

/** Lời nhắn của trạng thái trống: đổi theo tab và bộ lọc (FR-BKG-14, AC-BKG-19). */
export function emptyCopy(filters: HistoryFilters): EmptyCopy {
  if (isFiltered(filters)) {
    return { title: 'Không có đơn nào khớp bộ lọc.', text: 'Thử chọn khoảng ngày rộng hơn hoặc bỏ bớt bộ lọc dịch vụ.', cta: null };
  }
  const base = {
    upcoming: { title: 'Bạn chưa có chuyến đi nào.', text: 'Đặt chuyến đi đầu tiên, đơn của bạn sẽ hiện ở đây.' },
    done: { title: 'Bạn chưa hoàn thành chuyến đi nào.', text: 'Những chuyến đã đi sẽ được lưu lại ở đây để bạn xem và đặt lại.' },
    cancelled: { title: 'Bạn không có đơn nào đã huỷ.', text: 'Các đơn bị huỷ, hết hạn hoặc thất bại sẽ hiện ở đây.' },
  }[filters.tab];
  return { ...base, cta: filters.tab === 'cancelled' ? null : { label: 'Tìm khách sạn', href: '/hotels' } };
}
