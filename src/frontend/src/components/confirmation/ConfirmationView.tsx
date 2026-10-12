'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTravel } from '../../context/TravelContext';
import { useAssistant } from '../../context/AssistantProvider';
import * as bookingApi from '../../services/booking';
import type { ApiBookingItem, BookingResponse, BookingTraveler } from '../../services/booking';
import { fetchRecommendations } from '../../services/recsys';
import { ApiError } from '../../services/http';
import type { RecommendationResponse } from '../../types/travel';
import { ProductCard } from '../common/ProductCard';
import { WhyPopover } from '../common/WhyPopover';
import {
  AlertTriangle, CheckCircle2, Clock, Copy, Check, HelpCircle, Home, Loader2, RefreshCw, Sparkles, XCircle,
} from 'lucide-react';
import {
  BOOKING_STATUS_BADGE, FAILURE_REASON_TEXT, MAX_CARD_ATTEMPTS, formatCountdown, formatDateTimeVn, formatVnd,
} from './bookingLabels';
import { FareLines } from '../checkout/FareLines';
import {
  BookingBreadcrumb, CancellationPolicyBlock, CustomerBlock, PartyBlock, PaymentPanel, ServiceFacts, ServiceInfoBlock,
} from './BookingDetailSections';
import { useProductInfo, type PropertyInfo } from './useProductInfo';

interface ConfirmationViewProps {
  referenceCode: string;
  /** `?payment=return` (Stripe đưa về sau khi trả) hoặc `cancelled` (khách bấm quay lại trên trang Stripe). */
  paymentReturn?: string;
}

type LoadState = { kind: 'loading' } | { kind: 'not_found' } | { kind: 'error'; error: ApiError | null };

