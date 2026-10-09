'use client';

import { useEffect, useState } from 'react';
import { getProduct, productFromApi } from '../../services/catalog';
import type { Product } from '../../types/travel';
import type { ApiBookingItem } from '../../services/booking';

/** Thông tin cơ sở hiển thị ở khối "Thông tin đặt chỗ"; phòng khách sạn lấy từ khách sạn cha (tên, hạng sao, địa chỉ, ảnh). */
export interface PropertyInfo {
  name: string;
  address?: string;
  starRating?: number;
  imageUrl?: string;
  amenities: string[];
}

/** Nhãn các tiện ích API trả về dạng cờ (`ProductAttributes`); chỉ liệt kê cờ có giá trị true. */
const AMENITY_LABELS: Record<string, string> = {
  wifi: 'Wi-Fi miễn phí', freeBreakfast: 'Bữa sáng', pool: 'Hồ bơi', privatePool: 'Hồ bơi riêng', kidsPool: 'Hồ bơi trẻ em',
  spa: 'Spa', parking: 'Chỗ đỗ xe', shuttle: 'Đưa đón', nearBeach: 'Gần biển', privateBeach: 'Bãi biển riêng',
  kidsClub: 'Câu lạc bộ trẻ em', balcony: 'Ban công', bathtub: 'Bồn tắm', kitchenette: 'Bếp nhỏ', butlerService: 'Quản gia',
  oceanView: 'Hướng biển', cityView: 'Hướng thành phố', gardenView: 'Hướng vườn', poolView: 'Hướng hồ bơi',
};

export function amenitiesOf(attributes: Record<string, unknown>): string[] {
  return Object.entries(AMENITY_LABELS).filter(([key]) => attributes[key] === true).map(([, label]) => label);
}

const cache = new Map<string, Promise<Product | null>>();

/** Chỉ cho test: bộ đệm cấp module sống lâu hơn một lần render. */
export function resetProductInfoCache(): void {
  cache.clear();
}

/** Một sản phẩm mỗi lần, dùng lại giữa các lần mở trang. Lỗi thì `null`: trang vẫn hiện được từ dữ liệu của đơn. */
function load(productId: string): Promise<Product | null> {
  let pending = cache.get(productId);
  if (!pending) {
    pending = Promise.resolve().then(() => getProduct(productId)).then(productFromApi).catch(() => null);
    cache.set(productId, pending);
    void pending.then((product) => { if (!product) cache.delete(productId); });
  }
  return pending;
}

function infoFrom(item: ApiBookingItem, own: Product | null, parent: Product | null): PropertyInfo {
  const source = parent ?? own;
  // Chỉ địa chỉ thật của catalog; `Product.address` tự lùi về tên điểm đến khi thiếu nên không dùng ở đây.
  const rawAddress = (source?.attributes as Record<string, unknown> | undefined)?.address;
  return {
    name: parent?.name ?? item.product.name,
    address: typeof rawAddress === 'string' && rawAddress ? rawAddress : undefined,
    starRating: typeof source?.attributes?.starRating === 'number' ? source.attributes.starRating : undefined,
    imageUrl: own?.imageUrl ?? source?.imageUrl,
    amenities: amenitiesOf((own?.attributes ?? source?.attributes ?? {}) as Record<string, unknown>),
  };
}

/** Thông tin cơ sở của từng mục đơn (khoá theo `bookingItemId`), nạp từ `GET /products/{id}` sau khi đơn đã hiển thị. */
export function useProductInfo(items: ApiBookingItem[]): Record<string, PropertyInfo> {
  const [info, setInfo] = useState<Record<string, PropertyInfo>>({});
  const key = items.map((i) => `${i.bookingItemId}:${i.product.productId}`).join('|');
  useEffect(() => {
    let alive = true;
    void Promise.all(items.map(async (item) => {
      const own = await load(item.product.productId);
      const parent = own?.parentProductId ? await load(own.parentProductId) : null;
      return [item.bookingItemId, infoFrom(item, own, parent)] as const;
    })).then((pairs) => { if (alive) setInfo(Object.fromEntries(pairs)); });
    return () => { alive = false; };
    // `items` đổi tham chiếu mỗi lần đơn được tải lại; chỉ nạp lại khi bộ sản phẩm thật sự đổi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return info;
}
