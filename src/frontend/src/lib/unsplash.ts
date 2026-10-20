/**
 * Ảnh Unsplash đã lưu trong `public/images/unsplash/` (bản gốc 1920 px, WebP; tên file là mã ảnh).
 * Giấy phép Unsplash cho phép tải và dùng miễn phí, không bắt buộc ghi công. Ảnh đi qua `next/image`
 * để trình duyệt nhận đúng cỡ theo viewport; không tải thẳng từ images.unsplash.com.
 */
export function unsplashPath(photoId: string): string {
  return `/images/unsplash/${photoId}.webp`;
}
