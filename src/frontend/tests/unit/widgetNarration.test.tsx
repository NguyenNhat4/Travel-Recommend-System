// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WidgetNarration, narrationBlocks } from '../../src/features/itinerary/widget/WidgetNarration';
import type { ItineraryFlightItem, Product } from '../../src/types/travel';

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
    expect(screen.queryByText('4.4')).toBeNull();                              // điểm chỉ hiện một lần
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
    expect(add[0].getAttribute('aria-label')).toBe('Thêm Đài Quan Sát LOTTE Hanoi Sky vào giỏ');
    expect(add[0].textContent).toBe('Thêm vào giỏ');
    fireEvent.click(add[0]);
    expect(onQuickAdd).toHaveBeenCalledWith('lotte');
    expect(onOpen).not.toHaveBeenCalled();
  });
});

describe('WidgetNarration stays', () => {
  afterEach(cleanup);
  const stayText = [
    '**Nơi nghỉ**',
    '• Đêm 1 — [Khách sạn A](product:hotel) (544.000 ₫/đêm): dành thời gian nghỉ ngơi.',
    'Khách sạn gần các điểm tham quan.',
    '',
    '**Ngày 1**',
    '• Buổi sáng — [Văn Miếu](product:vanmieu).',
    '• Buổi tối — về [Khách sạn A](product:hotel) nghỉ.',
  ].join('\n');
  const withHotels = {
    ...products,
    hotel: product('hotel', 'Khách sạn A', { taxonomy: 'hotel' }),
    other: product('other', 'Khách sạn B', { taxonomy: 'hotel' }),
  };
  const ids = new Set(['hotel', 'other']);
  const order = (container: HTMLElement) => Array.from(container.querySelectorAll('h3, [data-testid="row"]'))
    .map((node) => node.getAttribute('data-testid') ?? node.textContent);

  it('makes the stay options row the content of "Nơi nghỉ": no hotel line, no hotel card', () => {
    const { container } = render(<WidgetNarration text={stayText} products={withHotels} onOpen={vi.fn()}
      stays={{ ids, node: <div data-testid="row" /> }} />);
    expect(order(container)).toEqual(['Nơi nghỉ', 'row', 'Ngày 1']);
    expect(screen.queryByText(/dành thời gian nghỉ ngơi/)).toBeNull();
    expect(screen.getByText('Khách sạn gần các điểm tham quan.')).toBeTruthy();
    // Không thẻ gọn nào cho khách sạn của hàng thẻ, kể cả khách sạn lời diễn giải không nhắc (không nối ở cuối).
    expect(screen.queryByRole('heading', { level: 4, name: /Khách sạn/ })).toBeNull();
    expect(screen.getAllByRole('heading', { level: 4 })).toHaveLength(2);
  });

  it('keeps day lines that mention the hotel, with the name as a link to its detail', () => {
    const onOpen = vi.fn();
    render(<WidgetNarration text={stayText} products={withHotels} onOpen={onOpen}
      stays={{ ids, node: <div data-testid="row" /> }} />);
    fireEvent.click(screen.getByRole('button', { name: 'Khách sạn A' }));
    expect(onOpen).toHaveBeenCalledWith('hotel');
  });

  it('puts the row at the end when the narration never mentions those hotels', () => {
    const { container } = render(<WidgetNarration text={stayText} products={withHotels} onOpen={vi.fn()}
      stays={{ ids: new Set(['ghost-hotel']), node: <div data-testid="row" /> }} />);
    expect(order(container)).toEqual(['Nơi nghỉ', 'Ngày 1', 'row']);
  });
});

