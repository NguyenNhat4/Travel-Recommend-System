import type { Metadata } from 'next';
import { VerticalLanding } from '../../../features/catalog/landing/VerticalLanding';
import { pickParam } from '../../../features/catalog/landing/searchHref';
import { parseTripContext } from '../../../features/search/tripContext';

export const metadata: Metadata = {
  title: 'Combo du lịch | V-OTA',
  description: 'Gói kết hợp lưu trú, vé và vui chơi trên V-OTA.',
};

// Đọc query ở server để hero có sẵn trong HTML (dùng useSearchParams sẽ đẩy cả trang sang render phía client).
// Có `?q=` thì là đang tìm: kết quả hiện ngay dưới tấm tìm kiếm (VerticalLanding).
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  const param = (name: string) => pickParam(query[name]) ?? null;
  return (
    <VerticalLanding
      vertical="combos"
      destination={pickParam(query.destination)}
      type={pickParam(query.type)}
      query={pickParam(query.q)}
      trip={parseTripContext({ get: param })}
    />
  );
}
