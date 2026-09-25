'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useTravel } from '../../context/TravelContext';
import * as bookingApi from '../../services/booking';
import type { ApiCartItem, CheckoutItemDetail } from '../../services/booking';
import { ApiError } from '../../services/http';
import type { Taxonomy } from '../../types/travel';
import { TaxonomyBadge } from '../common/TaxonomyBadge';
import { formatDateTimeVn, formatVnd } from '../confirmation/bookingLabels';
import { AlertTriangle, CreditCard, Edit3, Loader2, Lock, RefreshCw, Timer } from 'lucide-react';

const PHONE_PATTERN = /^0[0-9]{9}$/;

/** Phương thức thanh toán. Hiện chỉ Stripe; mục khác hiển thị vô hiệu hoá, nhãn "Sắp có" (user-flow §3.3). */
const PAYMENT_METHODS = [
  { id: 'stripe', label: 'Stripe — Thẻ thanh toán (chế độ test)', enabled: true },
  { id: 'ewallet', label: 'Ví điện tử', enabled: false },
  { id: 'bank_transfer', label: 'Chuyển khoản ngân hàng', enabled: false },
] as const;
type PaymentMethod = (typeof PAYMENT_METHODS)[number]['id'];

type Banner =
  | { kind: 'price'; cartItemId: string | null; name: string; oldPrice: number; newPrice: number }
  | { kind: 'unavailable' | 'date'; name: string; text: string }
  | { kind: 'error'; text: string; retryable: boolean; requestId: string | null };

interface PendingHold {
  referenceCode: string;
  holdExpiresAt: string | null;
}

interface ItemForm {
  guestNames: string[];
  specialRequest: string;
}

/** Quy tắc form → itemDetails (docs/spec/hop-dong-tich-hop-frontend.md §4.5). */
function guestSlots(item: ApiCartItem): number {
  if (item.product.taxonomy === 'hotel') return 1;
  if (item.product.taxonomy === 'flight') return item.quantity;
  return 0;
}

