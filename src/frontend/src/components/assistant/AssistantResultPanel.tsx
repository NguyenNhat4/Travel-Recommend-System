'use client';

import React from 'react';
import { AlertCircle, CalendarDays, Check, CloudSun, Compass, MapPin, PackageOpen, Sparkles, Users } from 'lucide-react';
import type { components } from '../../types/api.gen';

type Response = components['schemas']['ItineraryResponse'];
type Product = components['schemas']['ProductSummary'];
type IntentPatch = components['schemas']['TripIntentPatch'];

function formatMoney(amount: number | null | undefined, currency: string) {
  if (amount == null) return 'Chưa đủ dữ liệu để tính tổng';
  try {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency }).format(amount);
  } catch {
    return `${new Intl.NumberFormat('vi-VN').format(amount)} ${currency}`;
  }
}

function ProductCard({ product, note }: { product: Product; note?: string | null }) {
  return (
    <article className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:border-blue-200 hover:shadow-md">
      <div className="flex gap-3 p-3 sm:gap-4 sm:p-4">
        {product.imageUrl ? (
          <img src={product.imageUrl} alt={product.name} className="h-24 w-28 shrink-0 rounded-xl bg-slate-100 object-cover sm:h-28 sm:w-36" />
        ) : (
          <div aria-hidden="true" className="flex h-24 w-28 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-100 via-sky-50 to-white text-indigo-400 sm:h-28 sm:w-36">
            <Compass className="h-8 w-8" />
          </div>
        )}
        <div className="min-w-0 flex-1 py-0.5">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-blue-700">{product.taxonomy}</span>
            {product.available && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700"><Check className="h-3 w-3" /> Có trong dữ liệu nguồn</span>}
          </div>
          <h4 className="mt-2 line-clamp-2 text-sm font-bold leading-snug text-slate-900 sm:text-base">{product.name}</h4>
          <p className="mt-1 flex items-center gap-1 text-xs text-slate-500"><MapPin className="h-3 w-3 shrink-0" />{product.destination}</p>
          <p className="mt-2 text-xs font-bold text-indigo-700 sm:text-sm">
            {formatMoney(product.unitPrice, product.currency)}
            {product.priceUnit !== 'UNKNOWN' && product.unitPrice != null ? <span className="ml-1 font-medium text-slate-400">/ {product.priceUnit}</span> : null}
          </p>
          {note && <p className="mt-2 text-xs leading-relaxed text-slate-500">{note}</p>}
          {product.priceAsOf && <p className="mt-1 text-[10px] text-slate-400">Giá ghi nhận {new Date(product.priceAsOf).toLocaleDateString('vi-VN')}</p>}
        </div>
      </div>
    </article>
  );
}

function SearchResults({ results }: { results: Record<string, Product[]> }) {
  const groups = Object.entries(results).filter(([, products]) => products.length > 0);
  if (!groups.length) return <p className="mt-4 rounded-xl bg-white p-4 text-sm text-slate-500">Backend chưa trả sản phẩm phù hợp.</p>;
  return <div className="mt-4 space-y-5">{groups.map(([taxonomy, products]) => (
    <section key={taxonomy} className="space-y-2.5">
      <h4 className="text-xs font-extrabold uppercase tracking-wider text-slate-500">{taxonomy} · {products.length}</h4>
      {products.map((product) => <ProductCard key={product.productId} product={product} />)}
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
          <p className="mt-1 text-xs leading-relaxed text-slate-500">Response backend hiện chưa có tọa độ địa điểm. Bản đồ sẽ hiển thị khi contract cung cấp dữ liệu vị trí.</p>
        </div>
      </div>
      <div className="absolute bottom-3 right-3 rounded-lg bg-white/90 px-2 py-1 text-[10px] font-medium text-slate-400 shadow-sm">Chưa có dữ liệu vị trí</div>
    </section>
  );
}

export function AssistantResultPanel({
  response,
  onIntentOverride,
  onSuggestion,
  showMap = true,
}: {
  response: Response | null;
  onIntentOverride?: (intent: IntentPatch) => void;
  onSuggestion?: (suggestion: string) => void;
  showMap?: boolean;
}) {
  if (!response) {
    return (
      <div className="flex min-h-[360px] flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-white/70 p-8 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-100 to-sky-100 text-indigo-600"><Sparkles className="h-7 w-7" /></span>
        <h2 className="mt-4 text-lg font-extrabold text-slate-800">Lịch trình của bạn sẽ xuất hiện tại đây</h2>
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-500">Hãy mô tả điểm đến và thời gian mong muốn. Agent sẽ tìm kiếm và trả kết quả từ backend.</p>
        <div className="mt-5 flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-[11px] font-medium text-slate-500"><CloudSun className="h-3.5 w-3.5" /> Dữ liệu được tải khi bạn gửi yêu cầu</div>
      </div>
    );
  }

  if (response.status === 'NEEDS_CLARIFICATION') {
    const missing = response.missingFields ?? [];
    const destinations = response.suggestedValues?.destination ?? [];
    const days = response.suggestedValues?.days ?? [];
    return (
      <section aria-label="Cần làm rõ yêu cầu" className="rounded-3xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white p-5 shadow-sm sm:p-7">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-100 text-amber-700"><AlertCircle className="h-5 w-5" /></div>
        <p className="mt-4 text-xs font-extrabold uppercase tracking-[0.16em] text-amber-700">Cần thêm thông tin</p>
        <h2 className="mt-2 text-xl font-extrabold leading-snug text-slate-900">{response.question}</h2>
        {missing.includes('destination') && destinations.length > 0 && <div className="mt-5"><p className="mb-2 text-xs font-semibold text-slate-500">Điểm đến backend gợi ý</p><div className="flex flex-wrap gap-2">{destinations.map((destination) => <button key={destination} onClick={() => onIntentOverride?.({ destination })} className="rounded-full border border-amber-200 bg-white px-3.5 py-2 text-xs font-bold text-amber-900 transition hover:border-amber-400 hover:bg-amber-100">{destination}</button>)}</div></div>}
        {missing.includes('days') && days.length > 0 && <div className="mt-5"><p className="mb-2 text-xs font-semibold text-slate-500">Số ngày gợi ý</p><div className="flex flex-wrap gap-2">{days.map((value) => <button key={value} onClick={() => onIntentOverride?.({ days: value })} className="rounded-full border border-amber-200 bg-white px-3.5 py-2 text-xs font-bold text-amber-900 transition hover:border-amber-400 hover:bg-amber-100">{value} ngày</button>)}</div></div>}
        {missing.length === 0 && <p className="mt-4 text-sm text-slate-500">Bạn có thể bổ sung thông tin trực tiếp trong khung trò chuyện.</p>}
      </section>
    );
  }

  if (response.status === 'NO_RESULTS') {
    return (
      <section aria-label="Không tìm thấy kết quả" className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-slate-600"><PackageOpen className="h-5 w-5" /></div>
        <p className="mt-4 text-xs font-extrabold uppercase tracking-[0.16em] text-slate-500">Chưa có kết quả</p>
        <h2 className="mt-2 text-xl font-extrabold leading-snug text-slate-900">{response.message}</h2>
        {response.suggestions?.length ? <div className="mt-5 space-y-2">{response.suggestions.map((suggestion) => <button key={suggestion} onClick={() => onSuggestion?.(suggestion)} className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm font-semibold text-indigo-700 transition hover:border-indigo-200 hover:bg-indigo-50">{suggestion}<span aria-hidden="true">→</span></button>)}</div> : <p className="mt-3 text-sm text-slate-500">Bạn có thể thử điều chỉnh điểm đến hoặc thời gian chuyến đi.</p>}
      </section>
    );
  }

  if (response.status === 'FALLBACK') {
    return (
      <section aria-label="Kết quả tìm kiếm gần nhất" className="rounded-3xl border border-indigo-200 bg-gradient-to-br from-indigo-50/70 to-white p-5 shadow-sm sm:p-7">
        <div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-700"><Compass className="h-5 w-5" /></span><div><p className="text-xs font-extrabold uppercase tracking-[0.16em] text-indigo-700">Lựa chọn gần nhất</p><h2 className="mt-1 text-lg font-extrabold text-slate-900">{response.message}</h2></div></div>
        <SearchResults results={response.searchResults} />
      </section>
    );
  }

  const itinerary = response.itinerary;
  const intent = response.intent;
  const products = [itinerary.stay?.product, ...itinerary.days.flatMap((day) => day.slots.map((slot) => slot.product))].filter((value): value is Product => Boolean(value));
  const distinctProducts = new Map(products.map((product) => [product.productId, product]));

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
                {intent?.party?.type && <span className="inline-flex items-center gap-1.5"><Users className="h-3.5 w-3.5" />{intent.party.type.toLowerCase().replaceAll('_', ' ')} · {intent.party.adults + intent.party.children} khách</span>}
              </div>
            </div>
            <div className="min-w-40 rounded-2xl border border-white/20 bg-white/10 p-3.5 backdrop-blur-sm">
              <p className="text-[10px] font-bold uppercase tracking-wider text-blue-100">Tổng dự kiến</p>
              <p className="mt-1 text-base font-extrabold">{formatMoney(itinerary.estimatedTotal, itinerary.currency)}</p>
              <p className="mt-1 text-[10px] text-blue-100">{itinerary.bookableCount ?? 0} mục · Ngân sách {itinerary.budgetStatus}</p>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-px bg-slate-100 sm:grid-cols-4">
          <div className="bg-white px-4 py-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Ngày</p><p className="mt-1 text-sm font-extrabold text-slate-800">{itinerary.days.length}</p></div>
          <div className="bg-white px-4 py-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Sản phẩm</p><p className="mt-1 text-sm font-extrabold text-slate-800">{distinctProducts.size}</p></div>
          <div className="bg-white px-4 py-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Có thể đặt</p><p className="mt-1 text-sm font-extrabold text-slate-800">{itinerary.bookableCount ?? 0}</p></div>
          <div className="bg-white px-4 py-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Giá ghi nhận</p><p className="mt-1 text-xs font-bold text-slate-700">{itinerary.priceAsOf ? new Date(itinerary.priceAsOf).toLocaleDateString('vi-VN') : 'Chưa xác định'}</p></div>
        </div>
      </section>

      {itinerary.stay && <section className="space-y-2.5"><div className="flex items-center justify-between"><h3 className="text-sm font-extrabold text-slate-800">Nơi lưu trú</h3><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-bold text-indigo-700">{itinerary.stay.nights} đêm</span></div><ProductCard product={itinerary.stay.product} note={itinerary.stay.note} /></section>}

      <section className="space-y-3">
        <div className="flex items-center justify-between"><h3 className="text-sm font-extrabold text-slate-800">Lịch trình từng ngày</h3><span className="text-xs text-slate-400">{itinerary.days.length} ngày</span></div>
        {itinerary.days.map((day) => (
          <article key={day.day} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <header className="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/80 px-4 py-3">
              <div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-xs font-extrabold text-white">{String(day.day).padStart(2, '0')}</span><div><h4 className="text-sm font-extrabold text-slate-800">Ngày {day.day}{day.title ? ` · ${day.title}` : ''}</h4>{day.date && <p className="mt-0.5 text-[11px] text-slate-500">{day.date}</p>}</div></div>
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold text-slate-500">{day.slots.length} hoạt động</span>
            </header>
            <div className="space-y-0 px-4 py-1">
              {day.slots.length === 0 && <p className="py-4 text-xs text-slate-500">Backend chưa xếp hoạt động cho ngày này.</p>}
              {day.slots.map((slot, index) => (
                <div key={slot.slotId ?? `${day.day}-${index}`} className="relative grid grid-cols-[70px_minmax(0,1fr)] gap-3 py-3.5">
                  <div className="relative flex flex-col items-center"><span className="z-10 rounded-full bg-indigo-50 px-2 py-1 text-[10px] font-extrabold text-indigo-700">{slot.time}</span>{index < day.slots.length - 1 && <span aria-hidden="true" className="absolute bottom-[-14px] top-8 w-px bg-slate-200" />}</div>
                  <div className="min-w-0 space-y-2">
                    <p className="text-xs font-semibold text-slate-600">{slot.startTime ?? ''}{slot.endTime ? ` – ${slot.endTime}` : ''}</p>
                    {slot.product ? <ProductCard product={slot.product} note={slot.note} /> : <div className="rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">{slot.note || slot.activityType || 'Hoạt động do backend trả về'}</div>}
                  </div>
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>

      {response.warnings.length > 0 && <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4"><h3 className="text-xs font-extrabold text-amber-900">Lưu ý từ backend</h3><ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-amber-800">{response.warnings.map((warning, index) => <li key={`${warning.code}-${index}`}>• {warning.message}</li>)}</ul></section>}
      {showMap && <AssistantMapPanel />}
      {response.searchResults && <section><h3 className="text-sm font-extrabold text-slate-800">Kết quả tìm kiếm liên quan</h3><SearchResults results={response.searchResults} /></section>}
    </div>
  );
}
