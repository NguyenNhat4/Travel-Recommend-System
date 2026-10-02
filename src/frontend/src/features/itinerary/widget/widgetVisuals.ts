import type React from 'react';
import { placeholderImage } from '../../../services/catalog';
import type { Product } from '../../../types/travel';

/** Ảnh lỗi thì đổi sang placeholder theo loại (hop-dong-tich-hop-frontend.md §6.6), một lần để không lặp nếu placeholder cũng lỗi. */
export function placeholderOnError(taxonomy: string) {
  return (event: React.SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    const fallback = placeholderImage(taxonomy);
    if (!image.src.endsWith(fallback)) image.src = fallback;
  };
}

/**
 * Tag của thẻ khách sạn trong lịch trình, chỉ dựng từ `attributes` thật của catalog: không suy từ tên, ghi chú hay tiêu đề
 * và không có tag mặc định (docs/spec/hop-dong-tich-hop-frontend.md §6.3, §9.5). Nhãn theo bảng
 * `hop-dong-tich-hop-backend.md` §2.5; backend chỉ giữ các khoá này trong lịch trình (`SUMMARY_ATTRIBUTE_KEYS`).
 */
const HOTEL_TAG_LABEL: [key: 'oceanView' | 'privateBeach' | 'pool', label: string][] = [
  ['oceanView', 'Hướng biển'],
  ['privateBeach', 'Bãi biển riêng'],
  ['pool', 'Hồ bơi'],
];

export function hotelTags(product: Pick<Product, 'attributes'>): string[] {
  const attributes = product.attributes ?? {};
  const tags: string[] = [];
  const stars = Number(attributes.starRating);
  if (Number.isInteger(stars) && stars >= 1 && stars <= 5) tags.push(`${stars} sao`);
  for (const [key, label] of HOTEL_TAG_LABEL) {
    if (attributes[key] === true) tags.push(label);
  }
  return tags;
}
