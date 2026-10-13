/**
 * Từ giá trị của tấm tìm kiếm sang URL của trang danh mục (docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md §3;
 * kết quả hiện tại chính trang đó: đề xuất PRD update-archive/2026-10-07-tim-kiem-tai-trang-danh-muc.md).
 * Ngày và số khách đi theo URL làm ngữ cảnh chuyến đi (features/search/tripContext.ts), không phải bộ lọc phòng trống.
 */
import type { Taxonomy } from '../../../types/travel';
import { DEFAULT_QUERY } from '../../../services/search';
import { serializeTripContext, type TripContext } from '../../search/tripContext';
import { verticalForTaxonomy } from './verticals';

/** Bỏ dấu, hạ chữ thường: "Đà Nẵng" và "da nang" là một. */
export function fold(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/gi, 'd')
    .toLowerCase()
    .trim();
}

/**
 * Khớp theo đầu từ, không phân biệt dấu và hoa thường (FR-SRC-05): "ha" thấy "Hà Nội" và "Hạ Long". Bỏ dấu thì "Đảo" là
 * "dao", nên "da" cũng thấy "Côn Đảo"; gợi ý sắp xếp mục bắt đầu bằng chữ gõ lên trước (xem airportOptions).
 */
export function startsAWord(text: string, query: string): boolean {
  const wanted = fold(query).replace(/\s+/g, ' ').trim();
  if (!wanted) return true;
  const words = fold(text).replace(/[.,()\-]+/g, ' ').replace(/\s+/g, ' ').trim();
  return ` ${words} `.includes(` ${wanted}`);
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

/** `q` là câu mặc định theo danh mục (ô tìm trống), không phải chữ người dùng gõ. */
export function isDefaultQuery(query: string): boolean {
  return (Object.values(DEFAULT_QUERY) as string[]).includes(query.trim().toLowerCase());
}

/**
 * URL của lần tìm: về chính trang danh mục của loại dịch vụ (`/hotels?q=…`), `q` có mặt nghĩa là đang tìm.
 * `type` chỉ ghi khi không phải tab đầu của trang (như `LandingHero.tabHref`). Vé máy bay tìm tại chỗ ở `/flights`
 * (`flightHref.ts`); nhánh này chỉ là đường dự phòng về `/search?type=flight`.
 */
export function buildSearchHref(values: SearchSheetValues): string {
  const text = [values.origin, values.destination ? '' : values.location]
    .map((part) => part.trim())
    .filter(Boolean)
    .join(' ');
  const vertical = values.taxonomy === 'flight' ? null : verticalForTaxonomy(values.taxonomy);
  const params = new URLSearchParams();
  params.set('q', text || DEFAULT_QUERY[values.taxonomy]);
  if (!vertical || values.taxonomy !== vertical.tabs[0].taxonomy) params.set('type', values.taxonomy);
  if (values.destination) params.set('destination', values.destination);
  const trip = serializeTripContext(values.trip);
  return `${vertical?.route ?? '/search'}?${params.toString()}${trip ? `&${trip}` : ''}`;
}

/** Giá trị của query param có thể là mảng khi lặp khóa; lấy giá trị đầu, bỏ khoảng trắng thừa. */
export function pickParam(value: string | string[] | undefined): string | undefined {
  const first = Array.isArray(value) ? value[0] : value;
  const trimmed = first?.trim();
  return trimmed || undefined;
}
