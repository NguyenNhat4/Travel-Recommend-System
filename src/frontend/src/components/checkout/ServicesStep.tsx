'use client';

/**
 * Bước ② Dịch vụ (spec checkout-nhieu-buoc-hanh-khach.md §6.6): chọn ai dùng từng dịch vụ; khách sạn xếp người vào từng phòng.
 * Giá của mỗi thẻ lấy từ `fares` và `lineTotal` do Backend trả về sau mỗi lần sửa số khách; trong lúc chờ thì hiện khung chờ.
 */
import React, { useState } from 'react';
import { AlertTriangle, ArrowLeft, ArrowRight, BedDouble, CircleAlert, Check, ChevronRight, Info, MapPin, Trash2, X } from 'lucide-react';
import { getProduct } from '../../services/catalog';
import type { ApiCartItem } from '../../services/booking';
import { TaxonomyBadge } from '../common/TaxonomyBadge';
import { formatVnd } from '../confirmation/bookingLabels';
import type { Taxonomy } from '../../types/travel';
import {
  displayName, draftToTraveler, isHotel, isInfantForItem, maxOccupancyOf, shortName, unassignedRefs, type Allocation, type TravelerDraft,
} from './allocation';
import { MAX_PARTY, adultFrom, ageOn, fareTypeOn, formatDmy, messageFor, type Violation } from './checkoutRules';
import { ErrorSummaryBox, Notice, PrimaryButton, Skeleton } from './CheckoutParts';
import { FareLines } from './FareLines';
import type { CheckoutController } from './useCheckout';

const EMPTY: Allocation = { refs: [], rooms: [], custom: false };

function dateText(item: ApiCartItem): string {
  if (isHotel(item)) {
    const end = new Date(`${item.usingDate}T00:00:00Z`);
    end.setUTCDate(end.getUTCDate() + (item.nights ?? 1));
    return `${formatDmy(item.usingDate).slice(0, 5)} → ${formatDmy(end.toISOString().slice(0, 10))} · ${item.nights ?? 1} đêm`;
  }
  return formatDmy(item.usingDate);
}

/** Nhãn loại khách của một người ở một dịch vụ (theo tuổi tại ngày dùng dịch vụ đó). */
function typeTag(d: TravelerDraft, item: ApiCartItem): { text: string; className: string } {
  const traveler = draftToTraveler(d);
  if (fareTypeOn(traveler, item.usingDate) === 'ADULT') {
    return { text: d.type === 'CHILD' ? 'Người lớn (đủ 12t)' : 'Người lớn', className: 'bg-blue-50 text-blue-700' };
  }
  const age = traveler.birth ? ageOn(traveler.birth, item.usingDate) : null;
  if (item.product.taxonomy === 'flight' && isInfantForItem(d, item)) return { text: `Em bé, ${age} tuổi`, className: 'bg-rose-50 text-rose-700' };
  return { text: `Trẻ em${age !== null ? `, ${age} tuổi` : ''}`, className: 'bg-amber-50 text-amber-800' };
}

const violationsOf = (all: Violation[], id: string) => all.filter((v) => v.cartItemId === id);
const roomIndexOf = (v: Violation) => { const m = /rooms\[(\d+)\]/.exec(v.field); return m ? Number(m[1]) : null; };

/** Các dòng giá của mục theo `fares` của Backend; trong lúc chờ PATCH thì hiện khung chờ. */
const FareBox: React.FC<{ item: ApiCartItem; pending: boolean }> = ({ item, pending }) => {
  if (pending) return <div className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2.5 space-y-1.5"><Skeleton width={180} /><br /><Skeleton width={140} /></div>;
  return <FareLines fares={item.fares ?? []} />;
};

