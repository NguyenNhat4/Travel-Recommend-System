/** Định dạng hiển thị của trang kết quả vé máy bay. Ngày là YYYY-MM-DD theo giờ Việt Nam; không đổi múi giờ. */
import { addDaysIso } from '../../search/tripContext';

const WEEKDAY_SHORT = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'] as const;
const WEEKDAY_LONG = ['Chủ nhật', 'Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7'] as const;

const weekday = (iso: string): number => new Date(`${iso}T00:00:00Z`).getUTCDay();

/** "02/10" */
export const shortDate = (iso: string): string => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

export const weekdayLong = (iso: string): string => WEEKDAY_LONG[weekday(iso)];

/** "T6, 02/10"; `offsetDays` cho giờ đến qua nửa đêm. */
export function dayTag(iso: string, offsetDays = 0): string {
  const day = offsetDays ? addDaysIso(iso, offsetDays) : iso;
  return `${WEEKDAY_SHORT[weekday(day)]}, ${shortDate(day)}`;
}

/** "1.493.000" */
export const groupDigits = (amount: number): string => new Intl.NumberFormat('vi-VN').format(amount);

/** "1.493k": giá tròn nghìn cho dải ngày. */
export const thousands = (amount: number): string => `${groupDigits(Math.floor(amount / 1000))}k`;

/** "02/10/2026" từ một mốc ISO có giờ, theo giờ Việt Nam. */
export function dateOfIso(iso: string): string {
  return new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(iso));
}
