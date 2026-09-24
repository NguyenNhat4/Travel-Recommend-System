/**
 * Chuỗi hiển thị của đơn đặt chỗ — Web sở hữu (docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md §5.1, §10).
 */
import type { BookingStatus, PaymentFailureReason } from '../../services/booking';

export const BOOKING_STATUS_BADGE: Record<BookingStatus, { label: string; className: string }> = {
  PENDING_PAYMENT: { label: 'Chờ thanh toán', className: 'text-amber-700' },
  CONFIRMED: { label: 'Đã xác nhận', className: 'text-emerald-700' },
  PAYMENT_FAILED: { label: 'Thanh toán thất bại', className: 'text-rose-700' },
  EXPIRED: { label: 'Hết hạn giữ chỗ', className: 'text-slate-500' },
  CANCELLED: { label: 'Đã huỷ', className: 'text-slate-500' },
};

/** Số lần thẻ bị từ chối tối đa trong một đơn (FR-BKG-06); Backend đếm, Web chỉ hiển thị số lần còn lại. */
export const MAX_CARD_ATTEMPTS = 3;

export const FAILURE_REASON_TEXT: Record<PaymentFailureReason, string> = {
  CARD_DECLINED: 'Thẻ bị từ chối. Hãy thử thẻ khác.',
  INSUFFICIENT_FUNDS: 'Thẻ không đủ số dư.',
  EXPIRED_CARD: 'Thẻ đã hết hạn.',
  INCORRECT_CVC: 'Mã CVC không đúng.',
  AUTHENTICATION_FAILED: 'Xác thực với ngân hàng không thành công.',
  PROCESSING_ERROR: 'Ngân hàng xử lý lỗi. Thử lại sau ít phút.',
  TOO_MANY_ATTEMPTS: 'Thanh toán không thành công sau 3 lần. Giỏ hàng vẫn còn, bạn có thể đặt lại.',
  AMOUNT_MISMATCH: 'Có lỗi khi xác nhận thanh toán. Tiền đã được hoàn tự động.',
};

export function formatVnd(amount: number): string {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
}

/** Giờ hiển thị luôn theo giờ Việt Nam, không theo múi giờ máy người dùng. */
export function formatDateTimeVn(iso: string): string {
  return new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric',
  }).format(new Date(iso));
}

export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}