describe('WidgetNarration fare days', () => {
  afterEach(cleanup);
  const flight = (id: string, day: string, price: number, flightNumber: string): Product => product(id, `VietJet Air ${flightNumber}`, {
    taxonomy: 'flight', destination: 'Hà Nội', unitPrice: price,
    attributes: {
      airline: 'VietJet Air', flightNumber, departureAt: `${day}T06:15:00+07:00`, arrivalAt: `${day}T08:20:00+07:00`,
      departureTimeLocal: '06:15', originCity: 'TP. Hồ Chí Minh', destinationCity: 'Hà Nội', nonstop: true,
    },
  });
  // Response đưa chuyến lời trả lời nêu lên đầu; các ngày khác không có trong chữ.
  const fares = {
    f12: flight('f12', '2099-10-12', 632000, 'VJ124'),
    f13: flight('f13', '2099-10-13', 710000, 'VJ126'),
    f14: flight('f14', '2099-10-14', 590000, 'VJ128'),
  };
  const fareText = [
    '**Vé TP. Hồ Chí Minh → Hà Nội**',
    'Chuyến rẻ nhất ngày 12/10 là [VietJet Air VJ124](product:f12), 632.000 ₫/khách.',
    'Bạn muốn mình lập lịch Hà Nội luôn không?',
  ].join('\n');

  it('groups fare flights into one block right after the line that first cites one of them', () => {
    const blocks = narrationBlocks(fareText, (id) => id in fares, new Set(), new Set(Object.keys(fares)));
    expect(blocks.map((block) => (block.kind === 'text' ? 'text' : `${block.kind}:${'productId' in block ? block.productId : ''}`)))
      .toEqual(['text', 'fares:f12', 'text']);
  });

  it('renders one tile per day linking to the flights page of that route and day, first tile is the answer', () => {
    const { container } = render(<WidgetNarration text={fareText} products={fares} onOpen={vi.fn()} />);
    expect(screen.getAllByRole('region', { name: 'Giá vé theo ngày bay' })).toHaveLength(1);
    const links = screen.getAllByRole('link');
    expect(links.map((link) => link.getAttribute('aria-label'))).toEqual([
      'Xem chuyến bay ngày 12/10, từ 632.000 ₫',
      'Xem chuyến bay ngày 13/10, từ 710.000 ₫',
      'Xem chuyến bay ngày 14/10, từ 590.000 ₫',
    ]);
    const url = new URL(links[0].getAttribute('href')!, 'http://x');
    expect(url.pathname).toBe('/flights');
    expect(url.searchParams.get('origin')).toBe('TP. Hồ Chí Minh');
    expect(url.searchParams.get('destination')).toBe('Hà Nội');
    expect(url.searchParams.get('checkIn')).toBe('2099-10-12');
    expect(new URL(links[2].getAttribute('href')!, 'http://x').searchParams.get('checkIn')).toBe('2099-10-14');
    expect(links[0].textContent).toContain('T2, 12/10');
    expect(links[0].textContent).toContain('06:15 · VietJet Air VJ124');
    expect(links[0].className).toContain('bg-sky-50');
    expect(links[1].className).not.toContain('border-blue-300 bg-sky-50');
    // Không thẻ gọn nào, và tên chuyến trong chữ không mở panel chi tiết (vé không có trang chi tiết).
    expect(screen.queryByRole('button', { name: /Xem chi tiết/ })).toBeNull();
    expect(screen.queryByRole('button', { name: 'VietJet Air VJ124' })).toBeNull();
    expect(container.textContent).toContain('Bấm vào một ngày để xem các chuyến trên trang vé máy bay.');
  });

  it('puts the cited flight first and the block at the end when the text cites none', () => {
    const cited = narrationBlocks('Ngày 13 có [VJ126](product:f13).', (id) => id in fares, new Set(), new Set(Object.keys(fares)));
    expect(cited).toContainEqual({ kind: 'fares', productId: 'f13' });
    render(<WidgetNarration text={'Ngày 13 có [VJ126](product:f13).'} products={fares} onOpen={vi.fn()} />);
    expect(screen.getAllByRole('link')[0].getAttribute('aria-label')).toBe('Xem chuyến bay ngày 13/10, từ 710.000 ₫');
    cleanup();
    const { container } = render(<WidgetNarration text={'Giá vé tuyến này.'} products={fares} onOpen={vi.fn()} />);
    expect(container.lastElementChild?.getAttribute('aria-label')).toBe('Giá vé theo ngày bay');
  });

  it('names the destination on each tile when the tiles belong to different routes', () => {
    const toDaNang: Product = { ...fares.f13, attributes: { ...fares.f13.attributes, destinationCity: 'Đà Nẵng' } };
    render(<WidgetNarration text={fareText} products={{ f12: fares.f12, f13: toDaNang }} onOpen={vi.fn()} />);
    const links = screen.getAllByRole('link');
    expect(links[1].textContent).toContain('Đi Đà Nẵng');
    expect(links[1].getAttribute('aria-label')).toBe('Xem chuyến bay đi Đà Nẵng ngày 13/10, từ 710.000 ₫');
    cleanup();
    render(<WidgetNarration text={fareText} products={fares} onOpen={vi.fn()} />);
    expect(screen.getAllByRole('link')[0].textContent).not.toContain('Đi Hà Nội');
  });

  it('marks business-class and illustrative prices on the tile', () => {
    const business: Product = { ...fares.f13, attributes: { ...fares.f13.attributes, cabinClass: 'BUSINESS', simulated: true } };
    render(<WidgetNarration text={fareText} products={{ f12: fares.f12, f13: business }} onOpen={vi.fn()} />);
    const links = screen.getAllByRole('link');
    expect(links[1].textContent).toContain('Thương gia · giá minh hoạ');
    expect(links[0].textContent).not.toContain('Thương gia');
  });

  it('keeps plan legs as flight cards, not fare tiles', () => {
    const leg: ItineraryFlightItem = { productId: 'f12', product: fares.f12, date: '2099-10-12', returnDate: null,
      direction: 'OUTBOUND', passengers: 1 };
    render(<WidgetNarration text={fareText} products={{ f12: fares.f12 }} onOpen={vi.fn()} flights={[leg]} />);
    expect(screen.queryByRole('region', { name: 'Giá vé theo ngày bay' })).toBeNull();
    expect(screen.getByRole('article', { name: /Vé máy bay/ })).toBeTruthy();
  });
});

describe('product-only headings', () => {
  afterEach(cleanup);

  it('shows a standalone product name only on its clickable card', () => {
    const onOpen = vi.fn();
    render(<WidgetNarration text={'**[Hồ Hoàn Kiếm](product:lake)**\nBạn có thể ghé dạo quanh hồ.'}
      products={{ lake: product('lake', 'Hồ Hoàn Kiếm') }} onOpen={onOpen} />);
    expect(screen.getAllByText('Hồ Hoàn Kiếm')).toHaveLength(1);
    expect(screen.getByText('Bạn có thể ghé dạo quanh hồ.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Xem chi tiết Hồ Hoàn Kiếm' }));
    expect(onOpen).toHaveBeenCalledWith('lake');
  });

  it('keeps names within useful sentences and preserves unknown references', () => {
    const blocks = narrationBlocks('Ghé [Hồ Hoàn Kiếm](product:lake) để dạo bộ.\n[Nơi khác](product:unknown)',
      (id) => id === 'lake');
    expect(blocks).toEqual([
      { kind: 'text', text: 'Ghé [Hồ Hoàn Kiếm](product:lake) để dạo bộ.' },
      { kind: 'card', productId: 'lake' },
      { kind: 'text', text: '[Nơi khác](product:unknown)' },
    ]);
  });
});
