import React from 'react';
import { AssistantText, parseAssistantText } from '../../../components/assistant/inlineBold';
import { ProductCard } from '../../../components/common/ProductCard';
import type { Product } from '../../../types/travel';
import { isFreeToVisit } from './widgetPlan';
import type { CartAddState } from './useWidgetCart';

export type NarrationBlock = { kind: 'text'; text: string } | { kind: 'card'; productId: string };

/**
 * Tách lời diễn giải thành đoạn chữ và thẻ (PRD user-flow.md §4.2): mỗi sản phẩm `isKnown` có một thẻ ngay sau dòng
 * đầu tiên nhắc `[Tên](product:id)`, các lần nhắc sau chỉ còn link. Dòng trống ngay sau thẻ bỏ đi vì thẻ đã tách đoạn.
 */
export function narrationBlocks(text: string, isKnown: (productId: string) => boolean): NarrationBlock[] {
  const blocks: NarrationBlock[] = [];
  const shown = new Set<string>();
  let buffer: string[] = [];
  const flush = () => {
    if (buffer.length) blocks.push({ kind: 'text', text: buffer.join('\n') });
    buffer = [];
  };
  for (const line of text.split('\n')) {
    if (!buffer.length && blocks[blocks.length - 1]?.kind === 'card' && !line.trim()) continue;
    buffer.push(line);
    const fresh: string[] = [];
    for (const part of parseAssistantText(line)) {
      if (part.kind !== 'product' || shown.has(part.productId) || !isKnown(part.productId)) continue;
      shown.add(part.productId);
      fresh.push(part.productId);
    }
    if (!fresh.length) continue;
    flush();
    for (const productId of fresh) blocks.push({ kind: 'card', productId });
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
}

/** Lời diễn giải lịch trình trong bong bóng chat, kèm thẻ gọn của từng sản phẩm. */
export function WidgetNarration({ text, products, onOpen, quickAddIds, onQuickAdd, cartAddStates }: WidgetNarrationProps) {
  const known = (productId: string) => Object.prototype.hasOwnProperty.call(products, productId);
  // Mọi sản phẩm có trong `products` đều có thẻ, nên tên của chúng không cần link nữa; id lạ vẫn là link.
  const carded = new Set(Object.keys(products));
  // Sản phẩm của response mà lời diễn giải không nhắc (ví dụ ứng viên của FALLBACK) có thẻ ở cuối bong bóng.
  const blocks = narrationBlocks(text, known);
  const cited = new Set(blocks.flatMap((block) => (block.kind === 'card' ? [block.productId] : [])));
  for (const productId of Object.keys(products)) {
    if (!cited.has(productId)) blocks.push({ kind: 'card', productId });
  }
  return (
    <>
      {blocks.map((block, index) => {
        if (block.kind === 'text') {
          return (
            <NarrationText key={index} text={block.text} onOpen={onOpen} carded={carded} />
          );
        }
        const product = products[block.productId];
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
