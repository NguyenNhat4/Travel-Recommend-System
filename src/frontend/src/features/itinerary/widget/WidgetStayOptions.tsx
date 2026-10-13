import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Check, Loader2, Star } from 'lucide-react';
import { getAirportPoints } from '../../../services/routeGeometry';
import { placeholderOnError } from './widgetVisuals';
import { stayCardKey } from './widgetPlan';
import type { StayOptionCard } from './widgetTypes';

const vnd = new Intl.NumberFormat('vi-VN');
const km = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 });

const short = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 });
const score = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 });

/** Số tiền làm tròn cho dễ đọc trên thẻ (3.979.522 → "3,98 triệu"); số đầy đủ nằm ở bảng chi phí cột phải. */
function roughMoney(value: number) {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${short.format(abs / 1_000_000)} triệu`;
  if (abs >= 1_000) return `${vnd.format(Math.round(abs / 1_000))} nghìn`;
  return `${vnd.format(abs)} ₫`;
}

/** Chip đánh đổi: xanh khi có lợi cho người dùng (rẻ hơn, đi ít hơn), cam khi ngược lại. */
function Chip({ good, children }: { good: boolean; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[13px] font-semibold tabular-nums ${good
      ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
      {children}
    </span>
  );
}

interface WidgetStayOptionsProps {
  cards: StayOptionCard[];
  /** Chỉ hàng thẻ của câu trả lời mới nhất, khi không có lượt nào đang chạy, mới xem trước và đổi được khách sạn. */
  interactive: boolean;
  /** Khoá (`stayCardKey`) của thẻ đang được lưu lên server; thẻ đó đã là "Đang chọn", cả hàng tạm khoá. */
  selectingKey: string | null;
  /** Khoá của thẻ đang xem trước ở cột phải (chưa đổi). */
  previewKey: string | null;
  /** Chạm thân thẻ: xem trước lịch của thẻ đó ở cột phải (thẻ đang chọn: thôi xem trước). */
  onPreview: (card: StayOptionCard) => void;
  /** Nút "Đổi sang khách sạn này": đổi lịch và lưu. */
  onSelect: (card: StayOptionCard) => void;
}

/**
 * Hàng thẻ "Phương án khác" (AC-AGT-04, chốt 2026-10-08), nội dung của mục "Nơi nghỉ": một thẻ cho lịch đang chọn và
 * một thẻ cho mỗi phương án khác, với chênh tiền, chênh km và vượt ngân sách do backend tính. Chạm thẻ thì thẻ nổi lên và
 * cột phải xem trước lịch của nó, chưa đổi; nút "Đổi sang khách sạn này" mới đổi: thẻ đó thành "Đang chọn", chênh tiền/km
 * của các thẻ tính lại theo lịch mới, không thêm tin nhắn.
 *
 * Thứ tự thẻ giữ như lần hiện đầu tiên (backend đưa lịch đang chọn lên đầu sau mỗi lần đổi; đảo chỗ làm hàng nhảy).
 */
export function WidgetStayOptions({ cards, interactive, selectingKey, previewKey, onPreview, onSelect }: WidgetStayOptionsProps) {
  const rowRef = useRef<HTMLDivElement>(null);
  const [seenOrder, setSeenOrder] = useState<string[]>([]);
  const unseen = cards.map(stayCardKey).filter((key) => !seenOrder.includes(key));
  const order = unseen.length ? [...seenOrder, ...unseen] : seenOrder;
  if (unseen.length) setSeenOrder(order);
  const ordered = [...cards].sort((a, b) => order.indexOf(stayCardKey(a)) - order.indexOf(stayCardKey(b)));
  const activeKey = selectingKey ?? stayCardKey(cards.find((card) => card.index === null) ?? cards[0]);
  const scroll = (direction: 1 | -1) => rowRef.current?.scrollBy({ left: direction * 260, behavior: 'smooth' });
  const locked = !interactive || selectingKey !== null;
  // Trượt hàng tới thẻ đang xem trước hoặc đang lưu, kể cả khi hàng vừa dựng lại (widget mở rộng là cây DOM khác). Hàng
  // là `relative` nên `offsetLeft` của thẻ tính từ mép hàng.
  const focusKey = previewKey ?? selectingKey;
  // Km của backend gồm chặng sân bay khi lịch có chặng bay có toạ độ (AC-AGT-04, chốt 2026-10-09).
  const known = cards.filter((card) => card.plan.totalEstimatedPrice != null);
  const leastStay = Math.min(...known.map((card) => card.plan.budgetSummary?.stays ?? Infinity));
  const leastKm = Math.min(...cards.map((card) => card.distanceKm));
  const fitting = known.filter((card) => card.overBudget == null && card.plan.budgetSummary?.status !== 'OVER_BUDGET');
  const balanced = [...(fitting.length ? fitting : known)].sort((a, b) =>
    Math.floor(a.distanceKm / 2) - Math.floor(b.distanceKm / 2) || (a.plan.totalEstimatedPrice ?? Infinity) - (b.plan.totalEstimatedPrice ?? Infinity))[0];
  const premium = cards.filter((card) => card.hotels.length && card.hotels.every((hotel) => (hotel.attributes?.starRating ?? 0) >= 4));
  const loved = premium.filter((card) => card.hotels.every((hotel) => (hotel.aggregateRating?.score ?? 0) >= 4.5 && (hotel.aggregateRating?.count ?? 0) >= 50));
  const luxury = [...(loved.length ? loved : premium)].sort((a, b) =>
    Math.min(...b.hotels.map((hotel) => hotel.aggregateRating?.score ?? 0)) - Math.min(...a.hotels.map((hotel) => hotel.aggregateRating?.score ?? 0))
    || Math.min(...b.hotels.map((hotel) => hotel.aggregateRating?.count ?? 0)) - Math.min(...a.hotels.map((hotel) => hotel.aggregateRating?.count ?? 0)))[0];
  const activeCard = cards.find((card) => stayCardKey(card) === activeKey) ?? cards[0];
  const withAirport = Boolean(activeCard && getAirportPoints(activeCard.plan).arrival);
  useEffect(() => {
    const row = rowRef.current;
    const card = focusKey ? row?.querySelector<HTMLElement>(`[data-stay-key="${CSS.escape(focusKey)}"]`) : null;
    if (row && card) row.scrollTo?.({ left: card.offsetLeft - 4, behavior: 'smooth' });
  }, [focusKey]);

  return (
    <section aria-label="Phương án khác" data-stay-row className="my-4 whitespace-normal">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-sm text-slate-600">So sánh các phương án tìm được · Chạm thẻ để xem trước, bấm "Đổi sang khách sạn này" để chọn</p>
        <div className="hidden gap-1 sm:flex">
          <button type="button" onClick={() => scroll(-1)} aria-label="Thẻ trước"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 hover:bg-slate-50">
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </button>
          <button type="button" onClick={() => scroll(1)} aria-label="Thẻ sau"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 hover:bg-slate-50">
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
      <div ref={rowRef} className="no-scrollbar relative -mx-1 flex snap-x snap-mandatory gap-3 overflow-x-auto scroll-smooth px-1 pb-2 pt-1">
        {ordered.map((card) => {
          const key = stayCardKey(card);
          const active = key === activeKey;
          const saving = active && selectingKey !== null;
          const previewed = !active && key === previewKey;
          const [hotel] = card.hotels;
          const stays = card.plan.stays ?? [];
          const labels: { name: string; detail: string; color: string }[] = [];
          if (card.plan.budgetSummary?.stays === leastStay) labels.push({ name: 'Tiết kiệm nhất', detail: 'Chi phí lưu trú thấp nhất trong các phương án.', color: 'bg-emerald-50 text-emerald-800' });
          if (card.distanceKm === leastKm) labels.push({ name: 'Ít di chuyển nhất', detail: 'Tổng khoảng cách ước tính thấp nhất.', color: 'bg-sky-50 text-sky-800' });
          if (card === balanced) labels.push({ name: 'Cân bằng', detail: 'Ưu tiên ngân sách, cân bằng giá và khoảng cách.', color: 'bg-blue-50 text-blue-800' });
          if (card === luxury) labels.push({ name: loved.includes(card) ? 'Cao cấp · Được yêu thích' : 'Cao cấp', detail: loved.includes(card) ? 'Khách sạn 4–5 sao được khách chấm điểm cao.' : 'Khách sạn 4–5 sao.', color: 'bg-amber-50 text-amber-900' });
          const stars = hotel?.attributes?.starRating;
          const rating = hotel?.aggregateRating;
          return (
            <div key={key} data-stay-key={key} className={`flex w-64 shrink-0 snap-start flex-col overflow-hidden rounded-2xl border bg-white
                transition-[border-color,box-shadow,opacity,transform] duration-300 ease-out ${active
                ? 'border-blue-600 shadow-md ring-2 ring-blue-600'
                : previewed ? '-translate-y-1 border-slate-300 shadow-lg'
                  : 'border-slate-200 hover:-translate-y-0.5 hover:shadow-md'}
                ${!active && locked ? 'opacity-60' : ''}`}>
              <button type="button" onClick={() => onPreview(card)}
                disabled={!active && locked} aria-pressed={active || previewed}
                aria-label={active ? `Đang chọn: ${hotel?.name ?? ''}`
                  : card.index != null ? `Xem trước phương án ${card.index}: ${hotel?.name ?? ''}` : `Khách sạn trước: ${hotel?.name ?? ''}`}
                className="flex flex-1 flex-col text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed">
              {/* Ảnh `absolute` để ảnh dọc không kéo khung 16:9 (khung là item của flex-col, min-height theo ảnh). */}
              <div className="relative aspect-[16/9] w-full shrink-0 overflow-hidden bg-slate-100">
                {hotel && (
                  <img src={hotel.imageUrl} alt="" onError={placeholderOnError(hotel.taxonomy)}
                    className="absolute inset-0 h-full w-full object-cover" />
                )}
                {/* Chỉ một trạng thái nổi bật là "Đang chọn"; thẻ đang xem trước chỉ có nhãn trắng nhỏ. */}
                {(active || previewed) && (
                  <span className={`absolute left-2 top-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[13px] font-semibold ${active
                    ? 'bg-blue-600 text-white' : 'bg-white/95 text-slate-800 shadow-sm'}`}>
                    {active ? <><Check className="h-3.5 w-3.5" aria-hidden="true" />Đang chọn</> : 'Đang xem trước'}
                  </span>
                )}
              </div>
              <div className="flex flex-1 flex-col gap-2 p-3">
                <div className="flex flex-wrap items-center gap-1" aria-label="Loại phương án">
                  {labels.map((label) => <span key={label.name} className={`rounded-lg px-2 py-1 text-xs font-bold ${label.color}`}>{label.name}</span>)}
                  {card.index != null && <span className="text-[13px] text-slate-600">Phương án {card.index}</span>}
                </div>
                {labels.map((label) => <p key={label.name} className="text-[13px] leading-snug text-slate-600">{label.detail}</p>)}
                <div>
                  {stays.length > 1 ? stays.map((stay) => (
                    // Đổi khách sạn giữa chuyến: ghi đêm của từng khách sạn, vì hai phương án có thể cùng hai khách sạn
                    // mà chia đêm khác nhau.
                    <p key={`${stay.productId}:${stay.fromNight}`} className="line-clamp-2 text-sm font-semibold leading-snug text-slate-900">
                      {`${stay.dayRange} · ${stay.product.name}${stay.rooms != null && stay.rooms > 1 ? ` · ${stay.rooms} phòng` : ''}`}
                    </p>
                  )) : (
                    <p className="line-clamp-2 text-sm font-semibold leading-snug text-slate-900">
                      {`${hotel?.name ?? ''}${stays[0]?.rooms != null && stays[0].rooms > 1 ? ` · ${stays[0].rooms} phòng` : ''}`}
                    </p>
                  )}
                  {/* Điểm khách chấm và hạng sao là hai thứ khác nhau: ★ chỉ đi với điểm, hạng sao ghi bằng chữ ở dòng riêng
                      (thẻ hẹp, gộp một dòng thì dấu "·" bị treo cuối dòng). */}
                  {rating?.score != null && (
                    <p className="mt-1 flex items-center gap-1 text-[13px] text-slate-600">
                      <Star className="h-3.5 w-3.5 shrink-0 fill-amber-400 text-amber-400" aria-hidden="true" />
                      <span className="font-semibold text-slate-800">{score.format(rating.score)}/5</span>
                      {rating.count != null && <span>({vnd.format(rating.count)} đánh giá)</span>}
                    </p>
                  )}
                  {typeof stars === 'number' && stars > 0 && <p className="text-[13px] text-slate-600">Khách sạn {stars} sao</p>}
                </div>
                <div className="border-t border-slate-100 pt-2">
                  <p className="flex items-baseline justify-between gap-2">
                    <span className="text-[13px] text-slate-600">Tổng chuyến</span>
                    <strong className="text-lg font-bold tabular-nums text-slate-900">
                      {card.plan.totalEstimatedPrice != null ? roughMoney(card.plan.totalEstimatedPrice) : 'Chưa đủ giá'}
                    </strong>
                  </p>
                  <dl className="mt-0.5 space-y-0.5 text-[13px] tabular-nums text-slate-600">
                    {card.plan.budgetSummary && (
                      <div className="flex justify-between gap-2"><dt>Lưu trú</dt><dd>{roughMoney(card.plan.budgetSummary.stays)}</dd></div>
                    )}
                    <div className="flex justify-between gap-2"><dt>Đi lại cả chuyến</dt><dd>≈{km.format(card.distanceKm)} km</dd></div>
                  </dl>
                </div>
                {/* Chip đi liền sau số tiền; khoảng dư khi thẻ bên cạnh cao hơn dồn xuống trên nút đáy. */}
                {card.index !== null && (
                  <div>
                    <p className="mb-1 text-[13px] text-slate-600">So với lựa chọn hiện tại</p>
                    <div className="flex flex-wrap gap-1.5">
                      <Chip good={card.moneyDelta <= 0}>
                        {card.moneyDelta === 0 ? 'Giá như nhau' : `${card.moneyDelta < 0 ? 'Rẻ hơn' : 'Đắt hơn'} ${roughMoney(card.moneyDelta)}`}
                      </Chip>
                      <Chip good={card.kmDelta <= 0}>
                        {`${card.kmDelta < 0 ? 'Gần hơn' : 'Xa hơn'} ≈${km.format(Math.abs(card.kmDelta))} km`}
                      </Chip>
                      {card.overBudget != null && (
                        <span className="inline-flex items-center rounded-full bg-rose-50 px-2 py-0.5 text-[13px] font-semibold text-rose-700 tabular-nums">
                          Vượt ngân sách {roughMoney(card.overBudget)}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
              </button>
              {active ? (
                // Dáng nút bị tắt nhưng chỉ là nhãn trạng thái: thân thẻ đã mang tên "Đang chọn: …" cho trình đọc màn hình.
                <span className="flex min-h-10 cursor-default items-center justify-center gap-1.5 border-t border-blue-100 bg-blue-50 text-[13px] font-semibold text-blue-700">
                  {saving
                    ? <><Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />Đang lưu…</>
                    : 'Đang chọn'}
                </span>
              ) : card.index == null ? (
                // Lịch cũ trong lúc đang lưu lịch mới (< 0,1 s): chưa có số phương án nên chưa đổi lại được.
                <span className="flex min-h-10 items-center justify-center border-t border-slate-100 text-[13px] text-slate-500">
                  Khách sạn trước
                </span>
              ) : (
                <button type="button" onClick={() => onSelect(card)} disabled={locked}
                  aria-label={`Đổi sang phương án ${card.index}: ${hotel?.name ?? ''}`}
                  className="flex min-h-10 items-center justify-center gap-1.5 border-t border-slate-100 text-[13px] font-semibold text-blue-700
                    transition-colors duration-300 hover:bg-blue-50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600
                    disabled:cursor-not-allowed">
                  Đổi sang khách sạn này
                </button>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-1 text-[13px] text-slate-600">
        {withAirport
          ? 'Số km là ước tính quãng đường di chuyển cả hành trình, gồm cả đường sân bay.'
          : 'Số km là ước tính quãng đường di chuyển cả hành trình.'}
      </p>
    </section>
  );
}
