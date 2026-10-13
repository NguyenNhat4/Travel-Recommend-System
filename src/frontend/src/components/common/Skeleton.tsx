import React from 'react';

/**
 * Khung chờ dùng chung (product.md §4.0 `Skeleton`): giữ đúng khung hình của nội dung thật để trang không trống và không
 * nhảy khi dữ liệu về. Sóng chạy ngang ở `.skeleton-wave` (globals.css), tắt khi người dùng chọn giảm chuyển động.
 */

/** Một khối xám có sóng; kích thước và bo góc do `className` quyết định. Trình đọc màn hình bỏ qua. */
export function SkeletonBlock({ className = '' }: { className?: string }) {
  return <div aria-hidden="true" className={`skeleton-wave ${className}`} />;
}

/** Vùng đang tải: trình đọc màn hình chỉ nghe `label`, các khối bên trong bị ẩn. `className` là bố cục của vùng. */
export function SkeletonStatus({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <div role="status" aria-busy="true" aria-label={label} className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

/** Khung thẻ `ProductCard` biến thể `grid`: ảnh 16:10, dòng điểm đến và đánh giá, tên hai dòng, giá. */
export function ProductCardSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white">
      <SkeletonBlock className="aspect-16/10 w-full" />
      <div className="flex flex-1 flex-col justify-between gap-3 p-4">
        <div className="space-y-2.5">
          <div className="flex items-center justify-between gap-3">
            <SkeletonBlock className="h-3.5 w-24 rounded" />
            <SkeletonBlock className="h-3.5 w-16 rounded" />
          </div>
          <SkeletonBlock className="h-4 w-full rounded" />
          <SkeletonBlock className="h-4 w-2/3 rounded" />
        </div>
        <div className="border-t border-slate-100 pt-3">
          <SkeletonBlock className="h-6 w-36 rounded" />
        </div>
      </div>
    </div>
  );
}

/** Khung thẻ `ProductCard` biến thể `row`: ảnh trái (16:10 trên điện thoại), điểm đến, tên, hai dòng mô tả, giá và nút bên dưới. */
export function ProductRowSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white md:h-60 md:flex-row">
      <SkeletonBlock className="aspect-16/10 w-full shrink-0 md:aspect-auto md:h-full md:w-64" />
      <div className="flex min-w-0 flex-1 flex-col justify-between gap-3 p-5">
        <div className="space-y-2.5">
          <div className="flex items-center justify-between gap-3">
            <SkeletonBlock className="h-3.5 w-28 rounded" />
            <SkeletonBlock className="h-3.5 w-16 rounded" />
          </div>
          <SkeletonBlock className="h-5 w-3/4 rounded" />
          <SkeletonBlock className="h-3.5 w-full rounded" />
          <SkeletonBlock className="h-3.5 w-5/6 rounded" />
        </div>
        <div className="flex items-end justify-between gap-4 border-t border-slate-100 pt-3">
          <SkeletonBlock className="h-6 w-36 rounded" />
          <SkeletonBlock className="h-9 w-28 rounded-lg" />
        </div>
      </div>
    </div>
  );
}