export const CheckoutView: React.FC = () => {
  const { cart, currentPersona, authReady, navigate, refreshCart, updateCartItem, rememberBooking, openLoginModal } =
    useTravel();
  const items = useMemo(() => cart?.items ?? [], [cart]);

  const [fullName, setFullName] = useState(currentPersona?.name ?? '');
  const [phone, setPhone] = useState('');
  const [itemForms, setItemForms] = useState<Record<string, ItemForm>>({});
  const [method, setMethod] = useState<PaymentMethod>('stripe');
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [banner, setBanner] = useState<Banner | null>(null);
  const [pendingHold, setPendingHold] = useState<PendingHold | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const email = currentPersona?.email ?? '';

  useEffect(() => {
    if (currentPersona && !fullName) setFullName(currentPersona.name);
  }, [currentPersona, fullName]);

  // Checkout luôn đọc giỏ mới nhất từ server; giỏ rỗng thì về /cart (§4.5).
  useEffect(() => {
    if (currentPersona) void refreshCart();
  }, [currentPersona, refreshCart]);
  useEffect(() => {
    if (cart && cart.items.length === 0 && !submitting) navigate('/cart');
  }, [cart, submitting, navigate]);

  const formFor = (item: ApiCartItem): ItemForm => {
    const saved = itemForms[item.cartItemId];
    const slots = guestSlots(item);
    const guestNames = Array.from({ length: slots }, (_, i) => saved?.guestNames[i] ?? (i === 0 ? fullName : ''));
    return { guestNames, specialRequest: saved?.specialRequest ?? '' };
  };

  const setItemForm = (item: ApiCartItem, patch: Partial<ItemForm>) =>
    setItemForms((prev) => ({ ...prev, [item.cartItemId]: { ...formFor(item), ...patch } }));

  const contactValid = fullName.trim().length > 0 && fullName.trim().length <= 100 && PHONE_PATTERN.test(phone)
    && email.length > 0;
  const guestsValid = items.every((item) => formFor(item).guestNames.every((name) => name.trim().length > 0));
  const hasUnavailable = items.some((item) => !item.product.available);
  const canPay = contactValid && guestsValid && termsAgreed && method === 'stripe' && !hasUnavailable && !submitting;

  const itemName = (productId?: string) =>
    items.find((item) => item.product.productId === productId)?.product.name ?? 'Một dịch vụ';

  const showError = (error: unknown) => {
    if (!(error instanceof ApiError)) {
      setBanner({ kind: 'error', text: 'Có lỗi xảy ra. Vui lòng thử lại.', retryable: true, requestId: null });
      return;
    }
    const details = error.details ?? {};
    switch (error.code) {
      case 'CART_EMPTY':
        navigate('/cart');
        return;
      case 'BOOKING_PENDING_PAYMENT':
        setPendingHold({ referenceCode: details.referenceCode, holdExpiresAt: details.holdExpiresAt ?? null });
        return;
      case 'PRICE_CHANGED': {
        const item = items.find((i) => i.product.productId === details.productId);
        setBanner({ kind: 'price', cartItemId: item?.cartItemId ?? null, name: itemName(details.productId),
          oldPrice: details.oldPrice, newPrice: details.newPrice });
        return;
      }
      case 'PRODUCT_UNAVAILABLE':
        setBanner({ kind: 'unavailable', name: itemName(details.productId),
          text: `${itemName(details.productId)} vừa hết chỗ.` });
        return;
      case 'DATE_OUT_OF_RANGE':
        setBanner({ kind: 'date', name: itemName(details.productId), text:
          `Ngày sử dụng của ${itemName(details.productId)} nằm ngoài thời gian mở bán`
          + (details.availableFrom ? ` (${details.availableFrom} – ${details.availableTo}).` : '.') });
        return;
      case 'VALIDATION_ERROR': {
        const fields = Array.isArray(details.fields) ? details.fields : [];
        setFieldErrors(Object.fromEntries(fields.map((f: any) => [String(f.field ?? ''), String(f.message ?? 'Không hợp lệ')])));
        setBanner({ kind: 'error', text: error.message, retryable: false, requestId: error.requestId });
        return;
      }
      case 'PAYMENT_PROVIDER_UNAVAILABLE':
        setBanner({ kind: 'error', text: 'Cổng thanh toán tạm thời không phản hồi. Vui lòng thử lại.', retryable: true,
          requestId: error.requestId });
        return;
      default:
        setBanner({ kind: 'error', text: error.code === 'NETWORK_ERROR' ? 'Mất kết nối. Vui lòng thử lại.' : error.message,
          retryable: error.retryable, requestId: error.requestId });
    }
  };

  const submit = async () => {
    if (!canPay) return;
    setSubmitting(true);
    setBanner(null);
    setFieldErrors({});
    const itemDetails: CheckoutItemDetail[] = items.map((item) => {
      const form = formFor(item);
      return {
        cartItemId: item.cartItemId,
        ...(form.guestNames.length ? { guestNames: form.guestNames.map((n) => n.trim()) } : {}),
        ...(form.specialRequest.trim() ? { specialRequest: form.specialRequest.trim() } : {}),
      };
    });
    try {
      const booking = await bookingApi.createBooking({
        contact: { fullName: fullName.trim(), email, phone }, itemDetails,
      });
      rememberBooking(booking);
      // Giữ nút ở trạng thái đang xử lý trong lúc trình duyệt rời sang trang Stripe.
      if (booking.payment?.checkoutUrl) bookingApi.redirectToCheckout(booking.payment.checkoutUrl);
      else navigate(`/booking/${booking.referenceCode}`);
    } catch (error) {
      showError(error);
      setSubmitting(false);
    }
  };

  const acceptNewPrice = async () => {
    if (banner?.kind !== 'price') return;
    const item = items.find((i) => i.cartItemId === banner.cartItemId);
    // PATCH ghi lại giá snapshot = giá hiện tại: khách đã thấy giá mới, lần bấm sau không còn PRICE_CHANGED.
    if (item) await updateCartItem(item.cartItemId, { quantity: item.quantity });
    else await refreshCart();
    setBanner(null);
  };

  const continuePending = async () => {
    if (!pendingHold) return;
    try {
      const held = await bookingApi.getBooking(pendingHold.referenceCode);
      rememberBooking(held);
      if (held.status === 'PENDING_PAYMENT' && held.payment?.checkoutUrl) {
        bookingApi.redirectToCheckout(held.payment.checkoutUrl);
        return;
      }
    } catch {
      // Đọc đơn lỗi thì vẫn mở trang đơn để khách xem trạng thái.
    }
    navigate(`/booking/${pendingHold.referenceCode}`);
  };

  const cancelPendingAndRetry = async () => {
    if (!pendingHold) return;
    try {
      rememberBooking(await bookingApi.cancelBooking(pendingHold.referenceCode, 'Đặt lại từ giỏ'));
      setPendingHold(null);
      await submit();
    } catch (error) {
      setPendingHold(null);
      showError(error);
    }
  };

  if (authReady && !currentPersona) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-900">Đăng nhập để thanh toán</h2>
        <button
          onClick={() => openLoginModal()}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl"
        >
          Đăng nhập
        </button>
      </div>
    );
  }

  if (!cart || items.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 flex justify-center text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" aria-label="Đang tải giỏ hàng" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        <form
          className="lg:col-span-2 space-y-6"
          onSubmit={(e) => { e.preventDefault(); void submit(); }}
          aria-label="Thanh toán"
        >
          {/* 1. Thông tin liên hệ */}
          <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <SectionTitle step={1} title="THÔNG TIN LIÊN HỆ" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Họ và tên người đặt *" error={fieldErrors['contact.fullName']}>
                <input
                  type="text" required maxLength={100} value={fullName} onChange={(e) => setFullName(e.target.value)}
                  aria-label="Họ và tên"
                  className="w-full px-3 py-2 text-xs sm:text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-hidden"
                />
              </Field>
              <Field
                label="Số điện thoại *"
                error={fieldErrors['contact.phone'] || (phone && !PHONE_PATTERN.test(phone)
                  ? 'Số điện thoại gồm 10 chữ số, bắt đầu bằng 0' : undefined)}
              >
                <input
                  type="tel" required inputMode="numeric" value={phone} placeholder="0912345678"
                  onChange={(e) => setPhone(e.target.value.replace(/\s+/g, ''))} aria-label="Số điện thoại"
                  className="w-full px-3 py-2 text-xs sm:text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-hidden"
                />
              </Field>
              <div className="sm:col-span-2">
                <Field label="Email nhận thông tin (theo tài khoản)" error={fieldErrors['contact.email']}>
                  <input
                    type="email" disabled value={email} aria-label="Email"
                    className="w-full px-3 py-2 text-xs sm:text-sm bg-slate-100 border border-slate-300 rounded-lg text-slate-500 cursor-not-allowed"
                  />
                </Field>
              </div>
            </div>
          </section>

          {/* 2. Thông tin từng dịch vụ */}
          <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <SectionTitle step={2} title="THÔNG TIN TỪNG DỊCH VỤ" />
            <div className="space-y-4">
              {items.map((item, index) => {
                const form = formFor(item);
                return (
                  <div key={item.cartItemId} className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <TaxonomyBadge taxonomy={item.product.taxonomy as Taxonomy} size="sm" />
                        <span className="font-bold text-slate-800">{item.product.name}</span>
                      </div>
                      <span className="text-slate-500">Mục #{index + 1}</span>
                    </div>
                    {form.guestNames.map((name, i) => (
                      <input
                        key={i} type="text" value={name} required
                        aria-label={item.product.taxonomy === 'hotel' ? 'Tên khách nhận phòng' : `Hành khách ${i + 1}`}
                        placeholder={item.product.taxonomy === 'hotel' ? 'Tên khách nhận phòng' : `Họ tên hành khách ${i + 1}`}
                        onChange={(e) => {
                          const guestNames = [...form.guestNames];
                          guestNames[i] = e.target.value;
                          setItemForm(item, { guestNames });
                        }}
                        className="w-full px-3 py-1.5 border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500"
                      />
                    ))}
                    {form.guestNames.length === 0 && (
                      <div className="text-[11px] text-slate-600">Vé điện tử dùng cho ngày <strong>{item.usingDate}</strong></div>
                    )}
                    <textarea
                      rows={1} maxLength={500} value={form.specialRequest}
                      onChange={(e) => setItemForm(item, { specialRequest: e.target.value })}
                      placeholder="Yêu cầu đặc biệt (không bắt buộc)"
                      className="w-full px-3 py-1.5 border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                );
              })}
            </div>
          </section>

          {/* 3. Phương thức thanh toán */}
          <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <SectionTitle step={3} title="PHƯƠNG THỨC THANH TOÁN" />
            <div className="space-y-2" role="radiogroup" aria-label="Phương thức thanh toán">
              {PAYMENT_METHODS.map((option) => (
                <label
                  key={option.id}
                  className={`flex items-center justify-between gap-3 p-3 rounded-xl border text-xs ${
                    option.enabled ? 'border-blue-300 bg-blue-50/40 cursor-pointer' : 'border-slate-200 text-slate-400 cursor-not-allowed'}`}
                >
                  <span className="flex items-center gap-2">
                    <input
                      type="radio" name="payment-method" value={option.id} disabled={!option.enabled}
                      checked={method === option.id} onChange={() => setMethod(option.id)}
                    />
                    <CreditCard className="w-4 h-4" />
                    {option.label}
                  </span>
                  {!option.enabled && (
                    <span className="px-1.5 py-0.5 rounded-md bg-slate-100 text-[10px] font-semibold">Sắp có</span>
                  )}
                </label>
              ))}
            </div>
            <p className="text-[11px] text-slate-500 flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5" />
              Bạn nhập thẻ trên trang do Stripe host; V-OTA không nhận và không lưu số thẻ. Chế độ test: dùng thẻ
              4242 4242 4242 4242.
            </p>
          </section>

          {/* 4. Xác nhận */}
          <section className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <label className="flex items-start gap-3 text-xs text-slate-700 cursor-pointer p-3 bg-slate-50 rounded-xl border border-slate-200">
              <input
                type="checkbox" checked={termsAgreed} onChange={(e) => setTermsAgreed(e.target.checked)}
                className="mt-0.5 rounded border-slate-300 text-blue-600 w-4 h-4"
              />
              <span>
                Tôi đồng ý với <strong>Điều khoản dịch vụ</strong> và <strong>Chính sách huỷ</strong>: hoàn 100% nếu huỷ
                trước 00:00 ngày liền trước ngày sử dụng sớm nhất.
              </span>
            </label>

            {banner && <BannerView banner={banner} onAcceptPrice={acceptNewPrice} onRetry={submit} onBack={() => navigate('/cart')} />}

            <button
              type="submit"
              disabled={!canPay}
              className="w-full py-3.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold text-sm sm:text-base rounded-xl shadow-md transition-all flex items-center justify-center gap-2"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Đang giữ chỗ và mở trang thanh toán...</span>
                </>
              ) : (
                <span>Thanh toán {formatVnd(cart.total)}</span>
              )}
            </button>
            <p className="text-[11px] text-slate-500 text-center flex items-center justify-center gap-1">
              <Timer className="w-3.5 h-3.5" />
              Giữ chỗ 30 phút sau khi bấm Thanh toán. Bạn sẽ được chuyển sang Stripe.
            </p>
          </section>
        </form>

        {/* Tóm tắt đơn — số tiền lấy từ CartResponse */}
        <aside className="sticky top-20 bg-white p-6 rounded-2xl border border-slate-200 shadow-xl space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900">Đơn đặt của bạn ({cart.itemCount})</h3>
            <button onClick={() => navigate('/cart')} className="text-xs text-blue-600 hover:underline flex items-center gap-1">
              <Edit3 className="w-3 h-3" />
              Sửa giỏ hàng
            </button>
          </div>
          <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto pr-1">
            {items.map((item) => (
              <div key={item.cartItemId} className="py-2 flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <h5 className={`text-xs font-bold truncate ${item.product.available ? 'text-slate-900' : 'text-rose-600'}`}>
                    {item.product.name}
                  </h5>
                  <div className="text-[10px] text-slate-500">
                    {item.usingDate} · {item.quantity} {item.product.taxonomy === 'hotel' ? `phòng · ${item.nights ?? 1} đêm` : 'khách'}
                  </div>
                </div>
                <span className="text-xs font-bold text-slate-800 font-mono">{formatVnd(item.lineTotal)}</span>
              </div>
            ))}
          </div>
          <div className="pt-3 border-t border-slate-200 flex justify-between items-baseline">
            <span className="text-sm font-bold text-slate-900">Tổng thanh toán:</span>
            <span className="text-base font-black text-blue-900 font-mono">{formatVnd(cart.total)}</span>
          </div>
        </aside>
      </div>

      {pendingHold && (
        <div role="dialog" aria-modal="true" aria-labelledby="pending-hold-title"
          className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 id="pending-hold-title" className="text-base font-bold text-slate-900">Bạn đang có một đơn chờ thanh toán</h3>
            <p className="text-xs text-slate-600">
              Đơn <strong className="font-mono">{pendingHold.referenceCode}</strong>
              {pendingHold.holdExpiresAt ? <> đang được giữ đến {formatDateTimeVn(pendingHold.holdExpiresAt)}</> : null}.
              Mỗi tài khoản chỉ giữ một đơn cùng lúc.
            </p>
            <div className="flex flex-col gap-2">
              <button onClick={() => void continuePending()}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl">
                Tiếp tục thanh toán đơn đó
              </button>
              <button onClick={() => void cancelPendingAndRetry()}
                className="w-full py-2.5 bg-white border border-rose-300 text-rose-700 hover:bg-rose-50 text-xs font-bold rounded-xl">
                Huỷ đơn đó và đặt lại từ giỏ
              </button>
              <button onClick={() => setPendingHold(null)} className="w-full py-2 text-xs text-slate-500 hover:underline">
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const SectionTitle: React.FC<{ step: number; title: string }> = ({ step, title }) => (
  <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
    <span className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center">{step}</span>
    <h3 className="text-sm font-bold text-slate-900">{title}</h3>
  </div>
);

const Field: React.FC<{ label: string; error?: string; children: React.ReactNode }> = ({ label, error, children }) => (
  <div>
    <label className="block text-xs font-semibold text-slate-700 mb-1">{label}</label>
    {children}
    {error && <p className="text-[11px] text-rose-600 mt-1">{error}</p>}
  </div>
);

const BannerView: React.FC<{
  banner: Banner; onAcceptPrice: () => void; onRetry: () => void; onBack: () => void;
}> = ({ banner, onAcceptPrice, onRetry, onBack }) => (
  <div role="alert" className="flex items-start gap-2 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800">
    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
    <div className="space-y-2 flex-1">
      {banner.kind === 'price' && (
        <>
          <p>Giá {banner.name} đã đổi từ {formatVnd(banner.oldPrice)} thành {formatVnd(banner.newPrice)}.</p>
          <button type="button" onClick={onAcceptPrice} className="font-bold underline">Cập nhật và tiếp tục</button>
        </>
      )}
      {(banner.kind === 'unavailable' || banner.kind === 'date') && (
        <>
          <p>{banner.text}</p>
          <button type="button" onClick={onBack} className="font-bold underline">Quay lại giỏ</button>
        </>
      )}
      {banner.kind === 'error' && (
        <>
          <p>{banner.text}</p>
          {banner.retryable && (
            <button type="button" onClick={onRetry} className="font-bold underline flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> Thử lại
            </button>
          )}
          {banner.requestId && <p className="text-[10px] text-rose-500 font-mono">Mã yêu cầu: {banner.requestId}</p>}
        </>
      )}
    </div>
  </div>
);
