import type { Metadata } from 'next';
import { VerticalLanding } from '../../../features/catalog/landing/VerticalLanding';
import { pickParam } from '../../../features/catalog/landing/searchHref';

export const metadata: Metadata = {
  title: 'Vé máy bay | V-OTA',
  description: 'Duyệt chặng bay và tìm vé máy bay theo điểm đi, điểm đến và ngày bay trên V-OTA.',
};

// Đọc query ở server để hero có sẵn trong HTML (dùng useSearchParams sẽ đẩy cả trang sang render phía client).
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  return <VerticalLanding vertical="flights" destination={pickParam(query.destination)} type={pickParam(query.type)} />;
}