export const ConfirmationView: React.FC<ConfirmationViewProps> = ({ referenceCode, paymentReturn }) => {
  const {
    getBookingByCode, rememberBooking, refreshCart, markJustBooked, currentPersona, activeEvents, navigate, showToast,
  } = useTravel();
  const { openFloatingWidget } = useAssistant();
  const [booking, setBooking] = useState<BookingResponse | null>(() => getBookingByCode(referenceCode) ?? null);
  const [load, setLoad] = useState<LoadState>({ kind: 'loading' });
  const [polls, setPolls] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [rebooking, setRebooking] = useState(false);
  const confirmedOnce = useRef(false);

  const fetchBooking = useCallback(async (signal?: AbortSignal) => {
    try {
      const fresh = await bookingApi.getBooking(referenceCode, signal);
      setBooking(fresh);
      rememberBooking(fresh);
      return fresh;
    } catch (error) {
      if ((error as Error)?.name === 'AbortError') return null;
      if (error instanceof ApiError && error.code === 'BOOKING_NOT_FOUND') setLoad({ kind: 'not_found' });
      else setLoad({ kind: 'error', error: error instanceof ApiError ? error : null });
      return null;
    }
  }, [referenceCode, rememberBooking]);

  useEffect(() => {
    const controller = new AbortController();
    void fetchBooking(controller.signal);
    return () => controller.abort();
  }, [fetchBooking]);

  const status = booking?.status;
  const paymentStatus = booking?.payment?.status;
  const propertyInfo = useProductInfo(booking ? bookingApi.bookingItems(booking) : []);

  // Đồng hồ đếm ngược theo holdExpiresAt do server trả.
  const holdExpiresAt = status === 'PENDING_PAYMENT' ? booking?.holdExpiresAt ?? null : null;
  useEffect(() => {
    if (!holdExpiresAt) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [holdExpiresAt]);
  const remainingMs = holdExpiresAt ? Date.parse(holdExpiresAt) - now : null;
  const holdOver = remainingMs !== null && remainingMs <= 0;

  // Quay về từ Stripe không phải bằng chứng đã trả tiền: hỏi lại 2 giây/lần, tối đa 15 lần (spec booking §6.1).
  // Đồng hồ về 0 cũng hỏi lại: webhook hết hạn có thể tới chậm vài giây (§8.1).
  const awaitingConfirmation = status === 'PENDING_PAYMENT'
    && (paymentReturn === 'return' || paymentStatus === 'SUCCEEDED' || holdOver);
  useEffect(() => {
    if (!awaitingConfirmation || polls >= bookingApi.PAYMENT_POLL_MAX_ATTEMPTS) return;
    const timer = setTimeout(() => {
      setPolls((n) => n + 1);
      void fetchBooking();
    }, bookingApi.PAYMENT_POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [awaitingConfirmation, polls, fetchBooking]);

  // Đơn vừa chuyển CONFIRMED: giỏ phía server đã bỏ các mục vừa đặt; trang chủ cần gọi lại gợi ý (§4.1 justBooked).
  useEffect(() => {
    if (status !== 'CONFIRMED' || confirmedOnce.current) return;
    confirmedOnce.current = true;
    void refreshCart();
    if (paymentReturn === 'return') markJustBooked();
  }, [status, paymentReturn, refreshCart, markJustBooked]);

  // Đặt lại: đơn nháp mới từ các mục của đơn, giá tính lại; mục không còn bán bị bỏ (R-RBK-02, R-RBK-03).
  const rebook = async () => {
    setRebooking(true);
    try {
      const draft = await bookingApi.createBookingDraft({ fromBooking: referenceCode, allowPartial: true });
      if (draft.rejectedItems?.length) {
        showToast(`${draft.rejectedItems.length} dịch vụ không còn đặt được nên không nằm trong lần đặt lại này.`);
      }
      void refreshCart();
      navigate(bookingApi.checkoutPathOf(draft.draftId));
    } catch (error) {
      showToast(error instanceof ApiError ? error.message : 'Chưa đặt lại được đơn này. Vui lòng thử lại.');
    } finally {
      setRebooking(false);
    }
  };

  const cancel = async () => {
    setCancelling(true);
    setCancelError(null);
    try {
      const cancelled = await bookingApi.cancelBooking(referenceCode);
      setBooking(cancelled);
      rememberBooking(cancelled);
      setCancelOpen(false);
      showToast(cancelled.payment?.status === 'EXPIRED' ? 'Đã huỷ đơn. Đơn chưa thanh toán nên không phát sinh tiền.' : 'Đã huỷ đơn. Tiền hoàn về thẻ trong 5–10 ngày làm việc.');
    } catch (error) {
      if (error instanceof ApiError && error.code === 'BOOKING_ALREADY_PAID') {
        setCancelOpen(false);
        await fetchBooking();
        showToast('Đơn vừa được thanh toán. Muốn huỷ, hãy huỷ như đơn đã thanh toán.');
      } else if (error instanceof ApiError && error.code === 'BOOKING_NOT_CANCELLABLE') {
        setCancelError(error.details?.reason === 'TOO_LATE' && error.details?.cancellableUntil
          ? `Đã quá hạn huỷ trực tuyến (hạn: ${formatDateTimeVn(error.details.cancellableUntil)}).`
          : 'Đơn này không còn hiệu lực.');
      } else if (error instanceof ApiError && error.retryable) {
        setCancelError('Chưa huỷ được, vui lòng thử lại.');
      } else {
        setCancelError(error instanceof ApiError ? error.message : 'Chưa huỷ được, vui lòng thử lại.');
      }
    } finally {
      setCancelling(false);
    }
  };

  if (!booking) {
    if (load.kind === 'not_found') {
      return (
        <CenteredCard icon={<XCircle className="w-10 h-10 text-slate-400" />} title="Không tìm thấy đơn đặt chỗ này">
          <PrimaryButton onClick={() => navigate('/')}><Home className="w-4 h-4" /> Về trang chủ</PrimaryButton>
        </CenteredCard>
      );
    }
    if (load.kind === 'error') {
      return (
        <CenteredCard icon={<AlertTriangle className="w-10 h-10 text-rose-500" />} title="Chưa tải được đơn đặt chỗ">
          {load.error?.requestId && <p className="text-[11px] text-slate-400 font-mono">Mã yêu cầu: {load.error.requestId}</p>}
          <PrimaryButton onClick={() => { setLoad({ kind: 'loading' }); void fetchBooking(); }}>
            <RefreshCw className="w-4 h-4" /> Thử lại
          </PrimaryButton>
        </CenteredCard>
      );
    }
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 flex justify-center text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" aria-label="Đang tải đơn đặt chỗ" />
      </div>
    );
  }

  const canCancelConfirmed = booking.status === 'CONFIRMED' && booking.cancellableUntil !== null
    && Date.parse(booking.cancellableUntil) > now;
  const canCancel = booking.status === 'PENDING_PAYMENT' && paymentStatus === 'OPEN' || canCancelConfirmed;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <BookingBreadcrumb />
      <div className="space-y-6">
        <StatusCard
          booking={booking}
          paymentReturn={paymentReturn}
          remainingMs={remainingMs}
          pollsExhausted={polls >= bookingApi.PAYMENT_POLL_MAX_ATTEMPTS}
          onContinue={() => booking.payment?.checkoutUrl && bookingApi.redirectToCheckout(booking.payment.checkoutUrl)}
          onRebook={() => void rebook()}
          rebooking={rebooking}
          onHome={() => navigate('/')}
          onAssistant={() => openFloatingWidget(`Gợi ý lịch trình 3 ngày ở ${booking.groups[0]?.destination ?? 'điểm đến của tôi'}`)}
        />

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
          <div className="min-w-0 space-y-4">
            <BookingSummary booking={booking} info={propertyInfo} />
            <CustomerBlock booking={booking} />
            <PartyBlock booking={booking} />
            <ServiceInfoBlock items={bookingApi.bookingItems(booking)} info={propertyInfo} />
            <CancellationPolicyBlock booking={booking} nowMs={now} />
          </div>
          <aside className="min-w-0 lg:sticky lg:top-4">
            <PaymentPanel
              booking={booking}
              cancel={canCancel ? (
                <button
                  type="button"
                  onClick={() => { setCancelError(null); setCancelOpen(true); }}
                  className="mt-1 min-h-11 rounded-xl border border-rose-300 px-4 py-2 text-xs font-bold text-rose-700 hover:bg-rose-50"
                >
                  Huỷ đơn
                </button>
              ) : null}
            />
          </aside>
        </div>

        {booking.status === 'CONFIRMED' && (
          <NextForTrip destination={booking.groups[0]?.destination} persona={currentPersona} events={activeEvents} />
        )}
      </div>

      {cancelOpen && (
        <div role="dialog" aria-modal="true" aria-labelledby="cancel-title"
          className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 id="cancel-title" className="text-base font-bold text-slate-900">
              {booking.status === 'PENDING_PAYMENT' ? 'Huỷ đơn đang giữ chỗ?' : 'Huỷ đơn đã thanh toán?'}
            </h3>
            {booking.status === 'CONFIRMED' ? (
              <p className="text-xs text-slate-600">
                Sota hoàn <strong>{formatVnd(booking.payment?.amount ?? booking.total)}</strong> về thẻ đã dùng (5–10 ngày làm
                việc). Hạn huỷ có hoàn tiền: {booking.cancellableUntil && formatDateTimeVn(booking.cancellableUntil)}.
                Thao tác này không thể hoàn tác.
              </p>
            ) : (
              <p className="text-xs text-slate-600">Đơn chưa thanh toán nên không phát sinh tiền. Tour, trải nghiệm và tiện ích của đơn vẫn nằm trong giỏ hàng; khách sạn và vé máy bay cần đặt lại.</p>
            )}
            {cancelError && <p role="alert" className="text-xs text-rose-700">{cancelError}</p>}
            <div className="flex gap-2 justify-end">
              <button onClick={() => setCancelOpen(false)} className="px-4 py-2 text-xs text-slate-600 hover:underline">
                Giữ đơn
              </button>
              <button
                onClick={() => void cancel()} disabled={cancelling}
                className="px-4 py-2 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 disabled:bg-slate-300 rounded-xl flex items-center gap-1"
              >
                {cancelling && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Xác nhận huỷ
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// --- trạng thái đơn (spec booking §5.1) ------------------------------------------------------------

const StatusCard: React.FC<{
  booking: BookingResponse;
  paymentReturn?: string;
  remainingMs: number | null;
  pollsExhausted: boolean;
  onContinue: () => void;
  onRebook: () => void;
  rebooking: boolean;
  onHome: () => void;
  onAssistant: () => void;
}> = ({ booking, paymentReturn, remainingMs, pollsExhausted, onContinue, onRebook, rebooking, onHome, onAssistant }) => {
  const payment = booking.payment;
  const [copied, setCopied] = useState(false);
  const copy = () => {
    void navigator.clipboard?.writeText(booking.referenceCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  if (booking.status === 'PENDING_PAYMENT' && payment?.status === 'SUCCEEDED') {
    return (
      <CenteredCard icon={<Loader2 className="w-10 h-10 text-brand-600 animate-spin" />} title="Đã nhận thanh toán, đang xác nhận đơn">
        <p className="text-xs text-slate-500">Bạn có thể đóng trang, đơn sẽ tự cập nhật.</p>
      </CenteredCard>
    );
  }

  if (booking.status === 'PENDING_PAYMENT' && remainingMs !== null && remainingMs <= 0) {
    // Phiên Stripe hết hạn cùng lúc với giữ chỗ: link thanh toán cũ không dùng được nữa.
    return (
      <CenteredCard icon={<Clock className="w-10 h-10 text-slate-400" />} title="Hết thời gian giữ chỗ">
        <p className="text-xs text-slate-600">{REBOOK_HINT}</p>
        <RebookButton onClick={onRebook} busy={rebooking} />
      </CenteredCard>
    );
  }

  if (booking.status === 'PENDING_PAYMENT') {
    const confirming = paymentReturn === 'return' && !pollsExhausted;
    return (
      <CenteredCard
        icon={confirming ? <Loader2 className="w-10 h-10 text-brand-600 animate-spin" /> : <Clock className="w-10 h-10 text-amber-500" />}
        title={confirming ? 'Đang kiểm tra thanh toán...' : 'Đơn đang được giữ chỗ'}
      >
        {booking.holdExpiresAt && (
          <p className="text-xs text-slate-600">
            Giữ đến {formatDateTimeVn(booking.holdExpiresAt)} · còn{' '}
            <span data-testid="hold-countdown" className="font-mono font-bold text-amber-700">
              {formatCountdown(remainingMs ?? 0)}
            </span>
          </p>
        )}
        {paymentReturn === 'cancelled' && (
          <p className="text-xs text-slate-500">Bạn đã quay lại từ trang thanh toán. Đơn vẫn được giữ tới hạn.</p>
        )}
        {payment && payment.failedAttempts > 0 && payment.failureReason && (
          <p className="text-xs text-rose-700">
            Lần thanh toán trước: {FAILURE_REASON_TEXT[payment.failureReason]} Còn {Math.max(0, MAX_CARD_ATTEMPTS - payment.failedAttempts)} lần thử.
          </p>
        )}
        <ReferenceCode code={booking.referenceCode} copied={copied} onCopy={copy} />
        {payment?.checkoutUrl && (
          <PrimaryButton onClick={onContinue}>Tiếp tục thanh toán</PrimaryButton>
        )}
      </CenteredCard>
    );
  }

  if (booking.status === 'CONFIRMED') {
    return (
      <CenteredCard icon={<CheckCircle2 className="w-10 h-10 text-emerald-600" />} title="Đặt chỗ thành công!">
        <p className="text-xs sm:text-sm text-slate-500">Đã thanh toán {formatVnd(payment?.amount ?? booking.total)} qua Stripe.</p>
        <ReferenceCode code={booking.referenceCode} copied={copied} onCopy={copy} />
        {booking.cancellableUntil && (
          <p className="text-[11px] text-slate-500">Huỷ miễn phí, hoàn 100% trước {formatDateTimeVn(booking.cancellableUntil)}.</p>
        )}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <PrimaryButton onClick={onHome}><Home className="w-4 h-4" /> Xem gợi ý mới trên trang chủ</PrimaryButton>
          <button
            onClick={onAssistant}
            className="w-full sm:w-auto px-6 py-3 bg-brand-50 hover:bg-brand-100 text-brand-700 border border-brand-200 font-bold text-xs sm:text-sm rounded-xl flex items-center justify-center gap-2"
          >
            <Sparkles className="w-4 h-4" /> Lên lịch trình cho chuyến {booking.groups[0]?.destination}
          </button>
        </div>
      </CenteredCard>
    );
  }

  if (booking.status === 'PAYMENT_FAILED') {
    const reason = payment?.failureReason ? FAILURE_REASON_TEXT[payment.failureReason] : 'Thanh toán không thành công.';
    return (
      <CenteredCard icon={<XCircle className="w-10 h-10 text-rose-600" />} title="Thanh toán không thành công">
        <p className="text-xs text-slate-600">{reason}</p>
        <ReferenceCode code={booking.referenceCode} copied={copied} onCopy={copy} />
        <RebookButton onClick={onRebook} busy={rebooking} />
      </CenteredCard>
    );
  }

  if (booking.status === 'EXPIRED') {
    return (
      <CenteredCard icon={<Clock className="w-10 h-10 text-slate-400" />} title="Hết thời gian giữ chỗ">
        <p className="text-xs text-slate-600">Đơn chưa được thanh toán trong 30 phút. {REBOOK_HINT}</p>
        <RebookButton onClick={onRebook} busy={rebooking} />
      </CenteredCard>
    );
  }

  // CANCELLED
  const refund = booking.cancellation?.refundAmount ?? 0;
  const refundText = payment?.status === 'REFUNDED'
    ? `Đã hoàn ${formatVnd(payment.refundedAmount)} về thẻ.`
    : payment?.status === 'REFUND_PENDING'
      ? `Đang hoàn ${formatVnd(refund)}. Tiền về thẻ trong 5–10 ngày làm việc.`
      : payment?.status === 'REFUND_FAILED'
        ? 'Hoàn tiền đang gặp sự cố; Sota sẽ liên hệ với bạn.'
        : 'Đơn chưa thanh toán nên không phát sinh hoàn tiền.';
  return (
    <CenteredCard icon={<XCircle className="w-10 h-10 text-slate-400" />} title="Đã huỷ đơn">
      <p className="text-xs text-slate-600">{refundText}</p>
      {booking.cancellation && (
        <p className="text-[11px] text-slate-400">Huỷ lúc {formatDateTimeVn(booking.cancellation.cancelledAt)}</p>
      )}
      <ReferenceCode code={booking.referenceCode} copied={copied} onCopy={copy} />
    </CenteredCard>
  );
};

function TravelerName({ traveler }: { traveler: BookingTraveler }) {
  return (
    <span className="whitespace-nowrap">
      {traveler.fullName}
      {traveler.type === 'CHILD' && <span className="text-slate-400"> (trẻ em)</span>}
      {traveler.isLead && <span className="ml-1 rounded bg-brand-50 px-1 py-0.5 text-[10px] font-semibold text-brand-700">Đại diện nhận phòng</span>}
    </span>
  );
}

/**
 * Hành khách của một mục đơn (spec checkout-nhieu-buoc-hanh-khach.md §6.8): khách sạn hiện khách theo phòng và đánh dấu người đại
 * diện; dịch vụ khác một dòng. Không có ngày sinh (response không trả). Đơn tạo trước thay đổi này không có `travelers` nên vẫn hiện
 * `guestNames` như trước.
 */
const ItemTravelers: React.FC<{ item: ApiBookingItem }> = ({ item }) => {
  const travelers = item.travelers ?? [];
  if (travelers.length === 0) {
    return item.guestNames.length ? <p className="text-[11px] text-slate-500" data-testid="item-travelers">{item.guestNames.join(', ')}</p> : null;
  }
  const rooms = new Map<number, BookingTraveler[]>();
  for (const traveler of travelers) {
    if (traveler.roomNo === null) continue;
    rooms.set(traveler.roomNo, [...(rooms.get(traveler.roomNo) ?? []), traveler]);
  }
  const list = (people: BookingTraveler[]) => people.map((t, i) => <React.Fragment key={`${t.fullName}-${i}`}>{i > 0 && ', '}<TravelerName traveler={t} /></React.Fragment>);
  return (
    <ul className="text-[11px] text-slate-600 space-y-0.5" data-testid="item-travelers">
      {rooms.size > 0
        ? [...rooms.entries()].sort(([a], [b]) => a - b).map(([no, people]) => <li key={no}><span className="font-semibold text-slate-700">Phòng {no}:</span> {list(people)}</li>)
        : <li>{list(travelers)}</li>}
    </ul>
  );
};

/** Số lượng của mục theo loại dịch vụ: khách sạn theo phòng (kèm số khách nếu có), combo theo gói, còn lại theo khách. */
function quantityText(item: ApiBookingItem): string {
  if (item.product.taxonomy === 'hotel') {
    const guests = item.travelers?.length ?? 0;
    return guests ? `${item.quantity} phòng · ${guests} khách` : `${item.quantity} phòng`;
  }
  return item.product.taxonomy === 'combo' ? `${item.quantity} gói` : `${item.quantity} khách`;
}

const BookingSummary: React.FC<{ booking: BookingResponse; info: Record<string, PropertyInfo> }> = ({ booking, info }) => (
  <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
    <div className="flex items-center justify-between pb-3 border-b border-slate-100">
      <h3 className="text-sm font-bold text-slate-900">Thông tin đặt chỗ</h3>
      <span className={`text-xs font-bold ${BOOKING_STATUS_BADGE[booking.status].className}`}>
        {BOOKING_STATUS_BADGE[booking.status].label}
      </span>
    </div>
    {booking.groups.map((group) => (
      <div key={`${group.destination}-${group.items[0]?.bookingItemId}`} className="space-y-1">
        <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Chuyến {group.destination}</div>
        <div className="divide-y divide-slate-100">
          {group.items.map((item) => (
            <div key={item.bookingItemId} className="py-3 space-y-2" data-testid="booking-item">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-0.5">
                  <h5 className="text-xs font-bold text-slate-900">{item.product.name}</h5>
                  <p className="text-[11px] text-slate-500">
                    {item.usingDate}
                    {item.nights ? ` · ${item.nights} đêm` : ''} · {quantityText(item)}
                  </p>
                  <ItemTravelers item={item} />
                </div>
                <span className="text-xs font-semibold text-slate-800 font-mono">{formatVnd(item.lineTotal)}</span>
              </div>
              <FareLines fares={item.fares ?? []} />
              <div className="-mx-1 overflow-hidden rounded-xl border border-slate-100">
                <ServiceFacts item={item} info={info[item.bookingItemId]} />
              </div>
            </div>
          ))}
        </div>
      </div>
    ))}
  </div>
);

/** Chỉ gọi /recommendations khi đơn đã CONFIRMED (AC-REC-02); lỗi hoặc rỗng thì ẩn section. */
const NextForTrip: React.FC<{
  destination?: string;
  persona: ReturnType<typeof useTravel>['currentPersona'];
  events: ReturnType<typeof useTravel>['activeEvents'];
}> = ({ destination, persona, events }) => {
  const [recs, setRecs] = useState<RecommendationResponse | null>(null);
  const [showWhy, setShowWhy] = useState(false);
  useEffect(() => {
    if (!destination) return;
    const controller = new AbortController();
    fetchRecommendations({ k: 4, destination, signal: controller.signal })
      .then(setRecs)
      .catch(() => setRecs(null));
    return () => controller.abort();
  }, [destination, persona, events]);

  if (!destination || !recs || recs.recommendations.length === 0) return null;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-black text-slate-900">TIẾP THEO CHO CHUYẾN {destination.toUpperCase()}</h2>
          <p className="text-xs text-slate-600">Vì bạn vừa đặt dịch vụ tại {destination} — đây là các đề xuất bổ trợ cho hành trình.</p>
        </div>
        <button onClick={() => setShowWhy(true)} className="text-xs font-semibold text-brand-700 hover:text-brand-800 flex items-center gap-1">
          <HelpCircle className="w-3.5 h-3.5" /> Vì sao?
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {recs.recommendations.slice(0, 3).map((rec) => (
          <ProductCard
            key={rec.product.id}
            product={rec.product}
            variant="grid"
            because={rec.because}
            strategy={recs.strategy}
            excludedVerticals={recs.diagnostics.excludedVerticals}
          />
        ))}
      </div>
      <WhyPopover
        isOpen={showWhy}
        onClose={() => setShowWhy(false)}
        targetProductName={`Chuyến đi ${destination}`}
        becauseItems={recs.recommendations[0]?.because || []}
        strategy={recs.strategy}
        excludedVerticals={recs.diagnostics.excludedVerticals}
        destination={destination}
      />
    </div>
  );
};

const CenteredCard: React.FC<{ icon: React.ReactNode; title: string; children?: React.ReactNode }> = ({ icon, title, children }) => (
  <div className="p-8 bg-white rounded-3xl border border-slate-200 shadow-xl text-center space-y-4">
    <div className="w-16 h-16 rounded-full bg-slate-50 flex items-center justify-center mx-auto">{icon}</div>
    <h1 className="text-2xl sm:text-3xl font-black text-slate-900">{title}</h1>
    {children}
  </div>
);

/** Đặt lại một đơn chưa thanh toán xong: đơn nháp mới từ các mục của đơn, theo giá hiện tại (spec dat-truc-tiep-theo-don-nhap.md §7). */
const REBOOK_HINT = 'Bạn có thể đặt lại các dịch vụ của đơn này theo giá hiện tại.';

const RebookButton: React.FC<{ onClick: () => void; busy: boolean }> = ({ onClick, busy }) => (
  <button
    onClick={onClick} disabled={busy}
    className="w-full sm:w-auto px-6 py-3 bg-brand-600 hover:bg-brand-700 disabled:bg-slate-300 text-white font-bold text-xs sm:text-sm rounded-xl shadow-xs transition-colors inline-flex items-center justify-center gap-2"
  >
    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Đặt lại
  </button>
);

const PrimaryButton: React.FC<{ onClick: () => void; children: React.ReactNode }> = ({ onClick, children }) => (
  <button
    onClick={onClick}
    className="w-full sm:w-auto px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-xs transition-colors inline-flex items-center justify-center gap-2"
  >
    {children}
  </button>
);

const ReferenceCode: React.FC<{ code: string; copied: boolean; onCopy: () => void }> = ({ code, copied, onCopy }) => (
  <div className="inline-flex items-center gap-3 px-5 py-3 rounded-2xl bg-slate-50 border border-slate-200">
    <div className="text-left">
      <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">Mã đặt chỗ</span>
      <span className="font-mono text-lg font-black text-brand-900 tracking-wider">{code}</span>
    </div>
    <button onClick={onCopy} className="p-2 rounded-xl bg-white border border-slate-200 hover:bg-slate-100 text-slate-600" title="Sao chép mã">
      {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
    </button>
  </div>
);
