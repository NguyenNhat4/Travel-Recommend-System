/**
 * Nguồn duy nhất cho điều hướng theo nhóm dịch vụ: header, menu "tất cả dịch vụ", chip mobile, ô lối vào ở Home,
 * chân trang và trạng thái "đang ở đâu" (docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md §1).
 * Không import React: chỉ dữ liệu và hàm thuần để test trong môi trường node.
 */
import type { Taxonomy } from '../../../types/travel';

export type NavIcon = 'plane' | 'hotel' | 'ticket' | 'flag' | 'package' | 'sparkles';
export type NavGroupId = 'travel' | 'stay' | 'experience' | 'more';

export interface NavItem {
  id: string;
  label: string;
  /** Một dòng mô tả tĩnh; không nêu số liệu (số sản phẩm, giá, khuyến mãi). */
  description: string;
  href: string;
  icon: NavIcon;
  /** Có ở mọi mục là danh mục dữ liệu; vắng ở mục không phải danh mục (trợ lý). */
  taxonomy?: Taxonomy;
}

export interface NavGroup {
  id: NavGroupId;
  label: string;
  summary: string;
  itemIds: string[];
  /** Route nhận `?destination=` cho chip "Điểm đến phổ biến" trong menu. */
  destinationRoute: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { id: 'flights', label: 'Vé máy bay', description: 'Vé một chiều và khứ hồi', href: '/flights', icon: 'plane', taxonomy: 'flight' },
  { id: 'hotels', label: 'Khách sạn & resort', description: 'Nơi lưu trú cho chuyến đi', href: '/hotels', icon: 'hotel', taxonomy: 'hotel' },
  { id: 'attractions', label: 'Vé tham quan & vui chơi', description: 'Khu vui chơi, điểm tham quan', href: '/experiences', icon: 'ticket', taxonomy: 'attraction' },
  { id: 'golf', label: 'Sân golf', description: 'Sân golf nghỉ dưỡng', href: '/experiences?type=golf', icon: 'flag', taxonomy: 'golf' },
  { id: 'combos', label: 'Combo du lịch', description: 'Gói kết hợp lưu trú, vé và vui chơi', href: '/combos', icon: 'package', taxonomy: 'combo' },
  { id: 'assistant', label: 'Trợ lý lịch trình AI', description: 'Lập lịch từng ngày bằng sản phẩm có thật', href: '/assistant', icon: 'sparkles' },
];

/** Thứ tự hiển thị trên header, theo mẫu. */
export const NAV_GROUPS: readonly NavGroup[] = [
  { id: 'travel', label: 'Di chuyển', summary: 'Vé máy bay', itemIds: ['flights'], destinationRoute: '/flights' },
  { id: 'stay', label: 'Lưu trú', summary: 'Khách sạn và resort', itemIds: ['hotels'], destinationRoute: '/hotels' },
  { id: 'experience', label: 'Tour và trải nghiệm', summary: 'Vé tham quan, vui chơi, sân golf', itemIds: ['attractions', 'golf'], destinationRoute: '/experiences' },
  { id: 'more', label: 'Tiện ích khác', summary: 'Combo du lịch và trợ lý AI', itemIds: ['combos', 'assistant'], destinationRoute: '/combos' },
];

/** Route có hero: header nổi trên ảnh nền rồi chuyển nền trắng khi cuộn (Header.tsx). */
export const OVERLAY_ROUTES: readonly string[] = ['/', '/hotels', '/flights', '/experiences', '/combos'];

export const TAXONOMIES: readonly Taxonomy[] = ['hotel', 'flight', 'attraction', 'combo', 'golf'];

const TAXONOMY_GROUP: Record<Taxonomy, NavGroupId> = {
  flight: 'travel',
  hotel: 'stay',
  attraction: 'experience',
  golf: 'experience',
  combo: 'more',
};

type ParamSource = { get(name: string): string | null };

export function itemsOf(group: NavGroup): NavItem[] {
  return group.itemIds
    .map((id) => NAV_ITEMS.find((item) => item.id === id))
    .filter((item): item is NavItem => Boolean(item));
}

export function isOverlayRoute(pathname: string): boolean {
  return OVERLAY_ROUTES.includes(pathname === '' ? '/' : pathname.replace(/\/+$/, '') || '/');
}

function isTaxonomy(value: string | null): value is Taxonomy {
  return value !== null && (TAXONOMIES as readonly string[]).includes(value);
}

function under(pathname: string, base: string): boolean {
  return pathname === base || pathname.startsWith(`${base}/`);
}

/**
 * Danh mục dữ liệu mà route hiện tại đang xem; null khi route không thuộc danh mục nào
 * (Home, giỏ, trang chi tiết, trợ lý...). `/search` theo tham số `type|taxonomy`.
 */
export function activeTaxonomy(pathname: string, params?: ParamSource): Taxonomy | null {
  const path = pathname.replace(/\/+$/, '') || '/';
  if (under(path, '/search')) {
    const raw = params?.get('type') ?? params?.get('taxonomy') ?? null;
    return isTaxonomy(raw) ? raw : null;
  }
  if (under(path, '/hotels')) return 'hotel';
  if (under(path, '/flights')) return 'flight';
  if (under(path, '/combos')) return 'combo';
  if (under(path, '/experiences')) return params?.get('type') === 'golf' ? 'golf' : 'attraction';
  return null;
}

export function resolveActiveGroup(pathname: string, params?: ParamSource): NavGroupId | null {
  const taxonomy = activeTaxonomy(pathname, params);
  return taxonomy ? TAXONOMY_GROUP[taxonomy] : null;
}

export function isItemActive(item: NavItem, pathname: string, params?: ParamSource): boolean {
  if (!item.taxonomy) return under(pathname.replace(/\/+$/, '') || '/', item.href);
  return activeTaxonomy(pathname, params) === item.taxonomy;
}

/** Ô lối vào danh mục ở Home, chip mobile và chân trang: mỗi nhóm một ô, dẫn tới mục đầu tiên. */
export interface CategoryShortcut {
  id: NavGroupId;
  label: string;
  summary: string;
  href: string;
  icon: NavIcon;
}

export function categoryShortcuts(): CategoryShortcut[] {
  return NAV_GROUPS.map((group) => {
    const first = itemsOf(group)[0];
    return { id: group.id, label: group.label, summary: group.summary, href: first.href, icon: first.icon };
  });
}
