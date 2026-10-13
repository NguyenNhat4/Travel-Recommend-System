'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { HelpCircle, Search } from 'lucide-react';
import { useTravel } from '../../context/TravelContext';
import { fetchRecommendations } from '../../services/recsys';
import type { ListProductsParams } from '../../services/catalog';
import type { RecommendationResponse } from '../../types/travel';
import { ProductCard } from '../common/ProductCard';
import { GuestRecommendationBanner } from './GuestRecommendationBanner';
import { WhyPopover } from '../common/WhyPopover';
import { NavIcon } from '../layout/nav/NavIcon';
import { VerticalChips } from '../layout/nav/VerticalChips';
import { categoryShortcuts } from '../layout/nav/navConfig';
import { CatalogShelf } from '../../features/catalog/landing/ProductShelf';
import { DestinationTiles } from '../../features/catalog/landing/DestinationTiles';
import { InstantSearchPanel } from '../../features/search/instant/InstantSearchPanel';
import { useInstantSearchBox } from '../../features/search/instant/useInstantSearchBox';

/** Gợi ý cá nhân hóa quá 10 giây thì ẩn khối và hiện dòng "Thử lại" (frontend §6.4 RECOMMENDATION_TIMEOUT_MS). */
const RECOMMENDATION_TIMEOUT_MS = 10000;

const AI_PLACEHOLDERS = [
  'Tìm resort Sota view biển cho gia đình 4 người, ngân sách 10 triệu...',
  'Combo Phú Quốc 3N2Đ vé máy bay + khách sạn + vui chơi VinWonders...',
  'Tư vấn khách sạn Sota Nha Trang gần bãi biển, có bể bơi vô cực...',
  'Gợi ý lịch trình 4N3Đ Đà Nẵng - Hội An nghỉ dưỡng cao cấp...',
];

const AI_CHIPS = ['Resort Sota Nha Trang cho gia đình', 'Combo Phú Quốc 3N2Đ giá tốt', 'Villa ven biển view hoàng hôn'];

/**
 * Tab của khối "Phổ biến" (frontend §4.1 ④): chỉ tab đang chọn gọi API, mỗi tab một request. `Tất cả` nhờ Backend trộn theo
 * nhóm loại (`diversify`, contract 1.27.0) và là kệ duy nhất gắn nhãn loại trên thẻ; `Vé tham quan` gồm cả sân golf
 * (chốt 2026-10-12).
 */
const POPULAR_TABS: Array<{
  id: string;
  label: string;
  params: Pick<ListProductsParams, 'taxonomy' | 'diversify'>;
  showTaxonomy?: boolean;
}> = [
  { id: 'all', label: 'Tất cả', params: { diversify: 'taxonomy' }, showTaxonomy: true },
  { id: 'hotel', label: 'Khách sạn', params: { taxonomy: 'hotel' } },
  { id: 'flight', label: 'Vé máy bay', params: { taxonomy: 'flight' } },
  { id: 'attraction', label: 'Vé tham quan', params: { taxonomy: ['attraction', 'golf'] } },
  { id: 'combo', label: 'Combo', params: { taxonomy: 'combo' } },
];

/** Chữ gõ dần ở ô tìm kiếm AI; người dùng chọn giảm chuyển động thì đứng yên ở câu đầu. */
function useTypewriterPlaceholder(): string {
  const [index, setIndex] = useState(0);
  const [shown, setShown] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [still, setStill] = useState(false);

  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      setStill(true);
      setShown(AI_PLACEHOLDERS[0]);
    }
  }, []);

  useEffect(() => {
    if (still) return;
    const text = AI_PLACEHOLDERS[index];
    let timer: ReturnType<typeof setTimeout>;
    if (!deleting) {
      const typing = shown.length < text.length;
      timer = setTimeout(() => (typing ? setShown(text.slice(0, shown.length + 1)) : setDeleting(true)), typing ? 35 : 2800);
    } else if (shown.length > 0) {
      timer = setTimeout(() => setShown(text.slice(0, shown.length - 1)), 18);
    } else {
      setDeleting(false);
      setIndex((prev) => (prev + 1) % AI_PLACEHOLDERS.length);
      return;
    }
    return () => clearTimeout(timer);
  }, [shown, deleting, index, still]);

  return shown;
}

/**
 * Trang chủ tổng quan (docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md §4): tìm kiếm AI, lối vào bốn danh mục,
 * gợi ý cá nhân hóa (K1/K2), phổ biến theo tab và điểm đến. Các khối dưới màn hình chỉ tải khi cuộn tới.
 */
