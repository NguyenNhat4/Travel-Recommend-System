'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertTriangle, Building2, Flag, LayoutGrid, LogIn, Plane, RefreshCw, Search, Sparkles, Ticket } from 'lucide-react';
import { useTravel } from '../../context/TravelContext';
import * as bookingApi from '../../services/booking';
import type { BookingListResponse } from '../../services/booking';
import { ApiError } from '../../services/http';
import { BOOKING_HISTORY_PATH } from '../profile/AccountShell';
import { BookingCard } from './BookingCard';
import { DaysFilter } from './DaysFilter';
import { HistoryPagination } from './HistoryPagination';
import {
  BOOKING_TABS, HISTORY_PAGE_SIZE, SERVICE_FILTERS, emptyCopy, filtersToSearch, isFiltered, parseFilters,
  type HistoryFilters,
} from './historyModel';

const SERVICE_ICON: Record<string, React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>> = {
  ALL: LayoutGrid, hotel: Building2, flight: Plane, attraction: Ticket, combo: Sparkles, golf: Flag,
};

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ready'; data: BookingListResponse }
  | { kind: 'signed_out' }
  | { kind: 'error'; error: ApiError | null };

export const BookingHistoryView: React.FC = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentPersona, openLoginModal, navigate, showToast, refreshCart } = useTravel();
  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);
  const [load, setLoad] = useState<LoadState>({ kind: 'loading' });
  const [reloadKey, setReloadKey] = useState(0);
  const [rebookingRef, setRebookingRef] = useState<string | null>(null);
  const userId = currentPersona?.id ?? null;
  // Effect tải dữ liệu chỉ phụ thuộc vào bộ lọc; `router` đi qua ref để effect không chạy lại khi nó đổi tham chiếu.
  const routerRef = useRef(router);
  useEffect(() => { routerRef.current = router; }, [router]);

  const { tab, taxonomy, days, page } = filters;
  useEffect(() => {
    const controller = new AbortController();
    setLoad({ kind: 'loading' });
    bookingApi.listBookings({
      tab, taxonomy: taxonomy === 'ALL' ? undefined : taxonomy, days: days || undefined, page, pageSize: HISTORY_PAGE_SIZE,
    }, controller.signal)
      .then((data) => {
        // Trang vượt quá số trang hiện có (đơn vừa giảm, hoặc URL sửa tay): về trang cuối thay vì hiện trang trống.
        if (data.data.length === 0 && page > 1 && data.pagination.totalPages >= 1) {
          routerRef.current.replace(
            `${BOOKING_HISTORY_PATH}${filtersToSearch({ tab, taxonomy, days, page: data.pagination.totalPages })}`, { scroll: false });
          return;
        }
        setLoad({ kind: 'ready', data });
      })
      .catch((error: unknown) => {
        if ((error as Error)?.name === 'AbortError') return;
        if (error instanceof ApiError && error.status === 401) setLoad({ kind: 'signed_out' });
        else setLoad({ kind: 'error', error: error instanceof ApiError ? error : null });
      });
    return () => controller.abort();
  }, [tab, taxonomy, days, page, userId, reloadKey]);

  const go = useCallback((patch: Partial<HistoryFilters>) => {
    router.replace(`${BOOKING_HISTORY_PATH}${filtersToSearch({ ...filters, page: 1, ...patch })}`, { scroll: false });
  }, [filters, router]);

  const goPage = (next: number) => {
    go({ page: next });
    document.getElementById('booking-history-panel')?.scrollIntoView?.({ block: 'start' });
  };

  // Đặt lại: đơn nháp mới từ các mục của đơn theo giá hiện tại; mục không còn bán bị bỏ (R-RBK-02, R-RBK-03).
  const rebook = async (referenceCode: string) => {
    setRebookingRef(referenceCode);
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
      setRebookingRef(null);
    }
  };

  const ready = load.kind === 'ready' ? load.data : null;
  return (
    <div id="booking-history-panel" className="grid gap-3.5">
      <div>
        <h1 className="text-[22px] font-bold leading-tight tracking-tight text-slate-900">Lịch sử đặt chỗ</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">Theo dõi đơn đã đặt, thanh toán và hoàn tiền.</p>
      </div>

      <div className="sticky top-0 z-[5] rounded-2xl border border-slate-200 bg-white">
        <div role="tablist" aria-label="Trạng thái đơn" className="grid grid-cols-3 border-b border-slate-200 px-2">
          {BOOKING_TABS.map((item) => (
            <button
              key={item.id} type="button" role="tab" id={`booking-tab-${item.id}`} aria-selected={tab === item.id}
              aria-controls="booking-history-list" onClick={() => go({ tab: item.id })}
              className={`-mb-px min-h-12 border-b-[3px] px-1 text-sm transition-colors ${
                tab === item.id ? 'border-blue-600 font-semibold text-blue-700' : 'border-transparent font-medium text-slate-600 hover:text-slate-900'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div role="group" aria-label="Loại dịch vụ" className="flex gap-2 overflow-x-auto px-3.5 py-3 [scrollbar-width:none]">
          {SERVICE_FILTERS.map((item) => {
            const Icon = SERVICE_ICON[item.id];
            const active = taxonomy === item.id;
            return (
              <button
                key={item.id} type="button" aria-pressed={active} onClick={() => go({ taxonomy: item.id })}
                className={`inline-flex min-h-10 flex-none items-center gap-1.5 whitespace-nowrap rounded-full border px-3.5 text-[13px] font-medium transition-colors ${
                  active ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-200 bg-white text-slate-700 hover:border-blue-600 hover:text-blue-700'
                }`}
              >
                <Icon className="h-4 w-4" aria-hidden={true} />
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-0.5">
        <p aria-live="polite" className="min-h-[1em] text-[13px] text-slate-600 tabular-nums">
          {ready ? `${ready.pagination.totalItems} đơn` : ''}
        </p>
        <DaysFilter value={days} onChange={(value) => go({ days: value })} />
      </div>

      <div id="booking-history-list" role="tabpanel" aria-labelledby={`booking-tab-${tab}`}>
        {load.kind === 'loading' && (
          <div className="grid gap-3.5" aria-busy="true" aria-label="Đang tải đơn hàng">
            {[0, 1, 2].map((n) => <div key={n} className="h-40 animate-pulse rounded-2xl border border-slate-200 bg-slate-100" />)}
          </div>
        )}

        {load.kind === 'signed_out' && (
          <StateBlock
            title="Đăng nhập để xem đơn hàng của bạn."
            text="Các đơn đã đặt được lưu theo tài khoản của bạn."
            action={<ActionButton onClick={() => openLoginModal(() => setReloadKey((n) => n + 1))}><LogIn className="h-4 w-4" aria-hidden="true" /> Đăng nhập</ActionButton>}
          />
        )}

        {load.kind === 'error' && (
          <StateBlock
            alert title="Chưa tải được đơn hàng của bạn."
            text="Kết nối bị gián đoạn. Các đơn của bạn vẫn an toàn. Kiểm tra mạng rồi thử lại."
            note={load.error?.requestId ? `Mã yêu cầu: ${load.error.requestId}` : undefined}
            action={<ActionButton onClick={() => setReloadKey((n) => n + 1)}><RefreshCw className="h-4 w-4" aria-hidden="true" /> Thử lại</ActionButton>}
          />
        )}

        {load.kind === 'ready' && load.data.data.length === 0 && (() => {
          const copy = emptyCopy(filters);
          return (
            <StateBlock
              title={copy.title} text={copy.text}
              action={isFiltered(filters)
                ? <ActionButton onClick={() => go({ taxonomy: 'ALL', days: 0 })}>Xoá bộ lọc</ActionButton>
                : copy.cta
                  ? <Link href={copy.cta.href} className="inline-flex min-h-11 items-center gap-2 rounded-full bg-blue-600 px-6 text-[13px] font-semibold text-white hover:bg-blue-700"><Search className="h-4 w-4" aria-hidden="true" /> {copy.cta.label}</Link>
                  : undefined}
            />
          );
        })()}

        {load.kind === 'ready' && load.data.data.length > 0 && (
          <>
            <div className="grid gap-3.5">
              {load.data.data.map((booking) => (
                <BookingCard
                  key={booking.referenceCode} booking={booking}
                  rebooking={rebookingRef === booking.referenceCode} onRebook={(code) => void rebook(code)}
                />
              ))}
            </div>
            <HistoryPagination
              page={load.data.pagination.page} pageSize={load.data.pagination.pageSize}
              totalItems={load.data.pagination.totalItems} totalPages={load.data.pagination.totalPages} onPage={goPage}
            />
          </>
        )}
      </div>
    </div>
  );
};

const ActionButton: React.FC<{ onClick: () => void; children: React.ReactNode }> = ({ onClick, children }) => (
  <button
    type="button" onClick={onClick}
    className="inline-flex min-h-11 items-center gap-2 rounded-full bg-blue-600 px-6 text-[13px] font-semibold text-white hover:bg-blue-700"
  >
    {children}
  </button>
);

/** Vali và kính lúp: hình minh hoạ chung cho trạng thái trống và lỗi (vẽ tay, không dùng ảnh ngoài). */
const Illustration: React.FC = () => (
  <svg viewBox="0 0 132 112" fill="none" aria-hidden="true" className="mb-1.5 h-28 w-[8.25rem]">
    <ellipse cx="66" cy="102" rx="46" ry="6" className="fill-slate-100" />
    <rect x="22" y="38" width="62" height="54" rx="10" className="fill-blue-50 stroke-blue-600" strokeWidth="2.5" />
    <path d="M41 38v-8a6 6 0 0 1 6-6h12a6 6 0 0 1 6 6v8" className="stroke-blue-600" strokeWidth="2.5" />
    <path d="M38 50v30M68 50v30" className="stroke-blue-600" strokeWidth="2.5" strokeLinecap="round" />
    <circle cx="36" cy="95" r="4" className="fill-blue-600" />
    <circle cx="70" cy="95" r="4" className="fill-blue-600" />
    <circle cx="90" cy="48" r="17" className="fill-white stroke-slate-800" strokeWidth="3" />
    <path d="m102 61 14 15" className="stroke-slate-800" strokeWidth="5" strokeLinecap="round" />
  </svg>
);

const StateBlock: React.FC<{ title: string; text: string; note?: string; alert?: boolean; action?: React.ReactNode }> = ({
  title, text, note, alert, action,
}) => (
  <div role={alert ? 'alert' : undefined} className="grid justify-items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-11 text-center">
    {alert ? <AlertTriangle className="h-10 w-10 text-rose-500" aria-hidden="true" /> : <Illustration />}
    <h2 className="text-[17px] font-semibold text-slate-900 [text-wrap:balance]">{title}</h2>
    <p className="max-w-[44ch] text-[13px] text-slate-500">{text}</p>
    {action && <div className="mt-2.5">{action}</div>}
    {note && <p className="mt-1 font-mono text-[11px] text-slate-400">{note}</p>}
  </div>
);
