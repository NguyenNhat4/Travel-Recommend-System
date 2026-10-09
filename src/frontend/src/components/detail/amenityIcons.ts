import {
  Accessibility, Baby, Bath, Bus, Car, Check, CigaretteOff, Coffee, ConciergeBell, DoorOpen, Dumbbell, Flower2, GlassWater,
  Lock, Phone, Presentation, Refrigerator, ShowerHead, Shirt, Snowflake, Sparkles, Sunrise, Tv, Umbrella, Utensils, Waves,
  Wifi, Wind, Wine, type LucideIcon,
} from 'lucide-react';

/** Bỏ dấu, hạ chữ thường: "Điều hoà", "điều hòa" và "dieu hoa" là một. */
function fold(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/gi, 'd').toLowerCase();
}

/** Luật đầu tiên khớp thắng, nên cụm cụ thể ("bồn tắm") đứng trước cụm chung ("phòng tắm"). */
const RULES: ReadonlyArray<readonly [RegExp, LucideIcon]> = [
  [/wifi|wi-fi|internet/, Wifi],
  [/dieu hoa|may lanh|air ?con|khong khi/, Snowflake],
  [/bon tam|bon nuoc nong|jacuzzi|bathtub/, Bath],
  [/voi sen|shower|phong tam/, ShowerHead],
  [/\btv\b|ti vi|truyen hinh|man hinh phang|television/, Tv],
  [/ban cong|san hien|balcony|terrace/, DoorOpen],
  [/ket an toan|ket sat|\bsafe\b/, Lock],
  [/minibar|tu lanh|refrigerator/, Refrigerator],
  [/nuoc uong|nuoc suoi|nuoc dong chai/, GlassWater],
  [/am dun|ca phe|\btra\b|coffee|kettle/, Coffee],
  [/may say toc|hair ?dryer/, Wind],
  [/dien thoai|phone/, Phone],
  [/ao choang|dep di|quan ao|giat|ui do|\bdep\b/, Shirt],
  [/don phong|ve sinh|ban chai|luoc|mu tam|dao cao|khan/, Sparkles],
  [/le tan|concierge|24 ?(gio|h)|24\/7/, ConciergeBell],
  [/dua don|san bay|shuttle/, Bus],
  [/do xe|bai do|parking|gara/, Car],
  [/ho boi|be boi|pool/, Waves],
  [/nha hang|restaurant|bua sang|\ban sang\b|breakfast/, Utensils],
  [/\bbar\b|cocktail|quay bar/, Wine],
  [/spa|massage|mat-xa|xong hoi|sauna|cham soc/, Flower2],
  [/gym|the duc|fitness/, Dumbbell],
  [/bai bien|bien rieng|beach/, Umbrella],
  [/tre em|vui choi|\bkids?\b|tre con/, Baby],
  [/hoi nghi|phong hop|hop\/|meeting/, Presentation],
  [/xe lan|khuyet tat|accessib/, Accessibility],
  [/khong hut thuoc|non-?smoking/, CigaretteOff],
  [/tam nhin|view|huong/, Sunrise],
];

/** Icon theo loại tiện ích từ chuỗi tự do của nguồn; không nhận ra thì dấu tích. */
export function amenityIcon(label: string): LucideIcon {
  const text = fold(label);
  return RULES.find(([pattern]) => pattern.test(text))?.[1] ?? Check;
}

/** Tiện ích nên nêu ngay trên thẻ phòng, theo mức quan trọng với người đặt phòng (mỗi loại icon một lần). */
const HIGHLIGHT_ORDER: readonly LucideIcon[] = [Wifi, Snowflake, Bath, ShowerHead, Tv, DoorOpen, Lock, Refrigerator, Coffee, Wind];

export function pickHighlights(items: readonly string[], limit = 5): string[] {
  const byIcon = new Map<LucideIcon, string>();
  for (const item of items) {
    const icon = amenityIcon(item);
    if (icon !== Check && !byIcon.has(icon)) byIcon.set(icon, item);
  }
  const ranked = HIGHLIGHT_ORDER.filter((icon) => byIcon.has(icon)).map((icon) => byIcon.get(icon) as string);
  return ranked.slice(0, limit);
}