/** Điều kiện vé trẻ em của điểm đến: tải văn bản `attributes.policies` khi khách mở mục này (không nhét vào mọi lần đọc giỏ). */
const PolicyNote: React.FC<{ productId: string }> = ({ productId }) => {
  const [text, setText] = useState<string | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'done'>('idle');
  const load = () => {
    if (state !== 'idle') return;
    setState('loading');
    getProduct(productId)
      .then((detail) => {
        const policies = (detail.attributes as Record<string, unknown> | undefined)?.policies;
        const parts = policies && typeof policies === 'object' ? Object.values(policies as Record<string, unknown>) : policies ? [policies] : [];
        setText(parts.map(String).join('\n\n') || null);
      })
      .catch(() => setText(null))
      .finally(() => setState('done'));
  };
  return (
    <details className="text-xs" onToggle={(e) => { if ((e.currentTarget as HTMLDetailsElement).open) load(); }}>
      <summary className="cursor-pointer select-none text-blue-600 font-semibold inline-flex items-center gap-1">
        <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />Điều kiện vé trẻ em của điểm đến
      </summary>
      <p className="mt-2 text-slate-600 leading-relaxed bg-slate-50 border border-slate-100 rounded-lg px-3 py-2 whitespace-pre-line">
        {state === 'loading' ? 'Đang tải…' : text ?? 'Chưa có thông tin điều kiện vé trẻ em cho điểm đến này.'}
      </p>
    </details>
  );
};

const ErrorList: React.FC<{ messages: string[] }> = ({ messages }) => (messages.length ? (
  <ul className="space-y-1">
    {messages.map((m, i) => <li key={i} className="text-xs text-rose-600 font-medium flex items-start gap-1.5"><CircleAlert className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden="true" />{m}</li>)}
  </ul>
) : null);

const CardShell: React.FC<{
  item: ApiCartItem; ctl: CheckoutController; invalid: boolean; pill?: React.ReactNode; children: React.ReactNode;
}> = ({ item, ctl, invalid, pill, children }) => {
  const pending = Boolean(ctl.pending[item.cartItemId]);
  const failed = ctl.patchErrors[item.cartItemId];
  return (
    <article id={`card-${item.cartItemId}`} tabIndex={-1} data-testid="service-card"
      className={`bg-white rounded-2xl border shadow-xs outline-hidden ${invalid ? 'border-rose-300' : 'border-slate-200'}`}>
      <header className="p-4 sm:p-5 flex items-start justify-between gap-3 border-b border-slate-100">
        <div className="min-w-0 space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <TaxonomyBadge taxonomy={item.product.taxonomy as Taxonomy} size="sm" />
            {pill}
          </div>
          <h3 className="text-sm font-bold text-slate-900 leading-snug">{item.product.name}</h3>
          <p className="text-xs text-slate-500 tabular-nums">{dateText(item)}</p>
        </div>
        {invalid || failed ? (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-700 bg-rose-50 border border-rose-200 rounded-full px-2 py-0.5 whitespace-nowrap"><CircleAlert className="w-3 h-3" aria-hidden="true" />Cần sửa</span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5 whitespace-nowrap"><Check className="w-3 h-3" aria-hidden="true" />Đủ thông tin</span>
        )}
      </header>
      <div className="p-4 sm:p-5 space-y-4">
        {children}
        {failed && (
          <div role="alert" className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 flex items-start justify-between gap-2">
            <span>{failed.message}</span>
            {['PRODUCT_UNAVAILABLE', 'DATE_OUT_OF_RANGE'].includes(failed.code) && (
              <button type="button" onClick={() => void ctl.removeItem(item.cartItemId)} className="shrink-0 font-bold underline inline-flex items-center gap-1"><Trash2 className="w-3 h-3" aria-hidden="true" />{ctl.sourceKind === 'cart' ? 'Xoá khỏi giỏ' : 'Bỏ khỏi lần đặt'}</button>
            )}
          </div>
        )}
        <div className="flex items-center justify-between pt-3 border-t border-slate-100">
          <span className="text-xs text-slate-500">Thành tiền</span>
          {pending ? <Skeleton width={100} /> : <span className="text-base font-extrabold text-slate-900 tabular-nums" data-testid="line-total">{formatVnd(item.lineTotal)}</span>}
        </div>
        <textarea
          rows={1} maxLength={500} value={ctl.special[item.cartItemId] ?? ''} onChange={(e) => ctl.setSpecialRequest(item.cartItemId, e.target.value)}
          placeholder="Yêu cầu đặc biệt (không bắt buộc, tối đa 500 ký tự)" aria-label={`Yêu cầu đặc biệt cho ${item.product.name}`}
          className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-2 focus:ring-blue-500 resize-y"
        />
      </div>
    </article>
  );
};

