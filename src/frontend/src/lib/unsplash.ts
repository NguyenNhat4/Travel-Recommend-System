/**
 * Ảnh Unsplash theo chiều rộng. Ảnh `w=2000` nặng hơn nhiều so với màn hình điện thoại (ảnh panorama trang chủ
 * ~1,1 MB ở mobile), nên mọi ảnh nền toàn màn hình đi qua đây: `src` là cỡ mặc định, `srcSet` để trình duyệt chọn
 * đúng cỡ theo chiều rộng viewport và mật độ điểm ảnh.
 */
export const UNSPLASH_DEFAULT_WIDTH = 1280;

const UNSPLASH_WIDTHS = [640, 960, 1280, 1920] as const;

export function unsplashUrl(photoId: string, width: number): string {
  return `https://images.unsplash.com/photo-${photoId}?q=80&w=${width}&auto=format&fit=crop`;
}

export function unsplashSrcSet(photoId: string): string {
  return UNSPLASH_WIDTHS.map((width) => `${unsplashUrl(photoId, width)} ${width}w`).join(', ');
}
