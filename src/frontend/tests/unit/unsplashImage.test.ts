import { existsSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { coverFor } from '../../src/features/catalog/landing/destinationCovers';
import { VERTICAL_LIST } from '../../src/features/catalog/landing/verticals';
import { unsplashPath } from '../../src/lib/unsplash';

const PHOTO = '1582719508461-905c673771fd';
/** Nhãn điểm đến có ảnh bìa (destinationCovers.ts). */
const COVERED_DESTINATIONS = ['Nha Trang', 'Phú Quốc', 'Đà Nẵng', 'Hội An', 'TP. Hồ Chí Minh', 'Hạ Long', 'Quy Nhơn', 'Đà Lạt', 'Hà Nội', 'Huế'];

/** Đường dẫn ảnh trong `src` phải có file tương ứng trong `public/`, nếu không trình duyệt nhận 404. */
const publicFile = (src: string) => path.join(process.cwd(), 'public', src);

describe('unsplashPath', () => {
  it('trỏ tới file WebP trong public/images/unsplash, không tới images.unsplash.com', () => {
    expect(unsplashPath(PHOTO)).toBe(`/images/unsplash/${PHOTO}.webp`);
  });
});

describe('ảnh Unsplash hard-code đã có trong public', () => {
  it('mọi ảnh hero của danh mục có file', () => {
    for (const config of VERTICAL_LIST) {
      expect(existsSync(publicFile(unsplashPath(config.heroPhoto))), config.heroPhoto).toBe(true);
    }
  });

  it('mọi ảnh bìa điểm đến có file', () => {
    for (const destination of COVERED_DESTINATIONS) {
      const src = coverFor(destination);
      expect(src, destination).not.toBeNull();
      expect(existsSync(publicFile(src as string)), destination).toBe(true);
    }
  });
});