export const HomeView: React.FC = () => {
  const { currentPersona, activeEvents, navigate, showToast, authReady, openLoginModal } = useTravel();
  const placeholder = useTypewriterPlaceholder();
  const [aiQuery, setAiQuery] = useState('');
  const [popularTab, setPopularTab] = useState(POPULAR_TABS[0]);

  // Gợi ý thật từ GET /recommendations; lỗi hoặc quá hạn thì ẩn khối và hiện dòng "Thử lại" (product.md §4.1.5).
  const [recResponse, setRecResponse] = useState<RecommendationResponse | null>(null);
  const [recsFailed, setRecsFailed] = useState(false);
  const [recsRetry, setRecsRetry] = useState(0);
  const [isLoadingRecs, setIsLoadingRecs] = useState(false);
  const [showSectionWhy, setShowSectionWhy] = useState(false);

  // Chỉ phụ thuộc vào giá trị thật sự đổi kết quả. Đưa cả `currentPersona`/`activeEvents` vào deps thì mỗi lần
  // đối tượng/mảng đổi tham chiếu (nạp lại phiên, `resetClientState` gán `[]` mới) effect huỷ request đang bay.
  const personaId = currentPersona?.id;
  const personaDestination = currentPersona?.activeDestination;
  const eventCount = activeEvents.length;

  useEffect(() => {
    const controller = new AbortController();
    let timedOut = false;

    // Danh tính do BFF gắn từ cookie phiên; đổi tài khoản = đổi phiên nên effect chạy lại. Khách không gọi.
    if (!personaId) {
      setRecResponse(null);
      setRecsFailed(false);
      return () => controller.abort();
    }
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, RECOMMENDATION_TIMEOUT_MS);
    setIsLoadingRecs(true);
    setRecsFailed(false);
    fetchRecommendations({ k: 4, destination: personaDestination, signal: controller.signal })
      .then((data) => setRecResponse(data))
      .catch(() => {
        if (!controller.signal.aborted || timedOut) {
          setRecResponse(null);
          setRecsFailed(true);
        }
      })
      .finally(() => {
        clearTimeout(timer);
        if (!controller.signal.aborted || timedOut) setIsLoadingRecs(false);
      });

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [personaId, personaDestination, eventCount, recsRetry]);

  const strategy = recResponse?.strategy ?? 'popular';
  const destination = recResponse?.destination ?? '';
  const recommendations = recResponse?.recommendations ?? [];
  const excludedVerticals = recResponse?.diagnostics.excludedVerticals ?? [];

  // Gợi ý tức thì khi gõ (FR-SRC-05): chọn điểm đến hoặc từ khoá thì tìm như Enter, chọn sản phẩm thì mở trang chi tiết.
  const { containerRef: instantContainerRef, ...instant } = useInstantSearchBox({
    value: aiQuery,
    onSearch: (query) => {
      showToast(`Đang tìm kiếm: "${query.slice(0, 32)}..."`);
      navigate(`/search?q=${encodeURIComponent(query)}`);
    },
    onOpenProduct: (productId) => navigate(`/product/${encodeURIComponent(productId)}`),
  });

  const submitAi = (event: React.FormEvent) => {
    event.preventDefault();
    instant.search(aiQuery.trim() || placeholder || 'Resort Sota');
  };

  return (
    <div className="flex flex-col bg-[#f8fafc] font-sans text-slate-800 antialiased">
      {/* HERO: tìm kiếm AI là lối vào chính (FR-SRC-01); header nổi (fixed) đè lên phần đầu nên chừa pt-28 */}
      <section className="relative flex min-h-[560px] items-center justify-center px-4 pb-16 pt-28 sm:px-6 lg:min-h-[600px]">
        <div className="absolute inset-0 overflow-hidden bg-slate-800">
          <img
            src="https://images.unsplash.com/photo-1582719508461-905c673771fd?q=80&w=2000&auto=format&fit=crop"
            alt=""
            fetchPriority="high"
            loading="eager"
            decoding="async"
            className="h-full w-full object-cover object-center"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-slate-900/60 via-slate-900/30 to-slate-950/80" />
        </div>

        {/* z-20: panel gợi ý của ô tìm kiếm phải nằm trên dải danh mục (z-10) ngay bên dưới hero. */}
        <div className="relative z-20 mx-auto flex w-full max-w-5xl flex-col items-center gap-6 text-center">
          <VerticalChips activeGroup={null} />
          <div>
            <h1 className="type-hero text-white drop-shadow-md">
              Khám phá kỳ nghỉ tiếp theo
            </h1>
            <p className="type-hero-sub mx-auto mt-3 max-w-2xl text-white/90 drop-shadow">
              Mô tả chuyến đi bằng lời của bạn, Sota tìm dịch vụ phù hợp
            </p>
          </div>

          <div className="w-full max-w-4xl space-y-3">
            <div ref={instantContainerRef} className="relative">
            <form
              onSubmit={submitAi}
              role="search"
              className="glass-sheet flex items-center justify-between gap-2 rounded-2xl p-2 shadow-2xl ring-2 ring-brand-500/20 sm:rounded-full sm:p-2.5"
            >
              <input
                type="text"
                value={aiQuery}
                onChange={(e) => { setAiQuery(e.target.value); instant.onType(); }}
                {...instant.inputProps}
                aria-label="Mô tả chuyến đi bạn muốn"
                placeholder={placeholder || 'Hỏi AI: Tìm resort Sota view biển cho gia đình 4 người...'}
                className="min-w-0 flex-1 truncate bg-transparent pl-3.5 text-base font-medium text-slate-800 outline-none placeholder:text-slate-500 sm:pl-4"
              />
              <button
                type="submit"
                aria-label="Tìm kiếm"
                className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full bg-brand-600 text-white shadow-md transition hover:bg-brand-700 active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
              >
                <Search className="h-5 w-5" aria-hidden="true" />
              </button>
            </form>
            {instant.open && <InstantSearchPanel {...instant.panel} />}
            </div>

            <div className="flex flex-wrap items-center justify-center gap-2 text-[13px]">
              <span className="font-medium text-white/80 drop-shadow">Gợi ý câu hỏi:</span>
              {AI_CHIPS.map((chip) => (
                <Link
                  key={chip}
                  href={`/search?q=${encodeURIComponent(chip)}`}
                  onClick={() => instant.remember(chip)}
                  className="inline-flex min-h-10 items-center rounded-full border border-white/25 bg-white/20 px-4 font-medium text-white backdrop-blur-md transition-colors duration-200 hover:bg-white/35 focus-visible:outline-2 focus-visible:outline-white"
                >
                  {chip}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </section>

      <main className="flex-grow">
        {/* LỐI VÀO BỐN DANH MỤC (Category Nav của PRD) */}
        <section aria-label="Danh mục dịch vụ" className="relative z-10 mx-auto -mt-8 w-full max-w-7xl px-4 sm:px-6 lg:px-8">
          <ul className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {categoryShortcuts().map((shortcut) => (
              <li key={shortcut.id}>
                <Link
                  href={shortcut.href}
                  className="flex h-full items-center gap-3 rounded-2xl border border-slate-100 bg-white p-4 shadow-lg transition hover:-translate-y-0.5 hover:shadow-xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
                >
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600">
                    <NavIcon name={shortcut.icon} className="h-5 w-5" />
                  </span>
                  <span className="min-w-0">
                    <span className="block font-display text-[15px] leading-5 text-slate-900">{shortcut.label}</span>
                    <span className="block truncate text-[13px] leading-[18px] text-slate-500">{shortcut.summary}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        {/* ① GỢI Ý CÁ NHÂN HÓA (đã đăng nhập): AC-REC-01, AC-REC-02 */}
        {authReady && !currentPersona && (
          <GuestRecommendationBanner onLogin={() => openLoginModal()} onRegister={() => navigate('/register')} />
        )}
        {currentPersona && recsFailed && (
          <section className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
            <p className="text-xs text-slate-500">
              Chưa tải được gợi ý cho bạn ·{' '}
              <button onClick={() => setRecsRetry((n) => n + 1)} className="cursor-pointer font-semibold text-brand-600 hover:underline">
                Thử lại
              </button>
            </p>
          </section>
        )}
        {currentPersona && recommendations.length > 0 && (
          <section aria-label="Gợi ý cho bạn" className="mx-auto max-w-7xl px-4 pb-4 pt-8 sm:px-6 lg:px-8">
            <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-sm">
              <div className="flex flex-col items-start justify-between gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-center">
                <h2 className="type-title text-slate-900">Gợi ý</h2>
                <button
                  onClick={() => setShowSectionWhy(true)}
                  className="inline-flex cursor-pointer items-center gap-1 rounded-xl border border-brand-200 bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-700 transition-colors hover:bg-brand-100"
                >
                  <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Vì sao có gợi ý này?</span>
                </button>
              </div>

              <div className={`mt-5 grid grid-cols-1 gap-4 transition-opacity duration-200 sm:grid-cols-2 lg:grid-cols-4 ${isLoadingRecs ? 'pointer-events-none opacity-60' : 'opacity-100'}`}>
                {recommendations.slice(0, 4).map((rec) => (
                  <ProductCard
                    key={rec.product.id}
                    product={rec.product}
                    variant="grid"
                    because={rec.because}
                    strategy={strategy}
                    excludedVerticals={excludedVerticals}
                    score={rec.score}
                    rank={rec.rank}
                  />
                ))}
              </div>

              <WhyPopover
                isOpen={showSectionWhy}
                onClose={() => setShowSectionWhy(false)}
                targetProductName={`Toàn bộ danh mục chuyến ${destination}`}
                becauseItems={recommendations[0]?.because || []}
                strategy={strategy}
                excludedVerticals={excludedVerticals}
                destination={destination}
              />
            </div>
          </section>
        )}

        {/* ④ PHỔ BIẾN THEO TAB: luôn render, chỉ tab đang chọn gọi API */}
        <div className="pt-4">
          <div className="mx-auto w-full max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
            <div role="tablist" aria-label="Danh mục phổ biến" className="no-scrollbar flex gap-2 overflow-x-auto">
              {POPULAR_TABS.map((tab) => {
                const selected = tab.id === popularTab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    onClick={() => setPopularTab(tab)}
                    className={`h-11 shrink-0 cursor-pointer rounded-full border px-5 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 ${
                      selected ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
          <CatalogShelf
            key={popularTab.id}
            title="Phổ biến tại các điểm đến Việt Nam"
            params={{ ...popularTab.params, sort: 'popular', availableOnly: true, limit: 8 }}
            showTaxonomy={popularTab.showTaxonomy}
            empty={{ text: 'Chưa có dịch vụ nào trong danh mục này.' }}
          />
        </div>

        {/* BẠN MUỐN ĐI ĐÂU?: điểm đến từ API, mở trang khách sạn của điểm đến */}
        <DestinationTiles route="/hotels" />

        {/* NGƯỜI BẠN ĐỒNG HÀNH ĐÁNG TIN CẬY */}
        <section className="relative py-20 overflow-hidden mt-6">
          {/* Panoramic Background with Light Gradient Overlay */}
          <div className="absolute inset-0 z-0">
            <img
              src="https://images.unsplash.com/photo-1506929562872-bb421503ef21?q=80&w=2000&auto=format&fit=crop"
              alt="Coastal paradise panoramic"
              className="w-full h-full object-cover filter brightness-[0.85]"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-white/90 via-transparent to-white/70"></div>
          </div>

          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="type-title mb-8 text-slate-900">
              Người bạn đồng hành đáng tin cậy
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Trust Badge 1 */}
              <div className="glass-card rounded-2xl p-6 border border-white/70 shadow-lg hover:shadow-2xl transition duration-300 flex flex-col items-start">
                <div className="w-12 h-12 rounded-xl bg-brand-50 border border-brand-100/80 flex items-center justify-center mb-4 shadow-md shadow-brand-500/10 overflow-hidden">
                  <img
                    src="/trust_badge_ecosystem.webp"
                    alt="Hệ sinh thái du lịch & giải trí toàn diện"
                    className="w-10 h-10 object-contain drop-shadow-xs"
                  />
                </div>
                <h3 className="text-base font-bold text-slate-900 leading-snug">
                  Hệ sinh thái du lịch & giải trí toàn diện
                </h3>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  Tích hợp đồng bộ từ khách sạn, vui chơi giải trí VinWonders, ẩm thực tới di chuyển trong cùng một tài khoản.
                </p>
              </div>

              {/* Trust Badge 2 */}
              <div className="glass-card rounded-2xl p-6 border border-white/70 shadow-lg hover:shadow-2xl transition duration-300 flex flex-col items-start">
                <div className="w-12 h-12 rounded-xl bg-brand-50 border border-brand-100/80 flex items-center justify-center mb-4 shadow-md shadow-brand-500/10 overflow-hidden">
                  <img
                    src="/trust_badge_booking.webp"
                    alt="Trải nghiệm đặt dịch vụ liền mạch"
                    className="w-10 h-10 object-contain drop-shadow-xs"
                  />
                </div>
                <h3 className="text-base font-bold text-slate-900 leading-snug">
                  Trải nghiệm đặt dịch vụ liền mạch
                </h3>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  Xác nhận đặt chỗ theo thời gian thực, lưu trữ vé điện tử và mã QR bảo mật ngay trên ứng dụng mà không cần in giấy.
                </p>
              </div>

              {/* Trust Badge 3 */}
              <div className="glass-card rounded-2xl p-6 border border-white/70 shadow-lg hover:shadow-2xl transition duration-300 flex flex-col items-start">
                <div className="w-12 h-12 rounded-xl bg-brand-50 border border-brand-100/80 flex items-center justify-center mb-4 shadow-md shadow-brand-500/10 overflow-hidden">
                  <img
                    src="/trust_badge_ai_assistant.webp"
                    alt="Trợ lý AI đồng hành du lịch"
                    className="w-10 h-10 object-contain drop-shadow-xs"
                  />
                </div>
                <h3 className="text-base font-bold text-slate-900 leading-snug">
                  Trợ lý AI đồng hành du lịch
                </h3>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  Lên kế hoạch thông minh theo sở thích và ngân sách, tối ưu hóa thời gian và tuyến điểm di chuyển cho cả gia đình.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};
