'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Images, X } from 'lucide-react';
import { placeholderImage } from '../../services/catalog';
import type { Taxonomy } from '../../types/travel';

const MAX_IMAGES = 40;
const isUrl = (value: unknown): value is string => typeof value === 'string' && /^https?:\/\//.test(value);

/**
 * Ảnh của sản phẩm: `attributes.images` (danh sách ảnh của nguồn) và `imageUrl` làm ảnh đầu; bỏ trùng và đường dẫn không
 * phải http(s). Không có ảnh nào thì trả `imageUrl` (ảnh thay thế theo loại) để vẫn có một khung ảnh.
 */
export function imagesOf(product: { imageUrl?: string; attributes?: Record<string, unknown> | null }): string[] {
  const raw = product.attributes?.images;
  const list = Array.isArray(raw) ? raw.filter(isUrl) : [];
  const first = product.imageUrl;
  const all = isUrl(first) ? [first, ...list] : list;
  const unique = Array.from(new Set(all)).slice(0, MAX_IMAGES);
  return unique.length ? unique : first ? [first] : [];
}

/** Ảnh nguồn thường rất nặng (vài MB): ảnh chính tải ngay và được ưu tiên băng thông, ảnh còn lại tải sau. */
function Photo({ src, alt, taxonomy, className, priority }: { src: string; alt: string; taxonomy: Taxonomy; className?: string; priority?: boolean }) {
  return (
    <img
      src={src}
      alt={alt}
      loading={priority ? 'eager' : 'lazy'}
      fetchPriority={priority ? 'high' : 'low'}
      decoding="async"
      referrerPolicy="no-referrer"
      onError={(event) => {
        const fallback = placeholderImage(taxonomy);
        if (!event.currentTarget.src.endsWith(fallback)) event.currentTarget.src = fallback;
      }}
      className={className ?? 'h-full w-full object-cover'}
    />
  );
}

interface LightboxProps {
  images: string[];
  index: number;
  title: string;
  taxonomy: Taxonomy;
  onClose: () => void;
  onIndex: (index: number) => void;
}

