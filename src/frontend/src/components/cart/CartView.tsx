'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useTravel } from '../../context/TravelContext';
import { getProduct } from '../../services/catalog';
import { fetchRecommendations } from '../../services/recsys';
import type { ApiCartItem } from '../../services/booking';
import type { RecommendationResponse, Taxonomy } from '../../types/travel';
import { TaxonomyBadge } from '../common/TaxonomyBadge';
import { ProductCard } from '../common/ProductCard';
import { Trash2, ShoppingBag, ArrowRight, ShieldCheck, Sparkles, Loader2, AlertTriangle, Pencil } from 'lucide-react';
import { formatVnd } from '../confirmation/bookingLabels';
import { cartStateOf, guestsOfItem, sameCartState, type CartState } from '../checkout/allocation';
import { FareLines } from '../checkout/FareLines';
import { GuestCounters } from '../checkout/GuestCounters';
import { cartPayload, guestModeOf, guestsText, isValidCounts, maxOccupancyFromAttributes } from '../checkout/guestCounts';

function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function itemSummary(item: ApiCartItem): string {
  const guests = guestsText(guestsOfItem(item));
  if (item.product.taxonomy === 'hotel') {
    const nights = item.nights ?? 1;
    return `${item.usingDate} → ${addDays(item.usingDate, nights)} · ${nights} đêm · ${item.quantity} phòng · ${guests}`;
  }
  if (item.product.taxonomy === 'combo') return `Ngày dùng: ${item.usingDate} · ${item.quantity} gói`;
  return `Ngày dùng: ${item.usingDate} · ${guests}`;
}

/**
 * Nút [Sửa] của một mục: cùng bộ đếm với hộp đặt ở trang chi tiết, bấm Cập nhật thì `PATCH /cart/items/{id}` với `guests`
 * (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §6.9). Đơn giá vé trẻ em nằm ở `attributes` của sản phẩm nên chỉ tải khi mở.
 */
const GuestEditor: React.FC<{ item: ApiCartItem; onClose: () => void }> = ({ item, onClose }) => {
  const { updateCartItem } = useTravel();
  const mode = guestModeOf(item.product.taxonomy);
  const [draft, setDraft] = useState<CartState>(() => cartStateOf(item));
  const [attributes, setAttributes] = useState<Record<string, unknown> | null>((item.product.attributes ?? null) as Record<string, unknown> | null);
  const [pricesKnown, setPricesKnown] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getProduct(item.product.productId, controller.signal)
      .then((detail) => {
        setAttributes((prev) => ({ ...(prev ?? {}), ...((detail.attributes ?? {}) as Record<string, unknown>) }));
        setPricesKnown(true);
      })
      .catch(() => undefined); // không tải được thì chỉ ẩn đơn giá từng loại, vẫn sửa được
    return () => controller.abort();
  }, [item.product.productId]);

  const valid = isValidCounts(mode, draft, maxOccupancyFromAttributes(attributes));
  const changed = !sameCartState(cartStateOf(item), draft);
  const save = async () => {
    setSaving(true);
    const error = await updateCartItem(item.cartItemId, cartPayload(mode, draft)); // lỗi (ví dụ vượt sức chứa) do context báo bằng toast
    setSaving(false);
    if (!error) onClose();
  };

  return (
    <div role="group" aria-label={`Sửa số khách của ${item.product.name}`} className="rounded-xl border border-slate-200 bg-white p-4 space-y-3" data-testid="guest-editor">
      <GuestCounters taxonomy={item.product.taxonomy} unitPrice={item.product.unitPrice ?? 0} attributes={attributes}
        value={draft} onChange={setDraft} showPrices={pricesKnown} />
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="px-4 py-2 text-xs font-semibold text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50">Huỷ</button>
        <button type="button" onClick={() => void save()} disabled={!valid || !changed || saving}
          className="px-4 py-2 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 rounded-lg inline-flex items-center gap-1.5">
          {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />}Cập nhật
        </button>
      </div>
    </div>
  );
};

