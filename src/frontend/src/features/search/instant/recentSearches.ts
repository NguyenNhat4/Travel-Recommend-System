'use client';

import { useRecentPlaces, type RecentPlaces } from '../../catalog/landing/recentPlaces';

/** Lịch sử tìm kiếm của ô tìm kiếm chung (docs/spec/product.md §4.2.1): chỉ lưu ở trình duyệt, tối đa 5, có nút xóa. */
export const RECENT_SEARCHES_KEY = 'vota_recent_searches';

/** "Từ khoá phổ biến" khi ô còn trống: danh sách cố định, cùng nguồn với các chip gợi ý ở Home và `/search`. */
export const POPULAR_KEYWORDS: readonly string[] = [
  'Resort V-OTA Nha Trang cho gia đình',
  'Combo Phú Quốc 3N2Đ giá tốt',
  'Villa ven biển view hoàng hôn',
  'VinWonders Phú Quốc',
  'Sân golf nghỉ dưỡng',
];

export function useRecentSearches(): RecentPlaces {
  return useRecentPlaces(RECENT_SEARCHES_KEY, true);
}
