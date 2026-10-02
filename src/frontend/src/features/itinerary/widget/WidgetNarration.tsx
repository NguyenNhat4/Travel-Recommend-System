import React from 'react';
import { AssistantText, parseAssistantText } from '../../../components/assistant/inlineBold';
import { ProductCard } from '../../../components/common/ProductCard';
import type { Product } from '../../../types/travel';
import { isFreeToVisit } from './widgetPlan';

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
}

/** Lời diễn giải lịch trình trong bong bóng chat, kèm thẻ gọn của từng sản phẩm. */
export function WidgetNarration({ text, products, onOpen, quickAddIds, onQuickAdd }: WidgetNarrationProps) {
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
            <span key={index} className="block whitespace-pre-wrap">
              <AssistantText text={block.text} onProduct={onOpen} plainIds={carded} />
            </span>
          );
        }
        const product = products[block.productId];
        return (
          <div key={index} className="my-2 whitespace-normal">
            <ProductCard
              variant="compact"
              product={product}
              onSelect={() => onOpen(product.id)}
              showRatingAndAddress
              priceLabel={isFreeToVisit(product) ? 'Tham quan tự do' : undefined}
              onQuickAdd={onQuickAdd && quickAddIds?.has(product.id) ? () => onQuickAdd(product.id) : undefined}
            />
          </div>
        );
      })}
    </>
  );
}
