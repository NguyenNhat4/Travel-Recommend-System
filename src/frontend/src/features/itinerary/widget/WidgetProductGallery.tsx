import React from 'react';
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
  const mainImage = images[activeImage] ?? images[0];
  if (!mainImage) return null;
  const thumbnails = images.filter((url) => url !== mainImage);
  const hiddenCount = Math.max(0, thumbnails.length - THUMBNAILS);

  return (
    <div className={`grid gap-2 ${thumbnails.length ? 'grid-cols-5' : 'grid-cols-1'}`}>
      <div className={`relative overflow-hidden rounded-xl bg-slate-100 ${thumbnails.length ? 'col-span-3 aspect-square' : 'aspect-[4/3]'}`}>
        <img src={mainImage} alt={name} decoding="async" referrerPolicy="no-referrer"
          onError={placeholderOnError(taxonomy)} className="absolute inset-0 h-full w-full object-cover" />
      </div>
      {thumbnails.length > 0 && (
        <div className={`col-span-2 grid auto-rows-fr gap-2 ${thumbnails.length <= 2 ? 'grid-cols-1' : 'grid-cols-2'}`}>
          {thumbnails.slice(0, THUMBNAILS).map((url, index) => (
            <button key={url} type="button" onClick={() => onSelect(images.indexOf(url))}
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
  );
}