export const CartView: React.FC = () => {
  const {
    cart, removeFromCart, navigate, currentPersona, authReady, activeEvents, addToCart, openLoginModal,
  } = useTravel();
  const [recs, setRecs] = useState<RecommendationResponse | null>(null);
  const [editing, setEditing] = useState<string | null>(null);

  const items = useMemo(() => cart?.items ?? [], [cart]);
  const hasUnavailable = items.some((item) => !item.product.available);
  const primaryDestination = items[0]?.product.destination;

  // Gom nhóm "Chuyến {destination}" phía client (docs/spec/hop-dong-tich-hop-frontend.md §4.4)
  const itemsByDestination = useMemo(() => {
    const groups: Record<string, ApiCartItem[]> = {};
    for (const item of items) (groups[item.product.destination || 'Khác'] ??= []).push(item);
    return groups;
  }, [items]);

  // Thường được đặt cùng: GET /recommendations theo điểm đến đầu tiên; lỗi thì ẩn.
  useEffect(() => {
    if (!currentPersona || !primaryDestination) return;
    const controller = new AbortController();
    fetchRecommendations({ k: 4, destination: primaryDestination, signal: controller.signal })
      .then(setRecs).catch(() => setRecs(null));
    return () => controller.abort();
  }, [currentPersona, primaryDestination, activeEvents]);

  if (authReady && !currentPersona) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-900">Đăng nhập để xem giỏ hàng</h2>
        <p className="text-xs text-slate-500">Giỏ hàng được lưu theo tài khoản của bạn.</p>
        <button
          onClick={() => openLoginModal()}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-xs transition-colors"
        >
          Đăng nhập
        </button>
      </div>
    );
  }

  if (!cart) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 flex justify-center text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" aria-label="Đang tải giỏ hàng" />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center space-y-6">
        <div className="w-16 h-16 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto">
          <ShoppingBag className="w-8 h-8" />
        </div>
        <div className="space-y-1">
          <h2 className="text-xl font-bold text-slate-900">Giỏ hàng của bạn đang trống</h2>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Chưa có dịch vụ nào được thêm vào giỏ. Hãy bắt đầu chọn khách sạn, chuyến bay hoặc vé vui chơi!
          </p>
        </div>
        <div className="flex justify-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-xs transition-colors"
          >
            Khám phá gợi ý trang chủ
          </button>
          <button
            onClick={() => navigate('/assistant')}
            className="px-5 py-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 font-bold text-xs rounded-xl transition-colors flex items-center gap-1.5"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Lên kế hoạch cùng Trợ lý AI
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">
      <div className="flex items-baseline justify-between border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">
          Giỏ hàng của bạn ({cart.itemCount})
        </h1>
        <span className="text-xs text-slate-500">
          Các dịch vụ được gom nhóm theo từng điểm đến
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left: Cart Items by Destination */}
        <div className="lg:col-span-2 space-y-6">
          {Object.entries(itemsByDestination).map(([dest, group]) => (
            <div key={dest} className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-5 py-3.5 bg-slate-50 border-b border-slate-200/80 flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  CHUYẾN {dest.toUpperCase()}
                </h3>
                <span className="text-xs text-slate-500 font-medium">
                  {group.length} dịch vụ
                </span>
              </div>

              <div className="divide-y divide-slate-100 p-2">
                {group.map(item => (
                  <div
                    key={item.cartItemId}
                    data-testid="cart-item"
                    className={`p-3 space-y-3 ${item.product.available ? '' : 'border-2 border-rose-400 rounded-xl bg-rose-50/40'}`}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3.5 min-w-0">
                        <img
                          src={item.product.imageUrl || '/placeholders/hotel.svg'}
                          alt={item.product.name}
                          referrerPolicy="no-referrer"
                          className="w-16 h-16 rounded-lg object-cover bg-slate-100 shrink-0"
                        />
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 mb-1">
                            <TaxonomyBadge taxonomy={item.product.taxonomy as Taxonomy} size="sm" />
                            <span className="text-[11px] text-slate-400 font-medium">
                              {item.product.destination}
                            </span>
                          </div>
                          <h4 className="text-xs sm:text-sm font-bold text-slate-900 truncate">
                            {item.product.name}
                          </h4>
                          <div className="text-[11px] text-slate-500 mt-0.5" data-testid="cart-item-summary">{itemSummary(item)}</div>
                          {!item.product.available && (
                            <div className="text-[11px] text-rose-600 font-semibold mt-0.5">
                              Hết chỗ — xoá mục này để tiếp tục đặt chỗ
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex flex-col items-end gap-1.5 shrink-0">
                        <span className="text-sm font-bold text-blue-900 font-mono">
                          {formatVnd(item.lineTotal)}
                        </span>
                        <div className="flex items-center gap-3">
                          {item.product.available && item.product.unitPrice != null && (
                            <button
                              onClick={() => setEditing(editing === item.cartItemId ? null : item.cartItemId)}
                              aria-expanded={editing === item.cartItemId}
                              aria-label={`Sửa số khách của ${item.product.name}`}
                              className="text-xs text-slate-400 hover:text-blue-600 flex items-center gap-1 transition-colors"
                            >
                              <Pencil className="w-3.5 h-3.5" aria-hidden="true" />
                              <span>Sửa</span>
                            </button>
                          )}
                          <button
                            onClick={() => void removeFromCart(item.cartItemId)}
                            className="text-xs text-slate-400 hover:text-rose-600 flex items-center gap-1 transition-colors"
                            title="Xóa mục này"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            <span>Xóa</span>
                          </button>
                        </div>
                      </div>
                    </div>
                    <FareLines fares={item.fares ?? []} />
                    {editing === item.cartItemId && <GuestEditor key={item.cartItemId} item={item} onClose={() => setEditing(null)} />}
                  </div>
                ))}
              </div>
            </div>
          ))}

          {/* Thường được đặt cùng (§4.4) */}
          {recs && recs.recommendations.length > 0 && (
            <div className="pt-4 space-y-3">
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Thường được đặt cùng chuyến {primaryDestination}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {recs.recommendations.slice(0, 2).map(rec => (
                  <ProductCard
                    key={rec.product.id}
                    product={rec.product}
                    variant="compact"
                    because={rec.because}
                    onQuickAdd={(p) => void addToCart(p, 1)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Sticky Summary Box — mọi con số lấy từ CartResponse */}
        <div className="sticky top-20 bg-white p-6 rounded-2xl border border-slate-200 shadow-xl space-y-5">
          <h3 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-3">
            Tóm tắt đơn đặt chỗ
          </h3>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between text-slate-600">
              <span>Tổng số dịch vụ:</span>
              <span className="font-semibold text-slate-800">{cart.itemCount}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Tạm tính:</span>
              <span className="font-mono text-slate-800">{formatVnd(cart.subtotal)}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Thuế và phí:</span>
              <span className="text-emerald-600 font-semibold">Đã bao gồm</span>
            </div>
            <div className="pt-3 border-t border-slate-200 flex justify-between items-baseline">
              <span className="text-sm font-bold text-slate-900">Tổng thanh toán:</span>
              <span className="text-lg font-black text-blue-900 font-mono">{formatVnd(cart.total)}</span>
            </div>
          </div>

          {hasUnavailable && (
            <div className="flex items-start gap-2 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-[11px] text-rose-700">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>Giỏ có dịch vụ đã hết chỗ. Xoá mục đó để tiếp tục.</span>
            </div>
          )}

          <button
            onClick={() => navigate('/checkout')}
            disabled={hasUnavailable}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold text-sm rounded-xl shadow-xs transition-colors flex items-center justify-center gap-2"
          >
            <span>Tiến hành đặt chỗ</span>
            <ArrowRight className="w-4 h-4" />
          </button>

          <div className="text-center text-[11px] text-slate-500 space-y-1">
            <div className="flex items-center justify-center gap-1 text-slate-600 font-medium">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Thanh toán qua Stripe — V-OTA không lưu thông tin thẻ</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
