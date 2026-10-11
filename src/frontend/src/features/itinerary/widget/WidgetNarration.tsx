import React from 'react';
import { AssistantText, parseAssistantText } from '../../../components/assistant/inlineBold';
import { ProductCard } from '../../../components/common/ProductCard';
import type { ItineraryFlightItem, Product } from '../../../types/travel';
import { isFreeToVisit } from './widgetPlan';
import { WidgetFlightCard } from './WidgetFlightCard';
import { WidgetFareDays, isFareFlight } from './WidgetFareDays';
import type { CartAddState } from './useWidgetCart';

export type NarrationBlock =
  | { kind: 'text'; text: string }
  | { kind: 'card'; productId: string }
  | { kind: 'slot' }
  /** Hàng ô ngày–giá của lượt hỏi giá vé; `productId` là chuyến được nhắc đầu tiên (ô đầu). */
  | { kind: 'fares'; productId: string };

const HEADING = /^\*\*[^*]+\*\*$/;

/**
 * Tách lời diễn giải thành đoạn chữ và thẻ (PRD user-flow.md §4.2): mỗi sản phẩm `isKnown` có một thẻ ngay sau dòng
 * đầu tiên nhắc `[Tên](product:id)`, các lần nhắc sau chỉ còn link. Dòng trống ngay sau thẻ bỏ đi vì thẻ đã tách đoạn.
 *
 * `slotIds` (khách sạn của hàng thẻ "Phương án khác", AC-AGT-04 chốt 2026-10-08): mục chứa dòng đầu tiên nhắc một trong
 * các khách sạn này là mục "Nơi nghỉ"; mọi dòng nhắc chúng trong mục đó bỏ đi, thay bằng đúng một khối `slot` ở chỗ dòng
 * đầu. Các mục khác (ngày) giữ nguyên chữ, và các khách sạn này không có thẻ gọn.
 *
 * `fareIds` (chuyến bay của lượt hỏi giá vé, contract 1.25.0): không có thẻ riêng; cả nhóm thành đúng một khối `fares`
 * ngay sau dòng đầu tiên nhắc một trong các chuyến này.
 */
export function narrationBlocks(
  text: string,
  isKnown: (productId: string) => boolean,
  slotIds: ReadonlySet<string> = new Set(),
  fareIds: ReadonlySet<string> = new Set(),
): NarrationBlock[] {
  const blocks: NarrationBlock[] = [];
  const shown = new Set<string>();
  let faresPlaced = false;
  let buffer: string[] = [];
  let slot: 'before' | 'inside' | 'after' = 'before';
  const flush = () => {
    if (buffer.length) blocks.push({ kind: 'text', text: buffer.join('\n') });
    buffer = [];
  };
  for (const line of text.split('\n')) {
    const parts = parseAssistantText(line);
    if (slot === 'inside' && HEADING.test(line.trim())) slot = 'after';
    if (slot !== 'after' && parts.some((part) => part.kind === 'product' && slotIds.has(part.productId))) {
      if (slot === 'before') {
        flush();
        blocks.push({ kind: 'slot' });
        slot = 'inside';
      }
      continue;
    }
    if (!buffer.length && blocks[blocks.length - 1]?.kind !== 'text' && blocks.length && !line.trim()) continue;
    buffer.push(line);
    const fresh: NarrationBlock[] = [];
    for (const part of parts) {
      if (part.kind !== 'product' || shown.has(part.productId) || slotIds.has(part.productId) || !isKnown(part.productId)) continue;
      shown.add(part.productId);
      if (!fareIds.has(part.productId)) fresh.push({ kind: 'card', productId: part.productId });
      else if (!faresPlaced) {
        faresPlaced = true;
        fresh.push({ kind: 'fares', productId: part.productId });
      }
    }
    if (!fresh.length) continue;
    flush();
    blocks.push(...fresh);
  }
  flush();
  return blocks;
}

interface WidgetNarrationProps {
  text: string;
  /** Sản phẩm của chính response (`narrationProducts`); thẻ chỉ dựng từ đây, không từ chữ của LLM. */
  products: Record<string, Product>;
  /** Bấm thẻ (hoặc tên của sản phẩm không có thẻ): mở panel chi tiết. */
  onOpen: (productId: string) => void;
  /** Sản phẩm đặt được của lịch trình (`cartItems`); chỉ những thẻ này có nút "Thêm". */
  quickAddIds?: ReadonlySet<string>;
  onQuickAdd?: (productId: string) => void;
  cartAddStates?: Record<string, CartAddState>;
  /**
   * Hàng thẻ "Phương án khác" (AC-AGT-04, chốt 2026-10-08): là nội dung của mục "Nơi nghỉ", thay dòng chữ và thẻ gọn của
   * các khách sạn `ids`. Lời diễn giải không nhắc khách sạn nào trong `ids` thì hàng thẻ nằm cuối bong bóng.
   */
  stays?: { ids: ReadonlySet<string>; node: React.ReactNode };
  /** Vé máy bay của lịch: sản phẩm là vé thì dùng thẻ vé (giờ đi/đến, chặng, giá × số khách) thay thẻ gọn. */
  flights?: ItineraryFlightItem[];
  /** "Đặt ngay" của vé; chỉ vé có trong `cartItems` của lịch mới có nút. */
  onBookNow?: (productId: string) => void;
  bookableIds?: ReadonlySet<string>;
  /** Bấm một ô ngày–giá: sang trang vé máy bay trong tab này (nơi gọi đóng widget). */
  onLeave?: () => void;
}

