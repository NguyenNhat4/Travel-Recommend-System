/**
 * Từ giá trị của tấm tìm kiếm sang URL `/search` (docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md §3).
 * Ngày và số khách đi theo URL làm ngữ cảnh chuyến đi (features/search/tripContext.ts), không phải bộ lọc phòng trống.
 */
import type { Taxonomy } from '../../../types/travel';
import { DEFAULT_QUERY } from '../../../services/search';
import { serializeTripContext, type TripContext } from '../../search/tripContext';

/** Bỏ dấu, hạ chữ thường: "Đà Nẵng" và "da nang" là một. */
export function fold(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/gi, 'd')
    .toLowerCase()
    .trim();
}

type Named = { destination: string };

/** Nhãn điểm đến khớp đúng với văn bản người dùng gõ (không phân biệt dấu, hoa thường); không khớp thì null. */
export function matchDestination(text: string, destinations: readonly Named[] | null): string | null {
  if (!destinations || !text.trim()) return null;
  const wanted = fold(text);
  return destinations.find((d) => fold(d.destination) === wanted)?.destination ?? null;
}

/** Gợi ý cho ô địa điểm: chứa đoạn đã gõ (không phân biệt dấu). Ô trống thì giữ nguyên thứ tự đầu vào. */
export function filterDestinations<T extends Named>(text: string, destinations: readonly T[], limit = 8): T[] {
  const wanted = fold(text);
  const matches = wanted ? destinations.filter((d) => fold(d.destination).includes(wanted)) : [...destinations];
  return matches.slice(0, limit);
}

export interface SearchSheetValues {
  taxonomy: Taxonomy;
  /** Điểm đi (chỉ vé máy bay), gõ tự do. */
  origin: string;
  /** Văn bản trong ô địa điểm. */
  location: string;
  /** Nhãn điểm đến chuẩn khi người dùng chọn gợi ý hoặc gõ đúng nhãn; null thì `location` đi vào `q`. */
  destination: string | null;
  trip: TripContext;
}

export function buildSearchHref(values: SearchSheetValues): string {
  const text = [values.origin, values.destination ? '' : values.location]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(' ');
  const params = new URLSearchParams();
  params.set('q', text || DEFAULT_QUERY[values.taxonomy]);
  params.set('type', values.taxonomy);
  if (values.destination) params.set('destination', values.destination);
  const trip = serializeTripContext(values.trip);
  return `/search?${params.toString()}${trip ? `&${trip}` : ''}`;
}

/** Giá trị của query param có thể là mảng khi lặp khóa; lấy giá trị đầu, bỏ khoảng trắng thừa. */
export function pickParam(value: string | string[] | undefined): string | undefined {
  const first = Array.isArray(value) ? value[0] : value;
  const trimmed = first?.trim();
  return trimmed || undefined;
}
