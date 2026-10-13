'use client';

import { listProducts, productFromApi } from '../../../services/catalog';
import { useLazySection } from '../../../hooks/useLazySection';
import type { FamousHotel } from './FamousHotelsPanel';

/** Số khách sạn lấy về; dropdown chỉ hiện vài dòng, phần còn lại dùng để lọc khi đang gõ. `limit` tối đa của contract là 20. */
export const FAMOUS_HOTEL_FETCH = 20;

/**
 * Khách sạn nổi tiếng: `GET /products` của catalog, `sort=popular` (cùng thứ tự với kệ "Khách sạn và resort phổ biến"),
 * chỉ khách sạn còn bán. Tải khi ô được bấm; dùng chung một khoá bộ đệm cho `/hotels` và `/combos`.
 */
export function useFamousHotels(enabled: boolean) {
  return useLazySection<FamousHotel[]>('famous-hotels', async (signal) => {
    const response = await listProducts({ taxonomy: 'hotel', sort: 'popular', availableOnly: true, limit: FAMOUS_HOTEL_FETCH }, signal);
    return response.results.map(productFromApi).map((product) => ({
      id: product.id,
      name: product.name,
      destination: product.destination,
      imageUrl: product.imageUrl,
    }));
  }, { enabled, ttlMs: 5 * 60_000 });
}