const PersonCard: React.FC<{ ctl: CheckoutController; item: ApiCartItem }> = ({ ctl, item }) => {
  const alloc = ctl.allocs[item.cartItemId] ?? EMPTY;
  const errors = [
    ...violationsOf(ctl.itemViolations, item.cartItemId).map(messageFor), ...(ctl.serverItemErrors[item.cartItemId] ?? []),
  ];
  const n = alloc.refs.length;
  const total = ctl.drafts.length;
  const hasChild = alloc.refs.some((ref) => { const d = ctl.drafts.find((x) => x.ref === ref); return d && fareTypeOn(draftToTraveler(d), item.usingDate) === 'CHILD'; });
  const childFare = (item.fares ?? []).find((f) => f.fareType === 'CHILD');
  const adultFare = (item.fares ?? []).find((f) => f.fareType === 'ADULT');
  const sameChildPrice = childFare && adultFare && childFare.unitPrice === adultFare.unitPrice;
  const flight = item.product.taxonomy === 'flight';
  return (
    <CardShell item={item} ctl={ctl} invalid={errors.length > 0}
      pill={n > 0 && n < total ? <span className="text-[11px] font-semibold text-slate-600 bg-slate-100 rounded-full px-2 py-0.5 tabular-nums">{n}/{total} khách</span> : null}>
      <fieldset className="space-y-2">
        <legend className="text-xs font-semibold text-slate-700 mb-2">{flight ? 'Hành khách trên chuyến' : item.product.taxonomy === 'combo' ? 'Ai dùng gói?' : 'Ai dùng vé?'}</legend>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {ctl.drafts.map((d) => {
            const on = alloc.refs.includes(d.ref);
            const tag = typeTag(d, item);
            const name = displayName(d, ctl.drafts);
            return (
              <label key={d.ref} className={`flex items-center gap-2.5 rounded-lg border px-3 py-2 cursor-pointer hover:border-blue-400 ${on ? 'border-blue-300 bg-blue-50/50' : 'border-slate-200 bg-white'}`}>
                <input type="checkbox" checked={on} onChange={() => ctl.toggleTraveler(item.cartItemId, d.ref)} aria-label={`${name} dùng ${item.product.name}`} className="w-4 h-4 accent-blue-600 shrink-0" />
                <span className="text-sm text-slate-800 font-medium truncate">{name}</span>
                <span className={`ml-auto text-[11px] font-semibold rounded px-1.5 py-0.5 whitespace-nowrap ${tag.className}`}>{tag.text}</span>
              </label>
            );
          })}
        </div>
      </fieldset>
      <ErrorList messages={errors} />
      <FareBox item={item} pending={Boolean(ctl.pending[item.cartItemId])} />
      {flight && hasChild && (
        <div className="flex items-start gap-2 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
          <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden="true" />
          Chưa có giá vé trẻ em riêng: trẻ em và em bé có ghế riêng, tính giá người lớn.
        </div>
      )}
      {!flight && item.product.taxonomy !== 'combo' && hasChild && sameChildPrice && <p className="text-xs text-slate-600">Trẻ em: cùng giá người lớn</p>}
      {(item.product.taxonomy === 'attraction' || item.product.taxonomy === 'golf') && hasChild && <PolicyNote productId={item.product.productId} />}
    </CardShell>
  );
};

