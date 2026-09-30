'use client';

import React from 'react';
import { AlertCircle, CalendarDays, Check, CloudSun, Compass, ExternalLink, MapPin, PackageOpen, Repeat, ShoppingCart, Sparkles, Users } from 'lucide-react';
import type { components } from '../../types/api.gen';
import { splitBoldTitle } from './inlineBold';
import {
  ACTIVITY_TYPE_LABEL,
  BUDGET_STATUS_LABEL,
  PARTY_TYPE_LABEL,
  SLOT_TIME_LABEL,
  priceUnitSuffix,
  taxonomyLabel,
} from './assistantLabels';

type Response = components['schemas']['ItineraryResponse'];
type Product = components['schemas']['ProductSummary'];
type IntentPatch = components['schemas']['TripIntentPatch'];
type Itinerary = components['schemas']['ItineraryPlan'];

export interface AssistantCartItem {
  product: Product;
  usingDate?: string;
  checkOutDate?: string;
}

const MIN_TRIP_DAYS = 1;
const MAX_TRIP_DAYS = 7;

/** Cùng tiêu chí với `bookableCount`: còn trong dữ liệu nguồn, có giá, không bị đánh dấu không đặt được hay không bán vé. */
export function isCartEligible(product: Product) {
  return product.available && product.unitPrice != null && product.bookable !== false && product.attributes?.ticketed !== false;
}

function addDays(isoDate: string, days: number) {
  const date = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return undefined;
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** Gom mọi sản phẩm đặt được của lịch trình, mỗi productId một lần, kèm ngày dùng theo ngày của lịch trình. */
export function itineraryCartItems(itinerary: Itinerary): AssistantCartItem[] {
  const items = new Map<string, AssistantCartItem>();
  if (itinerary.stay && isCartEligible(itinerary.stay.product)) {
    const checkIn = itinerary.days[0]?.date ?? undefined;
    items.set(itinerary.stay.product.productId, {
      product: itinerary.stay.product,
      usingDate: checkIn,
      checkOutDate: checkIn ? addDays(checkIn, itinerary.stay.nights) : undefined,
    });
  }
  for (const day of itinerary.days) {
    for (const slot of day.slots) {
      if (!slot.product || !isCartEligible(slot.product) || items.has(slot.product.productId)) continue;
      items.set(slot.product.productId, { product: slot.product, usingDate: day.date ?? undefined });
    }
  }
  return [...items.values()];
}

function formatMoney(amount: number | null | undefined, currency: string) {
  if (amount == null) return 'Chưa đủ dữ liệu để tính tổng';
  try {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency }).format(amount);
  } catch {
    return `${new Intl.NumberFormat('vi-VN').format(amount)} ${currency}`;
  }
}

