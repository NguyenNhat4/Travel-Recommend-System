import { describe, expect, it } from 'vitest';
import { narrationProducts } from '../../src/features/itinerary/widget/widgetPlan';
import { narrationBlocks } from '../../src/features/itinerary/widget/WidgetNarration';
import type { components } from '../../src/types/api.gen';

/** Lượt khám phá trước khi lập lịch (contract 1.24.0, FR-AGT-06): thẻ dựng từ `searchResults` của câu hỏi lại. */
const summary = (productId: string, taxonomy: 'hotel' | 'attraction') => ({
  productId, name: `Nơi ${productId}`, taxonomy, destination: 'Hà Nội', unitPrice: 220_014, priceUnit: 'PER_NIGHT',
  currency: 'VND', available: true,
}) as components['schemas']['ProductSummary'];

const explore = {
  status: 'NEEDS_CLARIFICATION',
  conversationId: 'c1',
  question: '**Hà Nội có gì đáng đi**\nHà Nội hợp đi bộ.\n[Nơi ho](product:ho): nhiều người đánh giá nhất.\n'
    + '[Nơi charm](product:charm): giá thấp nhất.\nBạn có muốn mình lên lịch Hà Nội không?',
  searchResults: { attraction: [summary('ho', 'attraction')], hotel: [summary('charm', 'hotel')] },
  suggestions: ['Lên lịch Hà Nội cho mình', 'Tối ở Hà Nội đi đâu?'],
} as components['schemas']['ItineraryNeedsClarification'];

describe('explore cards', () => {
  it('builds a card for each product of searchResults', () => {
    expect(Object.keys(narrationProducts(explore)).sort()).toEqual(['charm', 'ho']);
  });

  it('places each card right after the line that first names it', () => {
    const products = narrationProducts(explore);
    const blocks = narrationBlocks(explore.question, (id) => id in products);
    expect(blocks.map((block) => block.kind)).toEqual(['text', 'card', 'text', 'card', 'text']);
  });
});
