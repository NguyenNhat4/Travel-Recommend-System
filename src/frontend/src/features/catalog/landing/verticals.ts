/**
 * Cấu hình bốn trang danh mục (docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md §3).
 * Thêm một danh mục = thêm một mục ở đây, một `page.tsx` và một mục ở `navConfig.ts`.
 * Mọi chữ hiển thị là lời của V-OTA; không có tên sản phẩm, giá hay số liệu (dữ liệu đến từ API).
 */
import type { Taxonomy } from '../../../types/travel';

export type VerticalId = 'hotels' | 'flights' | 'experiences' | 'combos';

export { DEFAULT_QUERY } from '../../../services/search';

export interface VerticalTab {
  taxonomy: Taxonomy;
  /** Nhãn tab; chỉ hiện khi danh mục có từ hai tab trở lên. */
  label: string;
  popularTitle: string;
  cheapTitle: string;
  /** Danh từ dùng trong câu rỗng: "Chưa có {noun} tại {điểm đến}". */
  noun: string;
  /** Từ nối trước điểm đến trong tiêu đề khối: "… tại Nha Trang", "… đến Nha Trang". */
  atWord: string;
}

export interface SheetConfig {
  /**
   * `destinations`: điểm đến phổ biến (tour, golf). `famous-hotels`: khách sạn nổi tiếng khi bấm ô (`/hotels`, `/combos`).
   * `airports`: sân bay hiện hành của catalog, chỉ nhận sân bay thật (`/flights`, spec ui-dia-diem-san-bay-va-khach-san-noi-tieng).
   */
  location: { label: string; placeholder: string; suggest: 'destinations' | 'famous-hotels' | 'airports' };
  /** Chỉ vé máy bay: ô điểm đi, chọn sân bay hiện hành như ô điểm đến. */
  origin?: { label: string; placeholder: string };
  dates: {
    mode: 'range' | 'single' | 'single-or-return';
    startLabel: string;
    endLabel?: string;
  };
  guestsLabel: string;
  rooms: boolean;
}

export interface VerticalConfig {
  id: VerticalId;
  route: string;
  title: string;
  subtitle: string;
  heroImage: string;
  tabs: VerticalTab[];
  sheet: SheetConfig;
  promo: { title: string; body: string; cta: string; prompt: string };
}

const heroUrl = (photo: string) => `https://images.unsplash.com/photo-${photo}?q=80&w=2000&auto=format&fit=crop`;

const PROMO_BODY = 'Nói với trợ lý AI chuyến đi bạn muốn: trợ lý lập lịch từng ngày bằng khách sạn, vé và trải nghiệm có thật trong hệ thống.';