/** Xem ảnh lớn: ← → đổi ảnh, Esc đóng, giữ tiêu điểm trong hộp thoại và trả về nút đã mở khi đóng. */
export function ImageLightbox({ images, index, title, taxonomy, onClose, onIndex }: LightboxProps) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const count = images.length;
  const go = useCallback((step: number) => onIndex((index + step + count) % count), [index, count, onIndex]);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
      opener?.focus?.();
    };
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      else if (event.key === 'ArrowLeft') go(-1);
      else if (event.key === 'ArrowRight') go(1);
      else if (event.key === 'Tab') {   // giữ tiêu điểm trong hộp thoại
        const focusable = document.querySelectorAll<HTMLElement>('[data-lightbox] button');
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [go, onClose]);

  const nav = 'absolute top-1/2 grid h-11 w-11 -translate-y-1/2 place-items-center rounded-full bg-white/15 text-white backdrop-blur transition hover:bg-white/30 focus-visible:outline-2 focus-visible:outline-white';
  return (
    <div role="dialog" aria-modal="true" aria-label={`Ảnh ${title}`} data-lightbox className="fixed inset-0 z-[60] flex flex-col bg-black/90">
      <div className="flex items-center justify-between gap-4 px-4 py-3 text-white">
        <p className="min-w-0 truncate text-sm font-semibold">{title}</p>
        <div className="flex items-center gap-3">
          <span className="text-xs tabular-nums text-white/80" aria-live="polite">{index + 1} / {count}</span>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Đóng" className="grid h-11 w-11 place-items-center rounded-full bg-white/15 hover:bg-white/30 focus-visible:outline-2 focus-visible:outline-white">
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="relative flex min-h-0 flex-1 items-center justify-center px-4">
        <img
          key={images[index]}
          src={images[index]}
          alt={`${title} — ảnh ${index + 1}`}
          referrerPolicy="no-referrer"
          onError={(event) => {
            const fallback = placeholderImage(taxonomy);
            if (!event.currentTarget.src.endsWith(fallback)) event.currentTarget.src = fallback;
          }}
          className="max-h-full max-w-full rounded-lg object-contain"
        />
        {count > 1 && (
          <>
            <button type="button" onClick={() => go(-1)} aria-label="Ảnh trước" className={`${nav} left-3`}><ChevronLeft className="h-6 w-6" aria-hidden="true" /></button>
            <button type="button" onClick={() => go(1)} aria-label="Ảnh sau" className={`${nav} right-3`}><ChevronRight className="h-6 w-6" aria-hidden="true" /></button>
          </>
        )}
      </div>
      {count > 1 && (
        <div className="flex gap-2 overflow-x-auto px-4 py-3" role="group" aria-label="Chọn ảnh">
          {images.map((src, i) => (
            <button key={src} type="button" onClick={() => onIndex(i)} aria-label={`Ảnh ${i + 1}`} aria-current={i === index ? 'true' : undefined}
              className={`h-14 w-20 shrink-0 overflow-hidden rounded-md border-2 transition ${i === index ? 'border-white' : 'border-transparent opacity-60 hover:opacity-100'}`}>
              <Photo src={src} alt="" taxonomy={taxonomy} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Lớp lưới của ô thứ `slot` (0 là ảnh lớn) theo số ảnh có: lớn 2×2 bên trái, tối đa bốn ảnh nhỏ bên phải lấp đầy lưới.
 * Điện thoại chỉ có ảnh lớn phủ cả lưới. Viết nguyên tên lớp (không ghép chuỗi) để Tailwind sinh được.
 */
function cellClass(slot: number, total: number): string {
  if (slot === 0) return total === 1 ? 'col-span-4 row-span-2' : 'col-span-4 row-span-2 md:col-span-2';
  if (total === 2) return 'hidden md:block md:col-span-2 md:row-span-2';
  if (total === 3) return 'hidden md:block md:col-span-2';
  if (total === 4 && slot === 3) return 'hidden md:block md:col-span-2';
  return 'hidden md:block';
}

interface GalleryProps {
  images: string[];
  name: string;
  taxonomy: Taxonomy;
  /** Phủ lớp "tạm hết chỗ" lên ảnh. */
  unavailable?: boolean;
}

/**
 * Bộ ảnh đầu trang chi tiết: một ảnh lớn và tối đa bốn ảnh nhỏ (màn hình rộng), một ảnh duy nhất trên điện thoại; nút "N ảnh" và
 * mọi ô đều mở trình xem ảnh lớn.
 */
export const ProductGallery: React.FC<GalleryProps> = ({ images, name, taxonomy, unavailable }) => {
  const [open, setOpen] = useState<number | null>(null);
  if (images.length === 0) return null;
  const shown = images.slice(0, 5);
  const total = shown.length;
  const badge = (className: string) => (
    <span className={`pointer-events-none absolute bottom-3 right-3 items-center gap-1.5 rounded-lg bg-white/90 px-2.5 py-1 text-xs font-semibold text-slate-800 shadow ${className}`}>
      <Images className="h-3.5 w-3.5" aria-hidden="true" />{images.length} ảnh
    </span>
  );
  return (
    <>
      <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 shadow-md">
        <div className="grid aspect-4/3 grid-cols-4 grid-rows-2 gap-1 md:aspect-16/7">
          {shown.map((src, slot) => (
            <button
              key={src}
              type="button"
              onClick={() => setOpen(slot)}
              aria-label={slot === 0 ? `Xem ${images.length} ảnh của ${name}` : `Xem ảnh ${slot + 1}`}
              className={`relative min-h-0 overflow-hidden focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-600 ${cellClass(slot, total)}`}
            >
              <Photo src={src} alt={slot === 0 ? name : ''} taxonomy={taxonomy} priority={slot === 0} className="h-full w-full object-cover transition-transform duration-300 hover:scale-[1.03] motion-reduce:transition-none" />
              {images.length > 1 && slot === 0 && badge('inline-flex md:hidden')}
              {images.length > 1 && total > 1 && slot === total - 1 && badge('hidden md:inline-flex')}
            </button>
          ))}
        </div>
        {unavailable && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-900/70 text-sm font-bold uppercase tracking-wider text-white sm:text-base">
            Sản phẩm hiện đã tạm hết chỗ
          </div>
        )}
      </div>
      {open !== null && (
        <ImageLightbox images={images} index={open} title={name} taxonomy={taxonomy} onClose={() => setOpen(null)} onIndex={setOpen} />
      )}
    </>
  );
};
