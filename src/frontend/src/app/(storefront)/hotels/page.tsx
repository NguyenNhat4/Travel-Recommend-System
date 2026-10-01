import type { Metadata } from 'next';
import { VerticalLanding } from '../../../features/catalog/landing/VerticalLanding';
import { pickParam } from '../../../features/catalog/landing/searchHref';

export const metadata: Metadata = {
  title: 'Khách sạn & resort | V-OTA',
  description: 'Duyệt và tìm khách sạn, resort theo điểm đến, ngày và số khách trên V-OTA.',
};

// Đọc query ở server để hero có sẵn trong HTML (dùng useSearchParams sẽ đẩy cả trang sang render phía client).
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  return <VerticalLanding vertical="hotels" destination={pickParam(query.destination)} type={pickParam(query.type)} />;
}
