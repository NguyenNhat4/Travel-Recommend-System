// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WidgetNarration, narrationBlocks } from '../../src/features/itinerary/widget/WidgetNarration';
import type { Product } from '../../src/types/travel';

vi.mock('../../src/context/TravelContext', () => ({
  useTravel: () => ({ navigate: vi.fn(), debugMode: false, recordEvent: vi.fn() }),
}));

const product = (id: string, name: string, extra: Partial<Product> = {}): Product => ({
  id, name, taxonomy: 'attraction', destination: 'Hà Nội', unitPrice: 210000, currency: 'VND',
  imageUrl: `https://cdn.example.vn/${id}.jpg`, description: '', attributes: {}, available: true, address: 'Hà Nội',
  ...extra,
} as Product);

const text = [
  '**Khám phá Hà Nội trong 3 ngày**',
  '**Ngày 3 · 17/10/2026**',
  '• Buổi sáng — [Đài Quan Sát LOTTE](product:lotte) (210.000 đ/người): Ngắm toàn cảnh Hà Nội.',
  '• Buổi chiều — [Văn Miếu](product:vanmieu) (tham quan tự do): Di tích văn hoá.',
  '',
  '**Lưu ý**',
  'Nhắc lại [Đài Quan Sát LOTTE](product:lotte) và [Nơi lạ](product:ghost).',
].join('\n');

const products = {
  lotte: product('lotte', 'Đài Quan Sát LOTTE Hanoi Sky', { aggregateRating: { score: 4.4, count: 13246 } }),
  vanmieu: product('vanmieu', 'Văn Miếu – Quốc Tử Giám', { unitPrice: null, address: '58 P. Quốc Tử Giám, Hà Nội' }),
};

describe('narrationBlocks', () => {
  it('puts one card right after the line that first mentions each known product', () => {
    const blocks = narrationBlocks(text, (id) => id in products);
    expect(blocks.map((block) => (block.kind === 'card' ? `card:${block.productId}` : 'text')))
      .toEqual(['text', 'card:lotte', 'text', 'card:vanmieu', 'text']);
  });

  it('keeps every non-empty line of the narration', () => {
    const joined = narrationBlocks(text, () => true)
      .flatMap((block) => (block.kind === 'text' ? [block.text] : [])).join('\n');
    for (const line of text.split('\n').filter(Boolean)) expect(joined).toContain(line);
  });
});

describe('WidgetNarration', () => {
  afterEach(cleanup);

  it('builds each card from response data, not from the narration text', () => {
    render(<WidgetNarration text={text} products={products} onOpen={vi.fn()} />);
    expect(screen.getByText('Đài Quan Sát LOTTE Hanoi Sky')).toBeTruthy();   // tên catalog, không phải nhãn link
    expect(screen.getByText('4.4/5')).toBeTruthy();
    expect(screen.getByText(/13\.246 đánh giá/)).toBeTruthy();
    expect(screen.getByText('Tham quan tự do')).toBeTruthy();
    expect(screen.getByText('58 P. Quốc Tử Giám, Hà Nội')).toBeTruthy();
    expect(screen.queryByText(/Nơi lạ/)).toBeTruthy();                         // id lạ: chỉ còn chữ, không có thẻ
    expect(screen.getAllByRole('button', { name: /^Xem chi tiết/ })).toHaveLength(2);
  });

  it('opens the detail from the card; names with a card are plain text, unknown ids stay links', () => {
    const onOpen = vi.fn();
    render(<WidgetNarration text={text} products={products} onOpen={onOpen} />);
    expect(screen.queryByRole('button', { name: 'Văn Miếu' })).toBeNull();
    expect(screen.getByText('Văn Miếu')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Xem chi tiết Đài Quan Sát LOTTE Hanoi Sky' }));
    fireEvent.click(screen.getByRole('button', { name: 'Nơi lạ' }));
    expect(onOpen.mock.calls).toEqual([['lotte'], ['ghost']]);
  });

  it('lists products the text does not mention as cards at the end (FALLBACK candidates)', () => {
    render(<WidgetNarration text={'**Chưa dựng được lịch trình hoàn chỉnh**\nMình tìm được 1 khách sạn.'}
      products={{ h1: product('h1', 'Serenity Retreat', { taxonomy: 'hotel' }) }} onOpen={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Xem chi tiết Serenity Retreat' })).toBeTruthy();
  });

  it('offers quick add only for bookable items, without opening the detail', () => {
    const onOpen = vi.fn();
    const onQuickAdd = vi.fn();
    render(<WidgetNarration text={text} products={products} onOpen={onOpen}
      quickAddIds={new Set(['lotte'])} onQuickAdd={onQuickAdd} />);
    const add = screen.getAllByRole('button', { name: /Thêm/ });
    expect(add).toHaveLength(1);
    fireEvent.click(add[0]);
    expect(onQuickAdd).toHaveBeenCalledWith('lotte');
    expect(onOpen).not.toHaveBeenCalled();
  });
});