export const VERTICALS: Record<VerticalId, VerticalConfig> = {
  hotels: {
    id: 'hotels',
    route: '/hotels',
    title: 'Khách sạn & resort',
    subtitle: 'Tìm nơi nghỉ phù hợp cho chuyến đi tiếp theo của bạn',
    heroImage: heroUrl('1582719508461-905c673771fd'),
    tabs: [{
      taxonomy: 'hotel', label: 'Khách sạn', noun: 'khách sạn', atWord: 'tại',
      popularTitle: 'Khách sạn và resort phổ biến', cheapTitle: 'Khách sạn giá tốt nhất',
    }],
    sheet: {
      location: { label: 'Địa điểm', placeholder: 'Nhập điểm đến', suggest: 'famous-hotels' },
      dates: { mode: 'range', startLabel: 'Ngày đi', endLabel: 'Ngày về' },
      guestsLabel: 'Số lượng',
      rooms: true,
    },
    promo: {
      title: 'Chưa biết nên ở đâu?', body: PROMO_BODY, cta: 'Lên lịch trình với trợ lý AI',
      prompt: 'Gợi ý khách sạn và lịch trình 3 ngày cho chuyến đi của tôi',
    },
  },
  flights: {
    id: 'flights',
    route: '/flights',
    title: 'Vé máy bay',
    subtitle: 'Chọn chặng bay và ngày đi thuận tiện cho hành trình của bạn',
    heroImage: heroUrl('1436491865332-7a61a109cc05'),
    tabs: [{
      taxonomy: 'flight', label: 'Vé máy bay', noun: 'vé máy bay', atWord: 'đến',
      popularTitle: 'Chặng bay phổ biến', cheapTitle: 'Vé giá tốt nhất',
    }],
    sheet: {
      origin: { label: 'Điểm đi', placeholder: 'Chọn sân bay đi' },
      location: { label: 'Điểm đến', placeholder: 'Chọn sân bay đến', suggest: 'airports' },
      dates: { mode: 'single-or-return', startLabel: 'Ngày đi', endLabel: 'Ngày về' },
      guestsLabel: 'Hành khách',
      rooms: false,
    },
    promo: {
      title: 'Chưa chốt điểm đến?', body: PROMO_BODY, cta: 'Lên lịch trình với trợ lý AI',
      prompt: 'Gợi ý chuyến bay và lịch trình 3 ngày cho chuyến đi của tôi',
    },
  },
  experiences: {
    id: 'experiences',
    route: '/experiences',
    title: 'Tour và trải nghiệm',
    subtitle: 'Vé tham quan, vui chơi và sân golf tại điểm đến của bạn',
    heroImage: heroUrl('1530789253388-582c481c54b0'),
    tabs: [
      {
        taxonomy: 'attraction', label: 'Vé tham quan', noun: 'vé tham quan', atWord: 'tại',
        popularTitle: 'Vé tham quan phổ biến', cheapTitle: 'Vé tham quan giá tốt nhất',
      },
      {
        taxonomy: 'golf', label: 'Sân golf', noun: 'sân golf', atWord: 'tại',
        popularTitle: 'Sân golf phổ biến', cheapTitle: 'Sân golf giá tốt nhất',
      },
    ],
    sheet: {
      location: { label: 'Điểm đến', placeholder: 'Nhập điểm đến', suggest: 'destinations' },
      dates: { mode: 'single', startLabel: 'Ngày sử dụng' },
      guestsLabel: 'Số khách',
      rooms: false,
    },
    promo: {
      title: 'Muốn có sẵn lịch vui chơi?', body: PROMO_BODY, cta: 'Lên lịch trình với trợ lý AI',
      prompt: 'Gợi ý các điểm vui chơi và lịch trình 3 ngày cho chuyến đi của tôi',
    },
  },
  combos: {
    id: 'combos',
    route: '/combos',
    title: 'Combo du lịch',
    subtitle: 'Gói kết hợp lưu trú, vé và vui chơi trong một lần đặt',
    heroImage: heroUrl('1506929562872-bb421503ef21'),
    tabs: [{
      taxonomy: 'combo', label: 'Combo', noun: 'combo', atWord: 'tại',
      popularTitle: 'Combo được chọn nhiều', cheapTitle: 'Combo giá tốt nhất',
    }],
    sheet: {
      location: { label: 'Điểm đến', placeholder: 'Nhập điểm đến', suggest: 'famous-hotels' },
      dates: { mode: 'single', startLabel: 'Ngày bắt đầu' },
      guestsLabel: 'Số khách',
      rooms: false,
    },
    promo: {
      title: 'Cần một gói vừa ý?', body: PROMO_BODY, cta: 'Lên lịch trình với trợ lý AI',
      prompt: 'Gợi ý combo phù hợp cho chuyến đi 3 ngày của tôi',
    },
  },
};

export const VERTICAL_LIST: VerticalConfig[] = [VERTICALS.hotels, VERTICALS.flights, VERTICALS.experiences, VERTICALS.combos];

/** Tab theo tham số `?type=`; giá trị lạ hoặc thiếu thì lấy tab đầu. */
export function resolveTab(config: VerticalConfig, type: string | null | undefined): VerticalTab {
  return config.tabs.find((tab) => tab.taxonomy === type) ?? config.tabs[0];
}

export function verticalForTaxonomy(taxonomy: Taxonomy): VerticalConfig {
  return VERTICAL_LIST.find((v) => v.tabs.some((tab) => tab.taxonomy === taxonomy)) ?? VERTICALS.hotels;
}

/** "Chặng bay phổ biến đến Nha Trang" khi có điểm đến, nếu không thì tiêu đề gốc. */
export function titleWithDestination(title: string, tab: VerticalTab, destination?: string | null): string {
  return destination ? `${title} ${tab.atWord} ${destination}` : title;
}
