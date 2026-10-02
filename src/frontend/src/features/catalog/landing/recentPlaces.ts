/**
 * Lịch sử địa điểm ở tấm tìm kiếm (hiện cho vé máy bay: ô Điểm đi và Điểm đến), lưu ở trình duyệt của người dùng.
 * Cùng kiểu "Tìm kiếm gần đây" của docs/spec/product.md §4.2.1: tối đa 5, mới nhất trước, có nút xóa.
 * Không có tài khoản hay dữ liệu cá nhân nào đi lên Backend; đọc ghi lỗi (chế độ riêng tư, bị chặn) thì coi như chưa có lịch sử.
 */
import { useCallback, useState } from 'react';
import { filterDestinations, fold, matchDestination } from './searchHref';
import { topDestinations } from './useDestinations';
import type { DestinationOption } from '../../../services/destinations';

export const RECENT_LIMIT = 5;
export const RECENT_ORIGINS_KEY = 'vota_flight_recent_origins';
export const RECENT_DESTINATIONS_KEY = 'vota_flight_recent_destinations';

function read(key: string): string[] {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(key) ?? '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === 'string' && item.trim().length > 0).slice(0, RECENT_LIMIT);
  } catch {
    return [];
  }
}

function write(key: string, items: string[]): void {
  try {
    if (items.length === 0) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, JSON.stringify(items));
  } catch {
    // Không lưu được thì lịch sử chỉ sống trong phiên này.
  }
}

/** Đưa `name` lên đầu danh sách, bỏ bản trùng (không phân biệt dấu, hoa thường), giữ tối đa `RECENT_LIMIT`. */
export function addRecent(items: readonly string[], name: string): string[] {
  const label = name.trim();
  if (!label) return [...items];
  const wanted = fold(label);
  return [label, ...items.filter((item) => fold(item) !== wanted)].slice(0, RECENT_LIMIT);
}

export interface RecentPlaces {
  items: string[];
  remember: (name: string) => void;
  clear: () => void;
}

/** Lịch sử một ô. `enabled` false thì không đọc và không ghi gì (các danh mục chưa có lịch sử). */
export function useRecentPlaces(key: string, enabled: boolean): RecentPlaces {
  const [items, setItems] = useState<string[]>(() => (enabled && typeof window !== 'undefined' ? read(key) : []));

  const remember = useCallback(
    (name: string) => {
      if (!enabled) return;
      const next = addRecent(read(key), name);
      write(key, next);
      setItems(next);
    },
    [enabled, key],
  );
  const clear = useCallback(() => {
    write(key, []);
    setItems([]);
  }, [key]);

  return { items: enabled ? items : [], remember, clear };
}

export interface PlaceOptions {
  /** Địa điểm đã tìm gần đây; chỉ hiện khi ô còn trống. */
  recent: string[];
  /** Gợi ý theo chữ đã gõ, không lặp với `recent`. */
  popular: string[];
}

interface PlaceOptionsInput {
  text: string;
  recent: readonly string[];
  /** Điểm đến của `/destinations`; null khi chưa tải. */
  destinations: DestinationOption[] | null;
  /** Nhãn không được gợi ý (điểm đi đã chọn ở ô điểm đến, và ngược lại). */
  exclude?: string;
}

/**
 * Hai nhóm gợi ý của một ô địa điểm. Lịch sử chỉ gồm nhãn còn có trong `/destinations` khi danh sách đã tải
 * (nhãn đã biến mất khỏi catalog sẽ không dẫn tới lần tìm vô nghĩa), và được đổi về đúng nhãn chuẩn.
 */
export function buildPlaceOptions({ text, recent, destinations, exclude }: PlaceOptionsInput): PlaceOptions {
  const skip = exclude?.trim() ? fold(exclude) : null;
  const allowed = (name: string) => fold(name) !== skip;

  const canonical = recent
    .map((name) => (destinations ? matchDestination(name, destinations) : name))
    .filter((name): name is string => Boolean(name) && allowed(name as string));
  const shownRecent = fold(text) ? [] : canonical;
  const taken = new Set(shownRecent.map(fold));

  const pool = topDestinations(destinations, 50).filter((d) => allowed(d.destination) && !taken.has(fold(d.destination)));
  return { recent: shownRecent, popular: filterDestinations(text, pool).map((d) => d.destination) };
}
