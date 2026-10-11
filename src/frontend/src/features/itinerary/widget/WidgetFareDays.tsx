import React from 'react';
import Link from 'next/link';
import { FLIGHTS_ROUTE, flightProductHref } from '../../flights/results/flightHref';
import type { Product } from '../../../types/travel';
import { flightShortDay, flightTime } from './widgetFlight';

const vnd = new Intl.NumberFormat('vi-VN');
const CABINS: Record<string, string> = { PREMIUM_ECONOMY: 'Phổ thông đặc biệt', BUSINESS: 'Thương gia', FIRST: 'Hạng nhất' };

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/** Chuyến bay cụ thể (có giờ cất cánh), khác tuyến bay cấp cha: chỉ chuyến mới có ngày để đặt vào ô ngày–giá. */
export function isFareFlight(product: Pick<Product, 'taxonomy' | 'attributes'>): boolean {
  return product.taxonomy === 'flight' && text(product.attributes?.departureAt) !== null;
}

function FareTile({ product, answer, showRoute, onNavigate }: {
  product: Product;
  answer: boolean;
  /** Các ô thuộc nhiều tuyến ("đi đâu cũng được"): ghi nơi đến trên ô, không thì ô nào cũng giống một ngày của cùng tuyến. */
  showRoute: boolean;
  onNavigate?: () => void;
}) {
  const attributes = product.attributes ?? {};
  const departureAt = text(attributes.departureAt);
  const day = flightShortDay(departureAt);
  const time = flightTime(departureAt) ?? text(attributes.departureTimeLocal);
  const carrier = [text(attributes.airline), text(attributes.flightNumber)].filter(Boolean).join(' ');
  // Hạng ghế khác Phổ thông và giá minh hoạ của catalog phải hiện trên thẻ: vé Thương gia mô phỏng đắt gấp mấy lần
  // (chat thử 11/10, "tại sao đắt").
  const cabin = CABINS[text(attributes.cabinClass) ?? ''] ?? null;
  const note = [cabin, attributes.simulated === true ? 'giá minh hoạ' : null].filter(Boolean).join(' · ');
  const price = product.unitPrice != null ? `${vnd.format(product.unitPrice)} ₫` : null;
  const destination = text(attributes.destinationCity) ?? text(product.destination);
  const label = `Xem chuyến bay ${showRoute && destination ? `đi ${destination} ` : ''}${day ? `ngày ${day.date}` : product.name}${price ? `, từ ${price}` : ''}`;
  return (
    <li className="min-w-0">
      <Link href={flightProductHref(product) ?? FLIGHTS_ROUTE} aria-label={label} onNavigate={onNavigate}
        data-product-id={product.id}
        className={`flex min-h-11 h-full flex-col gap-1 rounded-xl border px-3 py-2.5 transition-colors
          focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${answer
          ? 'border-blue-300 bg-sky-50 shadow-xs hover:border-blue-400'
          : 'border-slate-200 bg-white hover:border-blue-300 hover:bg-sky-50/60'}`}>
        {showRoute && destination && (
          <span className="line-clamp-1 text-xs font-semibold text-blue-700">Đi {destination}</span>
        )}
        <span className="text-base font-semibold leading-tight text-slate-900">
          {day ? <>{day.weekday}, {day.date}</> : <span className="line-clamp-2 text-sm">{product.name}</span>}
        </span>
        <span className="tabular-nums leading-tight">
          {price
            ? <><span className="text-lg font-bold text-blue-700">{price}</span><span className="text-xs text-slate-500">/khách</span></>
            : <span className="text-sm text-slate-500">Chưa có giá</span>}
        </span>
        {note && <span className="text-xs font-semibold text-amber-700">{note}</span>}
        {(time || carrier) && (
          <span className="line-clamp-2 text-xs leading-snug text-slate-600">{[time, carrier].filter(Boolean).join(' · ')}</span>
        )}
      </Link>
    </li>
  );
}

/**
 * Hàng ô ngày–giá của lượt hỏi giá vé (contract 1.25.0, FR-AGT-07): các chuyến một chiều của tuyến được hỏi, mỗi chuyến
 * một ngày bay. Lời trả lời chỉ nêu chuyến đầu nên các ngày khác chỉ hiện ở đây; ô đầu (chuyến câu trả lời nêu) nổi nhẹ.
 * Vé không có trang chi tiết riêng nên mỗi ô mở trang vé máy bay của đúng tuyến và ngày bay đó.
 */
export function WidgetFareDays({ products, onNavigate }: {
  /** Đã xếp: chuyến lời trả lời nêu đầu tiên đứng đầu. */
  products: Product[];
  /** Chuyển trang trong tab này qua một ô (không tính Ctrl/Cmd + bấm mở tab mới): widget phủ màn hình nên phải đóng. */
  onNavigate?: () => void;
}) {
  if (!products.length) return null;
  const destinations = new Set(products.map((product) => text(product.attributes?.destinationCity) ?? product.destination));
  return (
    <section aria-label="Giá vé theo ngày bay" className="@container my-4 whitespace-normal">
      <ul className={`grid grid-cols-2 gap-2 ${products.length >= 4 ? '@lg:grid-cols-4' : products.length === 3 ? '@lg:grid-cols-3' : ''}`}>
        {products.map((product, index) => (
          <FareTile key={product.id} product={product} answer={index === 0} showRoute={destinations.size > 1}
            onNavigate={onNavigate} />
        ))}
      </ul>
      <p className="mt-2 text-xs text-slate-500">Bấm vào một ngày để xem các chuyến trên trang vé máy bay.</p>
    </section>
  );
}
