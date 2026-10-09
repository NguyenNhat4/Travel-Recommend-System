'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Check, ClipboardList, Copy, Mail, MapPin, Phone, Star, User } from 'lucide-react';
import { formatDay } from '../../features/bookings/historyModel';
import type { ApiBookingItem, BookingResponse } from '../../services/booking';
import { formatDateTimeVn, formatVnd } from './bookingLabels';
import { HOTEL_CHECK_IN_NOTE, HOTEL_CHECK_OUT_NOTE, SUPPORT_HOTLINE } from './bookingDefaults';
import type { PropertyInfo } from './useProductInfo';

const BOX = 'overflow-hidden rounded-2xl border border-slate-200 bg-white';
const BOX_HEAD = 'flex flex-wrap items-center justify-between gap-x-3 bg-gradient-to-r from-teal-100/80 to-white px-4 py-3 text-sm font-semibold text-slate-900';

export const Box: React.FC<{ title: string; hint?: string; children: React.ReactNode }> = ({ title, hint, children }) => (
  <section className={BOX}>
    <h3 className={BOX_HEAD}>{title}{hint && <span className="text-xs font-medium text-slate-500">{hint}</span>}</h3>
    {children}
  </section>
);

export const BookingBreadcrumb: React.FC = () => (
  <nav aria-label="Đường dẫn" className="mb-4 flex flex-wrap items-center gap-2 text-[13px] text-slate-500">
    <Link href="/profile/booking_history" className="hover:text-brand-700 hover:underline">Đơn hàng của tôi</Link>
    <span aria-hidden="true">/</span>
    <span aria-current="page" className="font-medium text-slate-800">Chi tiết đơn hàng</span>
  </nav>
);

// --- ngày ---------------------------------------------------------------------------------------

const DAY_MS = 86_400_000;

