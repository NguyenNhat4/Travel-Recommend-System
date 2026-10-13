import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, X, ZoomIn } from 'lucide-react';
import { placeholderOnError } from './widgetVisuals';

const THUMBNAILS = 4;

interface WidgetProductGalleryProps {
  images: string[];
  name: string;
  taxonomy: string;
  activeImage: number;
  onSelect: (index: number) => void;
}

/** Chỉ dùng ảnh catalog; giữ khung ảnh ổn định khi tải và khi đổi ảnh. */
export function WidgetProductGallery({ images, name, taxonomy, activeImage, onSelect }: WidgetProductGalleryProps) {
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open) dialog.current?.showModal?.();
    else dialog.current?.close?.();
  }, [open]);
  const mainImage = images[activeImage] ?? images[0];
  if (!mainImage) return null;
  const thumbnails = images.filter((url) => url !== mainImage);
  const hiddenCount = Math.max(0, thumbnails.length - THUMBNAILS);

  return (
    <><div className={`grid gap-2 ${thumbnails.length ? 'grid-cols-5' : 'grid-cols-1'}`}>
      <button type="button" onClick={() => setOpen(true)} aria-label={`Phóng to ảnh ${activeImage + 1} của ${name}`} className={`relative overflow-hidden rounded-xl bg-slate-100 ${thumbnails.length ? 'col-span-3 aspect-square' : 'aspect-[4/3]'}`}>
        <img src={mainImage} alt={name} decoding="async" referrerPolicy="no-referrer"
          onError={placeholderOnError(taxonomy)} className="absolute inset-0 h-full w-full object-cover" />
        <span className="absolute bottom-2 right-2 rounded-full bg-black/50 p-2 text-white"><ZoomIn className="h-4 w-4" /></span>
      </button>
      {thumbnails.length > 0 && (
        <div className={`col-span-2 grid auto-rows-fr gap-2 ${thumbnails.length <= 2 ? 'grid-cols-1' : 'grid-cols-2'}`}>
          {thumbnails.slice(0, THUMBNAILS).map((url, index) => (
            <button key={url} type="button" onClick={() => { onSelect(images.indexOf(url)); setOpen(true); }}
              aria-label={`Xem ảnh ${images.indexOf(url) + 1} của ${name}`}
              className="group relative min-h-0 overflow-hidden rounded-lg bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600">
              <img src={url} alt="" decoding="async" referrerPolicy="no-referrer"
                onError={placeholderOnError(taxonomy)} className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105 motion-reduce:transition-none" />
              {hiddenCount > 0 && index === THUMBNAILS - 1 && (
                <span className="absolute inset-0 flex items-center justify-center bg-slate-900/50 text-lg font-bold text-white">+{hiddenCount}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
    <dialog ref={dialog} onClose={() => setOpen(false)} aria-label={`Ảnh của ${name}`}
      onClick={(event) => { if (event.target === event.currentTarget) setOpen(false); }}
      onKeyDown={(event) => {
        event.stopPropagation();
        if (event.key === 'Escape') setOpen(false);
        if (event.key === 'ArrowLeft') onSelect((activeImage - 1 + images.length) % images.length);
        if (event.key === 'ArrowRight') onSelect((activeImage + 1) % images.length);
      }} className="fixed inset-0 m-auto h-fit w-[95vw] max-w-5xl overflow-hidden rounded-2xl bg-slate-950 p-4 text-white shadow-2xl backdrop:bg-black/80">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-sm">{name} · {activeImage + 1}/{images.length}</p>
        <button type="button" aria-label="Đóng ảnh phóng to" onClick={() => setOpen(false)} className="flex h-11 w-11 items-center justify-center rounded-full hover:bg-white/20"><X /></button>
      </div>
      {open && <img src={mainImage} alt={name} referrerPolicy="no-referrer" onError={placeholderOnError(taxonomy)} className="max-h-[75vh] w-full object-contain" />}
      {images.length > 1 && <div className="mt-3 flex justify-center gap-4">
        <button type="button" aria-label="Ảnh trước" onClick={() => onSelect((activeImage - 1 + images.length) % images.length)} className="flex h-11 w-11 items-center justify-center rounded-full bg-white/10"><ChevronLeft /></button>
        <button type="button" aria-label="Ảnh tiếp theo" onClick={() => onSelect((activeImage + 1) % images.length)} className="flex h-11 w-11 items-center justify-center rounded-full bg-white/10"><ChevronRight /></button>
      </div>}
    </dialog></>
  );
}
