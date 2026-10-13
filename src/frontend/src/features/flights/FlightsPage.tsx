'use client';

import React, { useState } from 'react';
import { PlaneTakeoff } from 'lucide-react';
import { resolveActiveGroup } from '../../components/layout/nav/navConfig';
import { LandingHero } from '../catalog/landing/LandingHero';
import { VERTICALS, resolveTab } from '../catalog/landing/verticals';
import { FlightResultsView } from './results/FlightResultsView';
import { buildFlightResultsHref, type FlightSearch, type FlightSearchInput } from './results/flightHref';

/**
 * Câu nói còn thiếu gì; null khi đủ sân bay đi và sân bay đến. Ô chỉ có sân bay thật khi đã khớp danh sách của catalog
 * (spec ui-dia-diem-san-bay-va-khach-san-noi-tieng §4.4); chữ chưa khớp được báo đúng tên ô.
 */
export function missingFlightInput(input: FlightSearchInput): string | null {
  if (input.airportsReady === false) return 'Chưa tải được danh sách sân bay. Thử lại sau giây lát.';
  const originText = input.originText?.trim() ?? '';
  const destinationText = input.location.trim();
  if (!input.origin && !input.destination && !originText && !destinationText) {
    return 'Chọn sân bay đi và sân bay đến để xem chuyến bay.';
  }
  if (!input.origin) {
    return originText
      ? `Chưa nhận ra sân bay đi “${originText}”. Chọn một sân bay trong danh sách gợi ý.`
      : 'Bạn chưa chọn sân bay đi.';
  }
  if (!input.destination) {
    return destinationText
      ? `Chưa nhận ra sân bay đến “${destinationText}”. Chọn một sân bay trong danh sách gợi ý.`
      : 'Bạn chưa chọn sân bay đến.';
  }
  return null;
}

/** Chỗ của kết quả khi chưa tìm, hoặc khi lần bấm Tìm vừa rồi còn thiếu thông tin. */
export const FlightSearchPrompt: React.FC<{ notice: string | null }> = ({ notice }) => (
  <section aria-label="Kết quả vé máy bay" className="relative z-10 -mt-8 rounded-t-4xl bg-white px-4 pb-8 pt-8 sm:px-6 lg:px-8">
    <div className="mx-auto flex max-w-3xl flex-col items-center gap-3 rounded-[20px] border border-slate-200 bg-slate-50 px-6 py-10 text-center">
      <span className="grid h-12 w-12 place-items-center rounded-full bg-brand-100 text-brand-700"><PlaneTakeoff className="h-6 w-6" aria-hidden="true" /></span>
      <h2 className="font-display text-xl text-slate-900">Nhập chuyến đi để xem chuyến bay</h2>
      <p className="max-w-lg text-sm text-slate-600">
        Chọn sân bay đi, sân bay đến và ngày bay ở ô tìm kiếm phía trên rồi bấm Tìm kiếm. Chuyến bay còn mở bán sẽ hiện ngay tại đây.
      </p>
      {notice && <p role="alert" className="rounded-xl bg-amber-50 px-4 py-2.5 text-sm font-medium text-amber-900">{notice}</p>}
    </div>
  </section>
);

interface FlightsPageProps {
  /** Lần tìm trong URL (`?origin&destination…`), hoặc null khi vào `/flights` trơn. */
  initial: FlightSearch | null;
  /** `?destination=` của URL khi chưa có lần tìm: điền sẵn ô điểm đến. */
  destination?: string;
  /** Các khối dưới lời nhắc (điểm đến, banner trợ lý); chỉ hiện khi chưa tìm. */
  children?: React.ReactNode;
}

/**
 * Trang `/flights`: hero và tấm tìm kiếm ở trên, bên dưới là chuyến bay của lần tìm. Tìm ở ngay tại đây, không chuyển trang:
 * kết quả thay chỗ lời nhắc, URL được cập nhật tại chỗ (`history.replaceState`) để chia sẻ được. Chưa nhập đủ điểm đi và
 * điểm đến thì phần dưới nói rõ còn thiếu gì.
 */
export const FlightsPage: React.FC<FlightsPageProps> = ({ initial, destination, children }) => {
  const config = VERTICALS.flights;
  const [search, setSearch] = useState<FlightSearch | null>(initial);
  const [notice, setNotice] = useState<string | null>(null);

  const run = (input: FlightSearchInput) => {
    const missing = missingFlightInput(input);
    if (missing) {
      setNotice(missing);
      return;
    }
    const next: FlightSearch = { origin: input.origin.trim(), destination: input.destination as string, trip: input.trip };
    setNotice(null);
    setSearch(next);
    window.history.replaceState(null, '', buildFlightResultsHref(next));
  };

  return (
    <div className="flex flex-col bg-white">
      <LandingHero
        config={config}
        tab={resolveTab(config, undefined)}
        activeGroup={resolveActiveGroup(config.route)}
        destination={initial?.destination ?? destination}
        search={initial ? { origin: initial.origin, trip: initial.trip } : undefined}
        compact={search !== null}
        onFlightSearch={run}
      />
      {search ? (
        // `key`: lần tìm khác thì kết quả dựng lại từ đầu (chuyến đã chọn, ngày, bộ lọc của lần trước không được giữ).
        <FlightResultsView key={buildFlightResultsHref(search)} search={search} notice={notice} />
      ) : (
        <>
          <FlightSearchPrompt notice={notice} />
          {children}
        </>
      )}
    </div>
  );
};