function addDays(iso: string, days: number): string {
  return new Date(Date.parse(`${iso}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

/** `2026-10-12` → "T2, 12 thg 10". Tính theo UTC để ngày không lệch theo múi giờ máy người dùng. */
function weekdayDay(iso: string): string {
  return new Intl.DateTimeFormat('vi-VN', { weekday: 'short', day: 'numeric', month: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${iso}T00:00:00Z`)).replace(/\//, ' thg ');
}

function attr(item: ApiBookingItem, key: string): string | undefined {
  const value = (item.product.attributes as Record<string, unknown> | undefined)?.[key];
  return typeof value === 'string' && value ? value : undefined;
}

const CABIN: Record<string, string> = {
  ECONOMY: 'Phổ thông', PREMIUM_ECONOMY: 'Phổ thông đặc biệt', BUSINESS: 'Thương gia', FIRST: 'Hạng nhất',
};

// --- khối dịch vụ ---------------------------------------------------------------------------------

const Stars: React.FC<{ count: number }> = ({ count }) => (
  <span role="img" aria-label={`${count} sao`} className="mr-1.5 inline-flex gap-px align-[-2px] text-amber-500">
    {Array.from({ length: Math.min(5, Math.max(0, Math.round(count))) }, (_, i) => <Star key={i} className="h-3.5 w-3.5 fill-current" aria-hidden="true" />)}
  </span>
);

const Timeline: React.FC<{ left: [string, string, string?]; right?: [string, string, string?]; middle: string }> = ({ left, right, middle }) => (
  <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 px-4 py-3.5" data-testid="item-timeline">
    <div className="min-w-0">
      <div className="text-[11px] text-slate-500">{left[0]}</div>
      <div className="break-words text-[15px] font-semibold text-brand-600">{left[1]}</div>
      {left[2] && <div className="text-xs text-slate-500">{left[2]}</div>}
    </div>
    <div className="max-w-[9rem] border-y border-dashed border-slate-300 px-2 py-1 text-center text-xs text-slate-500">{middle}</div>
    {right ? (
      <div className="min-w-0 text-right">
        <div className="text-[11px] text-slate-500">{right[0]}</div>
        <div className="break-words text-[15px] font-semibold text-brand-600">{right[1]}</div>
        {right[2] && <div className="text-xs text-slate-500">{right[2]}</div>}
      </div>
    ) : <div />}
  </div>
);

function mapHref(name: string, address?: string): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent([name, address].filter(Boolean).join(' '))}`;
}

/** Thông tin đặt chỗ của một dịch vụ: mốc thời gian, cơ sở (tên, hạng sao, địa chỉ, bản đồ) và, với khách sạn, tiện ích. */
export const ServiceFacts: React.FC<{ item: ApiBookingItem; info?: PropertyInfo }> = ({ item, info }) => {
  const taxonomy = item.product.taxonomy;
  const guests = item.travelers?.length || item.guestNames.length || item.quantity;

  let timeline: React.ReactNode;
  if (taxonomy === 'hotel' && item.nights) {
    const checkOut = addDays(item.usingDate, item.nights);
    timeline = <Timeline left={['Nhận phòng', weekdayDay(item.usingDate), HOTEL_CHECK_IN_NOTE]} right={['Trả phòng', weekdayDay(checkOut), HOTEL_CHECK_OUT_NOTE]}
      middle={`${item.nights} đêm · ${guests} khách`} />;
  } else if (taxonomy === 'flight') {
    const from = attr(item, 'originAirport'); const to = attr(item, 'destinationAirport');
    const departAt = attr(item, 'departureAt');
    const time = departAt ? new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit' }).format(new Date(departAt)) : undefined;
    timeline = <Timeline left={['Điểm đi', from ?? weekdayDay(item.usingDate), from ? `${weekdayDay(item.usingDate)}${time ? ` · ${time}` : ''}` : undefined]}
      right={to ? ['Điểm đến', to, attr(item, 'flightNumber') ? `Chuyến ${attr(item, 'flightNumber')}` : undefined] : undefined}
      middle={`${item.quantity} khách`} />;
  } else {
    timeline = <Timeline left={['Ngày sử dụng', weekdayDay(item.usingDate)]} middle={taxonomy === 'combo' ? `${item.quantity} gói` : `${item.quantity} khách`} />;
  }

  // Vé và combo đã có tên ở dòng trên: chỉ hiện địa chỉ khi catalog có. Khách sạn luôn hiện tên cơ sở (khác tên hạng phòng).
  const showProperty = taxonomy !== 'flight' && info && (taxonomy === 'hotel' || Boolean(info.address));
  const cabin = attr(item, 'cabinClass');
  return (
    <>
      {timeline}
      {showProperty && (
        <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-4 py-3">
          <div className="min-w-0">
            {taxonomy === 'hotel' && <h4 className="break-words text-[15px] font-semibold text-slate-900">{info.name}</h4>}
            <p className="text-xs text-slate-500">
              {info.starRating ? <Stars count={info.starRating} /> : null}
              {info.address}
            </p>
          </div>
          {info.address && (
            <a href={mapHref(info.name, info.address)} target="_blank" rel="noopener noreferrer"
              className="flex min-h-11 min-w-16 flex-none flex-col items-center justify-center gap-0.5 rounded-xl bg-slate-100 px-2 text-xs font-medium text-slate-800 hover:bg-brand-50">
              <MapPin className="h-[18px] w-[18px] text-rose-500" aria-hidden="true" />
              Bản đồ
            </a>
          )}
        </div>
      )}
      {taxonomy === 'hotel' && info && info.amenities.length > 0 && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 px-4 pb-3 text-[13px] text-slate-700" aria-label="Tiện ích">
          {info.amenities.slice(0, 5).map((label) => (
            <li key={label} className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-brand-600" aria-hidden="true" />{label}</li>
          ))}
          {info.amenities.length > 5 && <li className="rounded-full bg-brand-50 px-2.5 text-brand-700">+{info.amenities.length - 5} tiện ích khác</li>}
        </ul>
      )}
      {taxonomy === 'flight' && cabin && <p className="px-4 pb-3 text-[13px] text-slate-700">Hạng vé: {CABIN[cabin] ?? cabin}</p>}
    </>
  );
};

// --- khách hàng, hành khách ---------------------------------------------------------------------

const Row: React.FC<{ icon: React.ReactNode; label: string; value: React.ReactNode }> = ({ icon, label, value }) => (
  <div className="grid grid-cols-[1.25rem_minmax(0,1fr)] items-center gap-3">
    <span className="text-slate-400">{icon}</span>
    <div><dt className="text-[11px] text-slate-500">{label}</dt><dd className="break-words text-sm font-medium text-slate-900">{value}</dd></div>
  </div>
);

export const CustomerBlock: React.FC<{ booking: BookingResponse }> = ({ booking }) => (
  <Box title="Thông tin khách hàng">
    <dl className="grid gap-3.5 px-4 py-4">
      <Row icon={<User className="h-5 w-5" aria-hidden="true" />} label="Họ và tên" value={booking.contact.fullName} />
      <Row icon={<Phone className="h-5 w-5" aria-hidden="true" />} label="Số điện thoại" value={booking.contact.phone} />
      <Row icon={<Mail className="h-5 w-5" aria-hidden="true" />} label="Địa chỉ nhận thông tin" value={booking.contact.email} />
    </dl>
  </Box>
);

/** Người đi của cả đơn, gộp theo tên; đơn tạo trước khi có đoàn khách thì dùng `guestNames`. */
export function partyOf(booking: BookingResponse): Array<{ name: string; child: boolean }> {
  const seen = new Set<string>();
  const out: Array<{ name: string; child: boolean }> = [];
  for (const item of booking.groups.flatMap((g) => g.items)) {
    const people = item.travelers?.length
      ? item.travelers.map((t) => ({ name: t.fullName, child: t.type === 'CHILD' }))
      : item.guestNames.map((name) => ({ name, child: false }));
    for (const person of people) {
      const key = `${person.name}|${person.child}`;
      if (!seen.has(key)) { seen.add(key); out.push(person); }
    }
  }
  return out;
}

export const PartyBlock: React.FC<{ booking: BookingResponse }> = ({ booking }) => {
  const party = partyOf(booking);
  if (party.length === 0) return null;
  const items = booking.groups.flatMap((g) => g.items);
  const title = items.some((i) => i.product.taxonomy === 'flight') ? 'Thông tin hành khách'
    : items.some((i) => i.product.taxonomy === 'hotel') ? 'Thông tin khách lưu trú' : 'Thông tin khách tham gia';
  return (
    <Box title={title}>
      <dl className="grid gap-3.5 px-4 py-4">
        {party.map((person, index) => (
          <Row key={`${person.name}-${index}`} icon={<User className="h-5 w-5" aria-hidden="true" />}
            label={person.child ? 'Trẻ em' : 'Người lớn'} value={person.name} />
        ))}
      </dl>
    </Box>
  );
};

// --- thông tin dịch vụ, chính sách hoàn huỷ ----------------------------------------------------------

export const ServiceInfoBlock: React.FC<{ items: ApiBookingItem[]; info: Record<string, PropertyInfo> }> = ({ items, info }) => {
  const place = items.map((i) => info[i.bookingItemId]).find((p) => p?.address);
  return (
    <Box title="Thông tin dịch vụ">
      <dl className="grid gap-3.5 px-4 py-4">
        {place?.address && (
          <Row icon={<MapPin className="h-5 w-5" aria-hidden="true" />} label="Địa chỉ" value={
            <>{place.address}<br /><a className="text-[13px] font-medium text-brand-600 underline underline-offset-2" target="_blank" rel="noopener noreferrer" href={mapHref(place.name, place.address)}>Xem địa chỉ</a></>} />
        )}
        <Row icon={<Phone className="h-5 w-5" aria-hidden="true" />} label="Liên hệ hỗ trợ" value={SUPPORT_HOTLINE} />
        <Row icon={<ClipboardList className="h-5 w-5" aria-hidden="true" />} label="Chính sách" value="Huỷ miễn phí theo hạn ghi ở mục Chính sách hoàn huỷ bên dưới" />
      </dl>
    </Box>
  );
};

/** Hạn hoàn 100% (FR-BKG-07): 00:00 giờ Việt Nam của ngày liền trước ngày sử dụng sớm nhất. Đơn đã xác nhận dùng giá trị Backend trả. */
export function refundDeadlineLabel(booking: BookingResponse): string {
  if (booking.cancellableUntil) return formatDateTimeVn(booking.cancellableUntil);
  const earliest = booking.groups.flatMap((g) => g.items).map((i) => i.usingDate).sort()[0];
  return `00:00 ${formatDay(addDays(earliest, -1))}`;
}

export const CancellationPolicyBlock: React.FC<{ booking: BookingResponse; nowMs: number }> = ({ booking, nowMs }) => {
  const live = booking.status === 'CONFIRMED' && booking.cancellableUntil !== null;
  const stage = live ? (nowMs < Date.parse(booking.cancellableUntil as string) ? 0 : 1) : -1;
  const deadline = refundDeadlineLabel(booking);
  const note = booking.status === 'PENDING_PAYMENT' ? 'Đơn chưa thanh toán: bạn bỏ giữ chỗ lúc nào cũng được và không mất phí.'
    : booking.status === 'CONFIRMED' ? 'Huỷ áp dụng cho cả đơn, không huỷ riêng từng dịch vụ.'
      : 'Đơn này không còn hiệu lực. Chính sách hiện ở đây để bạn tham khảo.';
  const step = (index: number, title: string, text: string) => (
    <li key={title} className={`relative grid grid-cols-[1.375rem_minmax(0,1fr)] gap-3 pb-3.5 last:pb-0 ${stage >= 0 && stage !== index ? 'opacity-50' : ''}`}>
      <span className={`mt-0.5 grid h-[1.375rem] w-[1.375rem] place-items-center rounded-full border-2 ${stage === index ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-200 bg-slate-100'}`}>
        {stage === index && <Check className="h-3 w-3" aria-hidden="true" />}
      </span>
      <div><strong className="block text-sm font-semibold text-slate-900">{title}</strong><span className="text-xs text-slate-500">{text}</span></div>
    </li>
  );
  return (
    <Box title="Chính sách hoàn huỷ">
      <div className="px-4 py-4">
        <ol className="m-0 list-none p-0">
          {step(0, 'Miễn phí huỷ, hoàn 100%', `Trước ${deadline} (giờ Việt Nam, GMT+7)`)}
          {step(1, 'Không huỷ trực tuyến được', `Từ ${deadline}. Cần hỗ trợ, hãy gọi ${SUPPORT_HOTLINE}.`)}
        </ol>
        <p className="mt-3 text-[13px] text-slate-500">{note}</p>
      </div>
    </Box>
  );
};