function ProductCard({
  product,
  note,
  onAddToCart,
  onReplace,
  replaceDisabled = false,
}: {
  product: Product;
  note?: string | null;
  onAddToCart?: () => void;
  onReplace?: () => void;
  replaceDisabled?: boolean;
}) {
  const detailHref = `/product/${encodeURIComponent(product.productId)}`;
  const suffix = product.unitPrice != null ? priceUnitSuffix(product.priceUnit) : '';
  return (
    <article className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:border-blue-200 hover:shadow-md">
      <div className="flex gap-3 p-3 sm:gap-4 sm:p-4">
        <a href={detailHref} target="_blank" rel="noopener noreferrer" tabIndex={-1} aria-hidden="true" className="shrink-0">
          {product.imageUrl ? (
            <img src={product.imageUrl} alt="" className="h-24 w-28 rounded-xl bg-slate-100 object-cover sm:h-28 sm:w-36" />
          ) : (
            <div className="flex h-24 w-28 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-100 via-sky-50 to-white text-indigo-400 sm:h-28 sm:w-36">
              <Compass className="h-8 w-8" />
            </div>
          )}
        </a>
        <div className="min-w-0 flex-1 py-0.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-blue-700">{taxonomyLabel(product.taxonomy)}</span>
            {product.available && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700"><Check className="h-3 w-3" /> Đang mở bán</span>}
          </div>
          <h4 className="mt-2 line-clamp-2 text-sm font-bold leading-snug text-slate-900 sm:text-base">
            <a href={detailHref} target="_blank" rel="noopener noreferrer" className="hover:text-blue-700 hover:underline">{product.name}</a>
          </h4>
          <p className="mt-1 flex items-center gap-1 text-xs text-slate-500"><MapPin className="h-3 w-3 shrink-0" />{product.destination}</p>
          <p className="mt-2 text-xs font-bold text-indigo-700 sm:text-sm">
            {formatMoney(product.unitPrice, product.currency)}
            {suffix && <span className="ml-1 font-medium text-slate-400">{suffix}</span>}
          </p>
          {note && <p className="mt-2 text-xs leading-relaxed text-slate-500">{note}</p>}
          {product.priceAsOf && <p className="mt-1 text-[10px] text-slate-400">Giá ghi nhận {new Date(product.priceAsOf).toLocaleDateString('vi-VN')}</p>}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <a href={detailHref} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 px-2.5 text-[11px] font-bold text-slate-700 transition hover:border-blue-200 hover:bg-blue-50">
              <ExternalLink className="h-3.5 w-3.5" /> Xem chi tiết
            </a>
            {onAddToCart && isCartEligible(product) && (
              <button type="button" onClick={onAddToCart} className="inline-flex h-8 items-center gap-1 rounded-lg bg-blue-600 px-2.5 text-[11px] font-bold text-white transition hover:bg-blue-700">
                <ShoppingCart className="h-3.5 w-3.5" /> Thêm vào giỏ
              </button>
            )}
            {onReplace && (
              <button type="button" onClick={onReplace} disabled={replaceDisabled} className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-[11px] font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-40">
                <Repeat className="h-3.5 w-3.5" /> Đổi lựa chọn khác
              </button>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

function SearchResults({ results, onAddToCart }: { results: Record<string, Product[]>; onAddToCart?: (items: AssistantCartItem[]) => void }) {
  const groups = Object.entries(results).filter(([, products]) => products.length > 0);
  if (!groups.length) return <p className="mt-4 rounded-xl bg-white p-4 text-sm text-slate-500">Chưa có sản phẩm phù hợp.</p>;
  return <div className="mt-4 space-y-5">{groups.map(([taxonomy, products]) => (
    <section key={taxonomy} className="space-y-2.5">
      <h4 className="text-xs font-extrabold uppercase tracking-wider text-slate-500">{taxonomyLabel(taxonomy)} · {products.length}</h4>
      {products.map((product) => <ProductCard key={product.productId} product={product} onAddToCart={onAddToCart && (() => onAddToCart([{ product }]))} />)}
    </section>
  ))}</div>;
}

export function AssistantMapPanel() {
  return (
    <section aria-label="Bản đồ lịch trình" className="relative min-h-56 overflow-hidden rounded-2xl border border-slate-200 bg-[#f5f8fa] sm:min-h-72">
      <div aria-hidden="true" className="absolute inset-0 opacity-60" style={{ backgroundImage: 'linear-gradient(28deg, transparent 47%, #dce8eb 48%, #dce8eb 49%, transparent 50%), linear-gradient(118deg, transparent 44%, #dce8eb 45%, #dce8eb 46%, transparent 47%), linear-gradient(90deg, transparent 49%, #e8eff1 50%, transparent 51%)', backgroundSize: '130px 105px, 170px 135px, 100px 100px' }} />
      <div className="absolute left-[15%] top-[22%] h-20 w-32 rotate-12 rounded-[45%] bg-sky-100/80" />
      <div className="absolute bottom-[15%] right-[11%] h-24 w-36 -rotate-12 rounded-[48%] bg-emerald-100/70" />
      <div className="relative flex min-h-56 items-center justify-center p-5 sm:min-h-72">
        <div className="max-w-sm rounded-2xl border border-white/80 bg-white/90 p-5 text-center shadow-lg backdrop-blur-sm">
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600"><MapPin className="h-5 w-5" /></div>
          <h3 className="mt-3 text-sm font-extrabold text-slate-800">Bản đồ lịch trình</h3>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">Chưa có tọa độ cho các địa điểm trong lịch trình này nên chưa thể vẽ bản đồ.</p>
        </div>
      </div>
      <div className="absolute bottom-3 right-3 rounded-lg bg-white/90 px-2 py-1 text-[10px] font-medium text-slate-400 shadow-sm">Chưa có dữ liệu vị trí</div>
    </section>
  );
}

const BUDGET_BAR_COLOR: Record<components['schemas']['BudgetStatus'], string> = {
  WITHIN_BUDGET: 'bg-emerald-500',
  OVER_BUDGET: 'bg-rose-500',
  NO_BUDGET: 'bg-slate-400',
  UNKNOWN: 'bg-slate-400',
};

function BudgetBar({ total, budget, status, currency, onReduce }: {
  total: number;
  budget: number;
  status: components['schemas']['BudgetStatus'];
  currency: string;
  onReduce?: () => void;
}) {
  const ratio = budget > 0 ? total / budget : 0;
  return (
    <section aria-label="Ngân sách" className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs">
        <p className="font-extrabold text-slate-800">{BUDGET_STATUS_LABEL[status]}</p>
        <p className="text-slate-500">{formatMoney(total, currency)} / {formatMoney(budget, currency)} <span className="text-slate-400">· giá ước tính</span></p>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(Math.min(ratio, 1) * 100)}>
        <div className={`h-full rounded-full ${BUDGET_BAR_COLOR[status]}`} style={{ width: `${Math.min(ratio, 1) * 100}%` }} />
      </div>
      {status === 'OVER_BUDGET' && onReduce && (
        <button type="button" onClick={onReduce} className="mt-3 rounded-full border border-rose-200 bg-rose-50 px-3 py-1.5 text-[11px] font-bold text-rose-700 transition hover:bg-rose-100">Giảm chi phí cho vừa ngân sách</button>
      )}
    </section>
  );
}

const chipClass = 'inline-flex h-8 items-center gap-1 rounded-full border border-slate-200 bg-white px-3 text-[11px] font-bold text-slate-700 transition hover:border-indigo-200 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-40';

export function AssistantResultPanel({
  response,
  onIntentOverride,
  onSuggestion,
  onAddToCart,
  showMap = true,
  busy = false,
  readOnly = false,
}: {
  response: Response | null;
  onIntentOverride?: (intent: IntentPatch) => void;
  onSuggestion?: (suggestion: string) => void;
  /** Nhận một hoặc nhiều mục; nơi gọi tự xử lý đăng nhập và toast. */
  onAddToCart?: (items: AssistantCartItem[]) => void;
  showMap?: boolean;
  /** Agent đang chạy: khoá các nút chỉnh lịch trình. */
  busy?: boolean;
  /** Lịch trình đã lưu/chia sẻ: conversation có thể đã hết hạn nên ẩn các nút chỉnh. */
  readOnly?: boolean;
}) {
  if (!response) {
    return (
      <div className="flex min-h-[360px] flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-white/70 p-8 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-100 to-sky-100 text-indigo-600"><Sparkles className="h-7 w-7" /></span>
        <h2 className="mt-4 text-lg font-extrabold text-slate-800">Lịch trình của bạn sẽ xuất hiện tại đây</h2>
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-500">Hãy mô tả điểm đến và thời gian mong muốn. Trợ lý sẽ tìm sản phẩm thật và xếp lịch trình cho bạn.</p>
        <div className="mt-5 flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-[11px] font-medium text-slate-500"><CloudSun className="h-3.5 w-3.5" /> Dữ liệu được tải khi bạn gửi yêu cầu</div>
      </div>
    );
  }

  if (response.status === 'NEEDS_CLARIFICATION') {
    const missing = response.missingFields ?? [];
    const destinations = response.suggestedValues?.destination ?? [];
    const days = response.suggestedValues?.days ?? [];
    const { title, body } = splitBoldTitle(response.question);
    return (
      <section aria-label="Cần làm rõ yêu cầu" className="rounded-3xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white p-5 shadow-sm sm:p-7">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-100 text-amber-700"><AlertCircle className="h-5 w-5" /></div>
        <p className="mt-4 text-xs font-extrabold uppercase tracking-[0.16em] text-amber-700">Cần thêm thông tin</p>
        <h2 className="mt-2 text-xl font-extrabold leading-snug text-slate-900">{title ?? response.question}</h2>
        {title && body && <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">{body}</p>}
        {missing.includes('destination') && destinations.length > 0 && <div className="mt-5"><p className="mb-2 text-xs font-semibold text-slate-500">Điểm đến gợi ý</p><div className="flex flex-wrap gap-2">{destinations.map((destination) => <button key={destination} onClick={() => onIntentOverride?.({ destination })} className="rounded-full border border-amber-200 bg-white px-3.5 py-2 text-xs font-bold text-amber-900 transition hover:border-amber-400 hover:bg-amber-100">{destination}</button>)}</div></div>}
        {missing.includes('days') && days.length > 0 && <div className="mt-5"><p className="mb-2 text-xs font-semibold text-slate-500">Số ngày gợi ý</p><div className="flex flex-wrap gap-2">{days.map((value) => <button key={value} onClick={() => onIntentOverride?.({ days: value })} className="rounded-full border border-amber-200 bg-white px-3.5 py-2 text-xs font-bold text-amber-900 transition hover:border-amber-400 hover:bg-amber-100">{value} ngày</button>)}</div></div>}
        {missing.length === 0 && <p className="mt-4 text-sm text-slate-500">Bạn có thể bổ sung thông tin trực tiếp trong khung trò chuyện.</p>}
      </section>
    );
  }

  if (response.status === 'NO_RESULTS') {
    const { title, body } = splitBoldTitle(response.message);
    return (
      <section aria-label="Không tìm thấy kết quả" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-slate-600"><PackageOpen className="h-5 w-5" /></div>
        <p className="mt-4 text-xs font-extrabold uppercase tracking-[0.16em] text-slate-500">Chưa có kết quả</p>
        <h2 className="mt-2 text-xl font-extrabold leading-snug text-slate-900">{title ?? response.message}</h2>
        {title && body && <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">{body}</p>}
        {response.suggestions?.length ? <div className="mt-5 space-y-2">{response.suggestions.map((suggestion) => <button key={suggestion} onClick={() => onSuggestion?.(suggestion)} className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm font-semibold text-indigo-700 transition hover:border-indigo-200 hover:bg-indigo-50">{suggestion}<span aria-hidden="true">→</span></button>)}</div> : <p className="mt-3 text-sm text-slate-500">Bạn có thể thử điều chỉnh điểm đến hoặc thời gian chuyến đi.</p>}
      </section>
    );
  }

  if (response.status === 'FALLBACK') {
    const { title, body } = splitBoldTitle(response.message);
    return (
      <section aria-label="Kết quả tìm kiếm gần nhất" className="rounded-3xl border border-indigo-200 bg-gradient-to-br from-indigo-50/70 to-white p-5 shadow-sm sm:p-7">
        <div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-700"><Compass className="h-5 w-5" /></span><div><p className="text-xs font-extrabold uppercase tracking-[0.16em] text-indigo-700">Lựa chọn gần nhất</p><h2 className="mt-1 text-lg font-extrabold text-slate-900">{title ?? response.message}</h2></div></div>
        {title && body && <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">{body}</p>}
        <SearchResults results={response.searchResults} onAddToCart={onAddToCart} />
      </section>
    );
  }

  const itinerary = response.itinerary;
  const intent = response.intent;
  const products = [itinerary.stay?.product, ...itinerary.days.flatMap((day) => day.slots.map((slot) => slot.product))].filter((value): value is Product => Boolean(value));
  const distinctProducts = new Map(products.map((product) => [product.productId, product]));
  const cartItems = itineraryCartItems(itinerary);
  const canEdit = !readOnly && Boolean(onSuggestion);
  const currentDays = intent?.days ?? itinerary.days.length;
  const addOne = (item: AssistantCartItem) => onAddToCart && (() => onAddToCart([item]));
  const stayCheckIn = itinerary.days[0]?.date ?? undefined;

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-3xl border border-indigo-100 bg-white shadow-sm">
        <div className="relative overflow-hidden bg-gradient-to-br from-indigo-700 via-blue-700 to-sky-600 px-5 py-6 text-white sm:px-7 sm:py-8">
          <div aria-hidden="true" className="absolute -right-8 -top-12 h-48 w-48 rounded-full border-[24px] border-white/10" />
          <div className="relative flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-xl">
              <div className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.16em]"><Sparkles className="h-3 w-3" /> Itinerary Agent</div>
              <h2 className="mt-3 text-2xl font-extrabold leading-tight sm:text-3xl">{itinerary.title || `Khám phá ${intent?.destination ?? 'điểm đến của bạn'}`}</h2>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs font-medium text-blue-50 sm:text-sm">
                {intent?.destination && <span className="inline-flex items-center gap-1.5"><MapPin className="h-3.5 w-3.5" />{intent.destination}</span>}
                {intent?.days && <span className="inline-flex items-center gap-1.5"><CalendarDays className="h-3.5 w-3.5" />{intent.days} ngày</span>}
                {intent?.party?.type && <span className="inline-flex items-center gap-1.5"><Users className="h-3.5 w-3.5" />{PARTY_TYPE_LABEL[intent.party.type]} · {intent.party.adults + intent.party.children} khách</span>}
              </div>
            </div>
            <div className="min-w-40 rounded-2xl border border-white/20 bg-white/10 p-3.5 backdrop-blur-sm">
              <p className="text-[10px] font-bold uppercase tracking-wider text-blue-100">Tổng dự kiến</p>
              <p className="mt-1 text-base font-extrabold">{formatMoney(itinerary.estimatedTotal, itinerary.currency)}</p>
              <p className="mt-1 text-[10px] text-blue-100">{itinerary.bookableCount ?? 0} mục · {BUDGET_STATUS_LABEL[itinerary.budgetStatus]}</p>
              {onAddToCart && cartItems.length > 0 && (
                <button type="button" onClick={() => onAddToCart(cartItems)} className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-white px-3 py-2 text-xs font-extrabold text-indigo-700 shadow-sm transition hover:bg-indigo-50">
                  <ShoppingCart className="h-3.5 w-3.5" /> Thêm cả lịch trình vào giỏ ({cartItems.length})
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-px bg-slate-100 sm:grid-cols-4">
          <div className="bg-white px-4 py-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Ngày</p><p className="mt-1 text-sm font-extrabold text-slate-800">{itinerary.days.length}</p></div>
          <div className="bg-white px-4 py-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Sản phẩm</p><p className="mt-1 text-sm font-extrabold text-slate-800">{distinctProducts.size}</p></div>
          <div className="bg-white px-4 py-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Có thể đặt</p><p className="mt-1 text-sm font-extrabold text-slate-800">{itinerary.bookableCount ?? 0}</p></div>
          <div className="bg-white px-4 py-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Giá ghi nhận</p><p className="mt-1 text-xs font-bold text-slate-700">{itinerary.priceAsOf ? new Date(itinerary.priceAsOf).toLocaleDateString('vi-VN') : 'Chưa xác định'}</p></div>
        </div>
        {canEdit && (
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 px-4 py-3">
            <span className="text-[11px] font-semibold text-slate-500">Chỉnh nhanh:</span>
            {onIntentOverride && <button type="button" className={chipClass} disabled={busy || currentDays <= MIN_TRIP_DAYS} onClick={() => onIntentOverride({ days: currentDays - 1 })}>Bớt 1 ngày</button>}
            {onIntentOverride && <button type="button" className={chipClass} disabled={busy || currentDays >= MAX_TRIP_DAYS} onClick={() => onIntentOverride({ days: currentDays + 1 })}>Thêm 1 ngày</button>}
            {itinerary.stay && <button type="button" className={chipClass} disabled={busy} onClick={() => onSuggestion?.('Đổi sang khách sạn khác')}>Đổi khách sạn</button>}
          </div>
        )}
      </section>

      {intent?.budget != null && itinerary.estimatedTotal != null && (
        <BudgetBar
          total={itinerary.estimatedTotal}
          budget={intent.budget}
          status={itinerary.budgetStatus}
          currency={itinerary.currency}
          onReduce={canEdit && !busy ? () => onSuggestion?.('Giảm chi phí để vừa ngân sách') : undefined}
        />
      )}

      {itinerary.stay && <section className="space-y-2.5"><div className="flex items-center justify-between"><h3 className="text-sm font-extrabold text-slate-800">Nơi lưu trú</h3><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-bold text-indigo-700">{itinerary.stay.nights} đêm</span></div><ProductCard product={itinerary.stay.product} note={itinerary.stay.note} onAddToCart={addOne({ product: itinerary.stay.product, usingDate: stayCheckIn, checkOutDate: stayCheckIn ? addDays(stayCheckIn, itinerary.stay.nights) : undefined })} /></section>}

      <section className="space-y-3">
        <div className="flex items-center justify-between"><h3 className="text-sm font-extrabold text-slate-800">Lịch trình từng ngày</h3><span className="text-xs text-slate-400">{itinerary.days.length} ngày</span></div>
        {itinerary.days.map((day) => (
          <article key={day.day} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <header className="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/80 px-4 py-3">
              <div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-xs font-extrabold text-white">{String(day.day).padStart(2, '0')}</span><div><h4 className="text-sm font-extrabold text-slate-800">Ngày {day.day}{day.title ? ` · ${day.title}` : ''}</h4>{day.date && <p className="mt-0.5 text-[11px] text-slate-500">{new Date(`${day.date}T00:00:00`).toLocaleDateString('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' })}</p>}</div></div>
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold text-slate-500">{day.slots.length} hoạt động</span>
            </header>
            <div className="space-y-0 px-4 py-1">
              {day.slots.length === 0 && <p className="py-4 text-xs text-slate-500">Ngày này chưa có hoạt động nào.</p>}
              {day.slots.map((slot, index) => {
                const timeLabel = SLOT_TIME_LABEL[slot.time] ?? slot.time;
                const product = slot.product;
                return (
                  <div key={slot.slotId ?? `${day.day}-${index}`} className="relative grid grid-cols-[70px_minmax(0,1fr)] gap-3 py-3.5">
                    <div className="relative flex flex-col items-center"><span className="z-10 rounded-full bg-indigo-50 px-2 py-1 text-[10px] font-extrabold text-indigo-700">{timeLabel}</span>{index < day.slots.length - 1 && <span aria-hidden="true" className="absolute bottom-[-14px] top-8 w-px bg-slate-200" />}</div>
                    <div className="min-w-0 space-y-2">
                      {(slot.startTime || slot.endTime) && <p className="text-xs font-semibold text-slate-600">{slot.startTime ?? ''}{slot.endTime ? ` – ${slot.endTime}` : ''}</p>}
                      {product
                        ? <ProductCard
                            product={product}
                            note={slot.note}
                            onAddToCart={addOne({ product, usingDate: day.date ?? undefined })}
                            onReplace={canEdit ? () => onSuggestion?.(`Đổi ${product.name} (ngày ${day.day}, buổi ${timeLabel.toLowerCase()}) sang lựa chọn khác`) : undefined}
                            replaceDisabled={busy}
                          />
                        : <div className="rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">{slot.activityType && <span className="mr-1.5 font-bold text-slate-700">{ACTIVITY_TYPE_LABEL[slot.activityType]}{slot.note ? ' ·' : ''}</span>}{slot.note || (slot.activityType ? '' : 'Hoạt động tự do')}</div>}
                    </div>
                  </div>
                );
              })}
            </div>
          </article>
        ))}
      </section>

      {response.warnings.length > 0 && <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4"><h3 className="text-xs font-extrabold text-amber-900">Lưu ý</h3><ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-amber-800">{response.warnings.map((warning, index) => <li key={`${warning.code}-${index}`}>• {warning.message}</li>)}</ul></section>}
      {showMap && <AssistantMapPanel />}
      {response.searchResults && <section><h3 className="text-sm font-extrabold text-slate-800">Kết quả tìm kiếm liên quan</h3><SearchResults results={response.searchResults} onAddToCart={onAddToCart} /></section>}
    </div>
  );
}
