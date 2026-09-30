import React from 'react';

type FlightProduct = { taxonomy: string; attributes?: Record<string, unknown> };
const cabins: Record<string, string> = {
  ECONOMY: 'Phổ thông', PREMIUM_ECONOMY: 'Phổ thông đặc biệt', BUSINESS: 'Thương gia', FIRST: 'Hạng nhất',
};
const text = (value: unknown): string => typeof value === 'string' ? value : '';

function legSummary(leg: Record<string, unknown>): string {
  const departure = text(leg.departureAt);
  const when = departure && !Number.isNaN(Date.parse(departure))
    ? new Intl.DateTimeFormat('vi-VN', {
      timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(departure)) : '';
  return [text(leg.flightNumber), [text(leg.originAirport), text(leg.destinationAirport)].filter(Boolean).join(' → '), when]
    .filter(Boolean).join(' · ');
}

/** Both legs and the cabin belong to the selected productId; no client-side price derivation. */
export function FlightSummary({ product }: { product: FlightProduct }) {
  const a = product.attributes ?? {};
  if (product.taxonomy !== 'flight' || a.level !== 'flight') return null;
  const roundTrip = a.tripType === 'roundTrip';
  const back = a.returnFlight && typeof a.returnFlight === 'object' && !Array.isArray(a.returnFlight)
    ? a.returnFlight as Record<string, unknown> : null;
  return (
    <div className="text-[11px] text-slate-600 space-y-0.5 mt-1">
      <p>{roundTrip ? 'Khứ hồi' : 'Một chiều'} · {cabins[text(a.cabinClass)] ?? 'Chưa rõ hạng vé'}</p>
      {legSummary(a) && <p>Đi: {legSummary(a)}</p>}
      {roundTrip && back && <p>Về: {legSummary(back)}</p>}
      {roundTrip && <p>Giá gồm hai chặng / khách</p>}
    </div>
  );
}