const HotelCard: React.FC<{ ctl: CheckoutController; item: ApiCartItem }> = ({ ctl, item }) => {
  const alloc = ctl.allocs[item.cartItemId] ?? EMPTY;
  const all = violationsOf(ctl.itemViolations, item.cartItemId);
  const cardErrors = [...all.filter((v) => roomIndexOf(v) === null).map(messageFor), ...(ctl.serverItemErrors[item.cartItemId] ?? [])];
  const roomErrors = (k: number) => [...all.filter((v) => roomIndexOf(v) === k).map(messageFor), ...(ctl.serverRoomErrors[item.cartItemId]?.[k] ?? [])];
  const rooms = alloc.rooms.length;
  const cap = maxOccupancyOf(item);
  const unassigned = unassignedRefs(item, alloc, ctl.drafts);
  const leads = new Set(alloc.rooms.map((r) => r.lead).filter(Boolean));
  const adultsOnDate = ctl.drafts.filter((d) => fareTypeOn(draftToTraveler(d), item.usingDate) === 'ADULT');
  const canAddRoom = rooms < MAX_PARTY && adultsOnDate.some((d) => !leads.has(d.ref));
  const invalidCard = cardErrors.length > 0 || alloc.rooms.some((_, k) => roomErrors(k).length > 0);
  const guestTotal = alloc.rooms.reduce((n, r) => n + r.refs.length, 0);
  const nameOf = (ref: string) => { const d = ctl.drafts.find((x) => x.ref === ref); return d ? displayName(d, ctl.drafts) : ref; };
  const chip = (ref: string, roomIndex: number | null) => {
    const d = ctl.drafts.find((x) => x.ref === ref);
    if (!d) return null;
    const tag = typeTag(d, item);
    const options = alloc.rooms.map((_, k) => k).filter((k) => k !== roomIndex);
    return (
      <span key={ref} className={`inline-flex items-center gap-1 rounded-full border bg-white pl-3 pr-1 py-1 text-xs ${roomIndex === null ? 'border-amber-300' : 'border-slate-200'}`}>
        <span className="font-semibold text-slate-800">{shortName(d, ctl.drafts)}</span>
        <span className={`text-[11px] font-semibold rounded px-1 ${tag.className}`}>{tag.text}</span>
        {options.length > 0 && (
          <select aria-label={`Chuyển ${nameOf(ref)} sang phòng khác`} value="" onChange={(e) => { if (e.target.value !== '') ctl.moveToRoom(item.cartItemId, ref, Number(e.target.value)); }}
            className="text-xs font-semibold text-blue-700 bg-transparent border-0 py-0 pl-1 pr-0 rounded cursor-pointer focus:ring-2 focus:ring-blue-500">
            <option value="">{roomIndex === null ? 'Xếp vào…' : 'Đổi phòng'}</option>
            {options.map((k) => <option key={k} value={k}>Phòng {k + 1}</option>)}
          </select>
        )}
        {roomIndex !== null && (
          <button type="button" onClick={() => ctl.removeFromRoom(item.cartItemId, ref)} aria-label={`Bỏ ${nameOf(ref)} khỏi phòng ${roomIndex + 1}`}
            className="w-6 h-6 rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-700 flex items-center justify-center"><X className="w-3.5 h-3.5" aria-hidden="true" /></button>
        )}
      </span>
    );
  };
  return (
    <CardShell item={item} ctl={ctl} invalid={invalidCard}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-slate-800">Số phòng</span>
          <button type="button" onClick={() => ctl.removeRoom(item.cartItemId)} disabled={rooms <= 1} aria-label="Bớt phòng"
            className="w-8 h-8 rounded-full border border-slate-300 text-slate-700 flex items-center justify-center hover:border-blue-500 hover:text-blue-600 disabled:opacity-40 disabled:cursor-not-allowed">−</button>
          <span className="w-5 text-center font-bold tabular-nums" aria-live="polite">{rooms}</span>
          <button type="button" onClick={() => ctl.addRoom(item.cartItemId)} disabled={!canAddRoom} aria-label="Thêm phòng"
            className="w-8 h-8 rounded-full border border-slate-300 text-slate-700 flex items-center justify-center hover:border-blue-500 hover:text-blue-600 disabled:opacity-40 disabled:cursor-not-allowed">+</button>
        </div>
        <span className="text-xs text-slate-500">{cap ? `Tối đa ${cap} khách/phòng` : 'Khách sạn chưa công bố sức chứa phòng'}</span>
      </div>
      <div className={`grid grid-cols-1 gap-3 ${rooms > 1 ? 'sm:grid-cols-2' : ''}`}>
        {alloc.rooms.map((room, k) => {
          const errs = roomErrors(k);
          const roomAdults = room.refs.filter((ref) => adultsOnDate.some((d) => d.ref === ref));
          const over = cap !== null && room.refs.length > cap;
          return (
            <div key={k} id={`room-${item.cartItemId}-${k}`} tabIndex={-1} data-testid="room"
              className={`rounded-xl border p-3 space-y-2.5 outline-hidden ${errs.length ? 'border-rose-300 bg-rose-50/50' : 'border-slate-200 bg-slate-50/60'}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5"><BedDouble className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />Phòng {k + 1}</span>
                <span className={`text-xs tabular-nums ${over ? 'text-rose-600 font-bold' : 'text-slate-500'}`}>{room.refs.length}{cap ? `/${cap}` : ''} khách</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {room.refs.length ? room.refs.map((ref) => chip(ref, k)) : <span className="text-xs text-slate-500 italic py-1">Chưa có khách</span>}
              </div>
              {roomAdults.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <label htmlFor={`lead-${item.cartItemId}-${k}`} className="text-[11px] text-slate-600">Người đại diện nhận phòng</label>
                  <select id={`lead-${item.cartItemId}-${k}`} value={room.lead ?? ''} onChange={(e) => ctl.setLead(item.cartItemId, k, e.target.value)}
                    aria-label={`Người đại diện nhận phòng (Phòng ${k + 1})`} className="text-xs py-1 border border-slate-300 rounded-lg pl-2 pr-7 bg-white focus:ring-2 focus:ring-blue-500">
                    {roomAdults.map((ref) => <option key={ref} value={ref}>{nameOf(ref)}</option>)}
                  </select>
                </div>
              )}
              <ErrorList messages={errs} />
              {roomAdults.length === 0 && adultsOnDate.length < rooms && (
                <button type="button" onClick={() => ctl.removeRoom(item.cartItemId)} className="text-xs font-semibold text-blue-600 hover:underline">− Bớt phòng</button>
              )}
            </div>
          );
        })}
      </div>
      {unassigned.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 space-y-2">
          <div className="text-xs font-semibold text-amber-900 flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />Còn {unassigned.length} khách chưa có phòng</div>
          <div className="flex flex-wrap gap-1.5 items-center">
            {unassigned.map((ref) => chip(ref, null))}
            {canAddRoom && (
              <button type="button" onClick={() => ctl.addRoom(item.cartItemId)} className="text-xs font-bold text-blue-700 bg-white border border-blue-200 hover:bg-blue-50 rounded-full px-3 py-1">+ Thêm phòng</button>
            )}
          </div>
        </div>
      )}
      <ErrorList messages={cardErrors} />
      <FareBox item={item} pending={Boolean(ctl.pending[item.cartItemId])} />
      <p className="text-[11px] text-slate-500">Giá tính theo phòng/đêm; số khách không làm đổi giá phòng. {guestTotal > 0 ? `${guestTotal} khách đã xếp phòng.` : ''}</p>
    </CardShell>
  );
};

/** Cảnh báo không chặn (§5.4): W-01, W-03, W-04. */
function warningsOf(ctl: CheckoutController): string[] {
  const out: string[] = [];
  const used = new Set(ctl.items.flatMap((item) => ctl.refsOfItem(item)));
  for (const d of ctl.drafts) if (!used.has(d.ref)) out.push(`${displayName(d, ctl.drafts)} chưa có dịch vụ nào trong đơn.`);
  for (const d of ctl.drafts.filter((x) => x.type === 'CHILD')) {
    const birth = ctl.parseDob(d.birthText);
    if (!birth) continue;
    const turned = adultFrom(birth);
    if (ctl.items.some((item) => item.usingDate >= turned && ctl.refsOfItem(item).includes(d.ref))) {
      out.push(`Từ ${formatDmy(turned)}, ${displayName(d, ctl.drafts)} tính giá người lớn.`);
    }
  }
  const hotels = ctl.items.filter(isHotel);
  for (let i = 0; i < hotels.length; i += 1) {
    for (let j = i + 1; j < hotels.length; j += 1) {
      const endOf = (h: ApiCartItem) => { const e = new Date(`${h.usingDate}T00:00:00Z`); e.setUTCDate(e.getUTCDate() + (h.nights ?? 1)); return e.toISOString().slice(0, 10); };
      const start = hotels[i].usingDate > hotels[j].usingDate ? hotels[i].usingDate : hotels[j].usingDate;
      if (start < endOf(hotels[i]) && start < endOf(hotels[j])) {
        const shared = ctl.refsOfItem(hotels[i]).filter((ref) => ctl.refsOfItem(hotels[j]).includes(ref));
        for (const ref of shared) {
          const d = ctl.drafts.find((x) => x.ref === ref);
          if (d) out.push(`${displayName(d, ctl.drafts)} đang ở 2 khách sạn trong đêm ${formatDmy(start).slice(0, 5)}.`);
        }
      }
    }
  }
  return out;
}

export const ServicesStep: React.FC<{ ctl: CheckoutController }> = ({ ctl }) => {
  const groups = new Map<string, ApiCartItem[]>();
  for (const item of ctl.items) {
    const destination = item.product.destination || 'Khác';
    groups.set(destination, [...(groups.get(destination) ?? []), item]);
  }
  const warnings = warningsOf(ctl);
  return (
    <>
      <div className="space-y-1">
        <h2 id="step-heading" tabIndex={-1} className="text-xl font-extrabold text-slate-900 outline-hidden">Dịch vụ</h2>
        <p className="text-sm text-slate-500">Chọn ai dùng từng dịch vụ. Giá cập nhật theo số người lớn và trẻ em.</p>
      </div>
      {ctl.cartChanged && (
        <div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 flex items-start justify-between gap-2">
          <span>{ctl.sourceKind === 'cart' ? 'Giỏ hàng' : 'Lần đặt'} vừa thay đổi. Danh sách dịch vụ đã được cập nhật.</span>
          <button type="button" onClick={ctl.dismissCartChanged} className="font-bold underline shrink-0">Đóng</button>
        </div>
      )}
      {ctl.notice && <Notice>{ctl.notice}</Notice>}
      <ErrorSummaryBox entries={ctl.summary} onJump={ctl.focusId} />
      {warnings.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900 space-y-1" data-testid="warnings">
          {warnings.map((w) => <div key={w} className="flex items-start gap-2"><AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden="true" /><span>{w}</span></div>)}
        </div>
      )}
      {[...groups.entries()].map(([destination, list]) => (
        <section key={destination} className="space-y-3" aria-label={`Chuyến ${destination}`}>
          <div className="flex items-center gap-2 text-xs font-bold text-slate-500 uppercase tracking-wider"><MapPin className="w-3.5 h-3.5" aria-hidden="true" />Chuyến {destination}</div>
          <div className="space-y-4">
            {list.map((item) => (isHotel(item) ? <HotelCard key={item.cartItemId} ctl={ctl} item={item} /> : <PersonCard key={item.cartItemId} ctl={ctl} item={item} />))}
          </div>
        </section>
      ))}
      <div className="flex items-center justify-between gap-3">
        <button type="button" onClick={() => ctl.goto('travelers')} className="px-4 py-3 text-sm font-semibold text-slate-700 hover:text-slate-900 inline-flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />Quay lại
        </button>
        <div className="hidden lg:block">
          <PrimaryButton onClick={() => void ctl.continueFromServices()} busy={ctl.busy}>Tiếp tục <ArrowRight className="w-4 h-4" aria-hidden="true" /></PrimaryButton>
        </div>
      </div>
    </>
  );
};
