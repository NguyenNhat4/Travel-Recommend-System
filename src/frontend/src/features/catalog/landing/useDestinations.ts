'use client';

import { listDestinations, type DestinationOption } from '../../../services/destinations';
import { useLazySection } from '../../../hooks/useLazySection';

/**
 * Danh sách điểm đến dùng chung cho menu header, ô địa điểm và ô "Điểm đến phổ biến": một request, một khóa bộ đệm.
 * Chỉ gọi khi `enabled` (menu được mở, khối vào vùng nhìn, ô địa điểm được focus).
 */
export function useDestinations(enabled: boolean) {
  return useLazySection<DestinationOption[]>('destinations', (signal) => listDestinations(signal), {
    enabled,
    ttlMs: 5 * 60_000,
  });
}

/** Nhiều sản phẩm nhất trước; điểm đến chưa có sản phẩm nào bị bỏ. */
export function topDestinations(list: DestinationOption[] | null, limit: number): DestinationOption[] {
  if (!list) return [];
  return list
    .filter((d) => d.productCount > 0)
    .sort((a, b) => b.productCount - a.productCount || a.destination.localeCompare(b.destination, 'vi'))
    .slice(0, limit);
}
