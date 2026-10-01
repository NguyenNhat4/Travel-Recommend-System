import type { Metadata } from 'next';
import { VerticalLanding } from '../../../features/catalog/landing/VerticalLanding';
import { pickParam } from '../../../features/catalog/landing/searchHref';

export const metadata: Metadata = {
  title: 'Tour và trải nghiệm | V-OTA',
  description: 'Vé tham quan, khu vui chơi và sân golf tại điểm đến của bạn trên V-OTA.',
};

// Đọc query ở server để hero có sẵn trong HTML (dùng useSearchParams sẽ đẩy cả trang sang render phía client).
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  return <VerticalLanding vertical="experiences" destination={pickParam(query.destination)} type={pickParam(query.type)} />;
}
