import type { Metadata } from 'next';
import { DestinationTiles } from '../../../features/catalog/landing/DestinationTiles';
import { PromoBanner } from '../../../features/catalog/landing/PromoBanner';
import { pickParam } from '../../../features/catalog/landing/searchHref';
import { VERTICALS } from '../../../features/catalog/landing/verticals';
import { FlightsPage } from '../../../features/flights/FlightsPage';
import { buildFlightResultsHref, parseFlightSearch } from '../../../features/flights/results/flightHref';

export const metadata: Metadata = {
  title: 'Vé máy bay | Sota',
  description: 'Tìm vé máy bay theo điểm đi, điểm đến và ngày bay, chọn chuyến ngay trên Sota.',
};

// Đọc query ở server để hero có sẵn trong HTML (dùng useSearchParams sẽ đẩy cả trang sang render phía client).
// Trang tìm ngay tại chỗ: có `origin` và `destination` trên URL thì chuyến bay hiện luôn dưới tấm tìm kiếm.
// Chưa tìm thì bên dưới là lời nhắc nhập, rồi điểm đến và banner trợ lý (không có khối "phổ biến" và "giá tốt"; đề xuất
// docs/prd/update-archive/2026-09-30-trang-ve-may-bay-tim-tai-cho-bo-khoi-pho-bien-va-gia-tot.md).
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  const search = parseFlightSearch({ get: (name) => pickParam(query[name]) ?? null });
  const destination = pickParam(query.destination);
  return (
    // `key` theo URL: điều hướng thật tới một URL khác (menu, ô điểm đến) thì trang dựng lại; tìm tại chỗ không đổi key.
    <FlightsPage key={search ? buildFlightResultsHref(search) : `landing|${destination ?? ''}`} initial={search} destination={destination}>
      <DestinationTiles route={VERTICALS.flights.route} />
      <PromoBanner promo={VERTICALS.flights.promo} destination={destination} />
    </FlightsPage>
  );
}