// --- thanh toán -----------------------------------------------------------------------------------

const PAYMENT_LABEL: Record<string, string> = {
  OPEN: 'Chưa thanh toán', SUCCEEDED: 'Đã thanh toán', FAILED: 'Thanh toán thất bại', EXPIRED: 'Chưa thu tiền',
  REFUND_PENDING: 'Đang hoàn tiền', REFUNDED: 'Đã hoàn tiền', REFUND_FAILED: 'Hoàn tiền gặp sự cố',
};

export const PaymentPanel: React.FC<{ booking: BookingResponse; cancel?: React.ReactNode }> = ({ booking, cancel }) => {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    const done = () => { setCopied(true); setTimeout(() => setCopied(false), 3000); };
    try { void navigator.clipboard?.writeText(booking.referenceCode).then(done, () => undefined); } catch { /* không có quyền ghi clipboard */ }
  };
  const items = booking.groups.flatMap((g) => g.items);
  const paid = booking.payment && ['SUCCEEDED', 'REFUND_PENDING', 'REFUNDED', 'REFUND_FAILED'].includes(booking.payment.status);
  return (
    <Box title="Thông tin thanh toán">
      <div className="grid gap-2.5 px-4 py-4">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <span className="block text-[11px] text-slate-500">Mã đơn</span>
            <span className="break-all font-mono text-[13px] font-semibold text-slate-900" data-testid="panel-reference">{booking.referenceCode}</span>
          </div>
          <button type="button" onClick={copy}
            className="inline-flex min-h-9 flex-none items-center gap-1.5 rounded-full border border-slate-200 px-3 text-xs font-medium text-slate-700 hover:border-brand-600 hover:text-brand-700">
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" /> : <Copy className="h-3.5 w-3.5" aria-hidden="true" />}
            {copied ? 'Đã sao chép' : 'Sao chép'}
          </button>
        </div>
        <div className="flex justify-between gap-3 text-[13px]"><span className="text-slate-500">Đặt lúc</span><span className="tabular-nums">{formatDateTimeVn(booking.createdAt)}</span></div>
        {items.map((item) => (
          <div key={item.bookingItemId} className="flex justify-between gap-3 text-[13px]">
            <span className="min-w-0 break-words text-slate-500">{item.product.name}</span>
            <span className="whitespace-nowrap tabular-nums">{formatVnd(item.lineTotal)}</span>
          </div>
        ))}
        <div className="flex items-baseline justify-between gap-3 border-t border-dashed border-slate-200 pt-3 font-semibold">
          <span>Tổng thanh toán</span>
          <strong className="text-lg tabular-nums" data-testid="panel-total">{formatVnd(booking.total)}</strong>
        </div>
        <p className="-mt-1.5 text-right text-[11px] text-slate-500">Bao gồm thuế và phí</p>
        {booking.payment && (
          <div className="flex justify-between gap-3 text-[13px]">
            <span className="text-slate-500">Trạng thái thanh toán</span>
            <span className="font-medium">{PAYMENT_LABEL[booking.payment.status] ?? booking.payment.status}</span>
          </div>
        )}
        {paid && <div className="flex justify-between gap-3 text-[13px]"><span className="text-slate-500">Phương thức</span><span>Thẻ, qua Stripe</span></div>}
        {cancel}
      </div>
    </Box>
  );
};