/** Lời diễn giải lịch trình trong bong bóng chat, kèm thẻ gọn của từng sản phẩm. */
export function WidgetNarration({ text, products, onOpen, quickAddIds, onQuickAdd, cartAddStates, stays, flights, onBookNow,
  bookableIds, onLeave }: WidgetNarrationProps) {
  const known = (productId: string) => Object.prototype.hasOwnProperty.call(products, productId);
  const slotIds = stays?.ids ?? new Set<string>();
  // Chuyến bay không phải chặng của lịch (lượt hỏi giá vé): gom thành một hàng ô ngày–giá thay vì từng thẻ gọn. Tên
  // chuyến trong chữ là chữ thường (`carded`) vì vé không có trang chi tiết; ô ngày mới là chỗ bấm.
  const legIds = new Set((flights ?? []).map((flight) => flight.productId));
  const fareIds = Object.keys(products)
    .filter((productId) => !legIds.has(productId) && !slotIds.has(productId) && isFareFlight(products[productId]));
  // Sản phẩm có thẻ thì tên không cần link nữa; id lạ và khách sạn của hàng thẻ (không có thẻ gọn) vẫn là link.
  const carded = new Set(Object.keys(products).filter((productId) => !slotIds.has(productId)));
  // Sản phẩm của response mà lời diễn giải không nhắc (ví dụ ứng viên của FALLBACK) có thẻ ở cuối bong bóng.
  const blocks = narrationBlocks(text, known, slotIds, new Set(fareIds));
  const cited = new Set(blocks.flatMap((block) => (block.kind === 'card' ? [block.productId] : [])));
  for (const productId of Object.keys(products)) {
    if (!cited.has(productId) && !slotIds.has(productId) && !fareIds.includes(productId)) blocks.push({ kind: 'card', productId });
  }
  if (fareIds.length && !blocks.some((block) => block.kind === 'fares')) blocks.push({ kind: 'fares', productId: fareIds[0] });
  if (stays && !blocks.some((block) => block.kind === 'slot')) blocks.push({ kind: 'slot' });
  return (
    <>
      {blocks.map((block, index) => {
        if (block.kind === 'slot') return <React.Fragment key={index}>{stays?.node}</React.Fragment>;
        if (block.kind === 'fares') {
          // Ô đầu là chuyến lời trả lời nêu; các ngày khác giữ thứ tự của response.
          const ordered = [block.productId, ...fareIds.filter((productId) => productId !== block.productId)];
          return <WidgetFareDays key={index} products={ordered.map((productId) => products[productId])} onNavigate={onLeave} />;
        }
        if (block.kind === 'text') {
          return (
            <NarrationText key={index} text={block.text} onOpen={onOpen} carded={carded} />
          );
        }
        const product = products[block.productId];
        const flight = flights?.find((item) => item.productId === block.productId);
        if (flight) {
          return (
            <div key={index} className="my-4 whitespace-normal">
              <WidgetFlightCard flight={flight} onOpen={() => onOpen(flight.productId)}
                onBookNow={onBookNow && bookableIds?.has(flight.productId) ? () => onBookNow(flight.productId) : undefined} />
            </div>
          );
        }
        return (
          <div key={index} className="my-4 whitespace-normal">
            <ProductCard
              variant="compact"
              className="group gap-3 shadow-xs transition-colors hover:border-ai-300 focus-within:border-ai-400
                [&]:rounded-xl [&>div:first-child]:flex-1 [&>div:first-child>div:last-child]:flex-1
                [&_h4]:line-clamp-none [&_h4]:text-sm [&_h4]:leading-snug [&_h4_button]:line-clamp-2
                [&_h4~div]:flex-col [&_h4~div]:items-start [&_h4~div]:gap-1
                [&_h4~div>span]:max-w-full [&_h4~div>span]:text-slate-500
                [&_p>span:last-child]:text-slate-500
                [&_button]:min-h-11 [&_button]:focus-visible:outline-2
                [&_button]:focus-visible:outline-offset-2 [&_button]:focus-visible:outline-ai-600"
              product={product}
              onSelect={() => onOpen(product.id)}
              showRatingAndAddress
              priceLabel={isFreeToVisit(product) ? 'Tham quan tự do' : undefined}
              onQuickAdd={onQuickAdd && quickAddIds?.has(product.id) ? () => onQuickAdd(product.id) : undefined}
              quickAddState={cartAddStates?.[product.id]}
            />
          </div>
        );
      })}
    </>
  );
}

/** Tạo phân cấp cho tiêu đề đã có, giữ nguyên nội dung từ backend. */
function NarrationText({ text, onOpen, carded }: {
  text: string;
  onOpen: (productId: string) => void;
  carded: ReadonlySet<string>;
}) {
  return (
    <div className="space-y-3 whitespace-normal">
      {text.trim().split(/\n\s*\n/).map((paragraph, index) => (
        <div key={index} className="space-y-2">
          {paragraph.split('\n').map((line, lineIndex) => {
            const heading = /^\*\*([^*]+)\*\*$/.exec(line.trim());
            return heading
              ? <h3 key={lineIndex} className="font-sans pt-2 text-base font-semibold leading-6 text-slate-900">{heading[1]}</h3>
              : <div key={lineIndex} className="whitespace-pre-wrap"><AssistantText text={line} onProduct={onOpen} plainIds={carded} /></div>;
          })}
        </div>
      ))}
    </div>
  );
}
