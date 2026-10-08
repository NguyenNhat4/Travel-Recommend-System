import React, { useEffect, useRef } from 'react';
import { ChevronLeft, ChevronRight, Check, Loader2, Star } from 'lucide-react';
import { placeholderOnError } from './widgetVisuals';
import { stayCardKey } from './widgetPlan';
import type { StayOptionCard } from './widgetTypes';

const vnd = new Intl.NumberFormat('vi-VN');
const km = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 });

function money(value: number) {
  return `${vnd.format(Math.abs(value))} ₫`;
}

/** Chip đánh đổi: xanh khi có lợi cho người dùng (rẻ hơn, đi ít hơn), cam khi ngược lại. */
function Chip({ good, children }: { good: boolean; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${good
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
  const orderRef = useRef<string[]>([]);
  for (const card of cards) {
    if (!orderRef.current.includes(stayCardKey(card))) orderRef.current.push(stayCardKey(card));
  }
  const ordered = [...cards].sort((a, b) => orderRef.current.indexOf(stayCardKey(a)) - orderRef.current.indexOf(stayCardKey(b)));
  const activeKey = selectingKey ?? stayCardKey(cards.find((card) => card.index === null) ?? cards[0]);
  const scroll = (direction: 1 | -1) => rowRef.current?.scrollBy({ left: direction * 260, behavior: 'smooth' });
  const locked = !interactive || selectingKey !== null;
  // Trượt hàng tới thẻ đang xem trước hoặc đang lưu, kể cả khi hàng vừa dựng lại (widget mở rộng là cây DOM khác). Hàng
  // là `relative` nên `offsetLeft` của thẻ tính từ mép hàng.
  const focusKey = previewKey ?? selectingKey;
  useEffect(() => {
    const row = rowRef.current;
    const card = focusKey ? row?.querySelector<HTMLElement>(`[data-stay-key="${CSS.escape(focusKey)}"]`) : null;
    if (row && card) row.scrollTo?.({ left: card.offsetLeft - 4, behavior: 'smooth' });
  }, [focusKey]);

  return (
    <section aria-label="Phương án khác" data-stay-row className="my-4 whitespace-normal">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-sm text-slate-500">Chạm thẻ để xem trước, bấm "Đổi" để chọn khách sạn</p>
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
          const stars = hotel?.attributes?.starRating;
          return (
            <div key={key} data-stay-key={key} className={`flex w-60 shrink-0 snap-start flex-col overflow-hidden rounded-2xl border bg-white
                transition-[border-color,box-shadow,opacity,transform] duration-300 ease-out ${active
                ? 'border-blue-600 shadow-md ring-2 ring-blue-600'
                : previewed ? '-translate-y-1 border-blue-400 shadow-lg ring-1 ring-blue-400'
                  : 'border-slate-200 hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-sm'}
                ${!active && locked ? 'opacity-60' : ''}`}>
              <button type="button" onClick={() => onPreview(card)}
                disabled={!active && locked} aria-pressed={active || previewed}
                aria-label={active ? `Đang chọn: ${hotel?.name ?? ''}`
                  : card.index != null ? `Xem trước phương án ${card.index}: ${hotel?.name ?? ''}` : `Khách sạn trước: ${hotel?.name ?? ''}`}
                className="flex flex-1 flex-col text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed">
              <div className="relative aspect-[16/9] w-full bg-slate-100">
                {hotel && (
                  <img src={hotel.imageUrl} alt="" onError={placeholderOnError(hotel.taxonomy)}
                    className="h-full w-full object-cover" />
                )}
                <span className={`absolute left-2 top-2 rounded-full px-2 py-0.5 text-xs font-semibold transition-colors duration-300 ${active
                  ? 'bg-blue-600 text-white' : previewed ? 'bg-blue-50 text-blue-700' : 'bg-white/90 text-slate-800'}`}>
                  {active ? 'Đang chọn' : previewed ? 'Đang xem trước' : card.index != null ? `Phương án ${card.index}` : 'Khách sạn trước'}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-2 p-3">
                <div>
                  {stays.length > 1 ? stays.map((stay) => (
                    // Đổi khách sạn giữa chuyến: ghi đêm của từng khách sạn, vì hai phương án có thể cùng hai khách sạn
                    // mà chia đêm khác nhau.
                    <p key={`${stay.productId}:${stay.fromNight}`} className="line-clamp-2 text-sm font-semibold leading-snug text-slate-900">
                      {`${stay.dayRange} · ${stay.product.name}`}
                    </p>
                  )) : <p className="line-clamp-2 text-sm font-semibold leading-snug text-slate-900">{hotel?.name}</p>}
                  <p className="mt-1 flex items-center gap-1 text-xs text-slate-500">
                    {typeof stars === 'number' && stars > 0 && (
                      <span className="inline-flex items-center gap-0.5 text-amber-500">
                        <Star className="h-3 w-3 fill-current" aria-hidden="true" />{stars}
                      </span>
                    )}
                    {hotel?.priceString && <span className="tabular-nums">{hotel.priceString}/đêm</span>}
                  </p>
                </div>
                <div className="mt-auto flex flex-wrap gap-1.5">
                  {card.index === null ? (
                    <span className="text-xs text-slate-600 tabular-nums">Đi lại ~{km.format(card.distanceKm)} km cả chuyến</span>
                  ) : (
                    <>
                      <Chip good={card.moneyDelta <= 0}>
                        {card.moneyDelta === 0 ? 'Giá như cũ' : `${card.moneyDelta < 0 ? '−' : '+'}${money(card.moneyDelta)}`}
                      </Chip>
                      <Chip good={card.kmDelta <= 0}>
                        {`${card.kmDelta < 0 ? '−' : '+'}${km.format(Math.abs(card.kmDelta))} km`}
                      </Chip>
                      {card.overBudget != null && (
                        <span className="inline-flex items-center rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-700 tabular-nums">
                          Vượt ngân sách {money(card.overBudget)}
                        </span>
                      )}
                    </>
                  )}
                </div>
              </div>
              </button>
              {active ? (
                <span className="flex min-h-10 items-center justify-center gap-1.5 border-t border-blue-100 bg-blue-50 text-xs font-semibold text-blue-700">
                  {saving
                    ? <><Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />Đang lưu…</>
                    : <><Check className="h-3.5 w-3.5" aria-hidden="true" />Đang dùng</>}
                </span>
              ) : card.index == null ? (
                // Lịch cũ trong lúc đang lưu lịch mới (< 0,1 s): chưa có số phương án nên chưa đổi lại được.
                <span className="flex min-h-10 items-center justify-center border-t border-slate-100 text-xs text-slate-400">
                  Khách sạn trước
                </span>
              ) : (
                <button type="button" onClick={() => onSelect(card)} disabled={locked}
                  aria-label={`Đổi sang phương án ${card.index}: ${hotel?.name ?? ''}`}
                  className={`flex min-h-10 items-center justify-center gap-1.5 border-t text-xs font-semibold transition-colors duration-300
                    focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed ${previewed
                    ? 'border-blue-600 bg-blue-600 text-white hover:bg-blue-700' : 'border-slate-100 text-blue-600 hover:bg-blue-50'}`}>
                  Đổi sang khách sạn này
                </button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
