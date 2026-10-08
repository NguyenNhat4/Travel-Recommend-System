// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AssistantResultPanel, itineraryCartItems } from '../../src/components/assistant/AssistantResultPanel';
import type { components } from '../../src/types/api.gen';

type Response = components['schemas']['ItineraryResponse'];

const product: components['schemas']['ProductSummary'] = {
  productId: 'api-product-1',
  name: 'Khách sạn từ API',
  taxonomy: 'hotel',
  destination: 'Hội An',
  status: 'ACTIVE',
  unitPrice: null,
  currency: 'VND',
  priceUnit: 'UNKNOWN',
  available: true,
  imageUrl: null,
};

describe('AssistantResultPanel', () => {
  afterEach(cleanup);

  it('renders the backend itinerary and reports the map empty state without inventing coordinates', () => {
    const response: Response = {
      status: 'COMPLETED',
      conversationId: 'api-session',
      intent: {
        destination: 'Hội An',
        startDate: null,
        days: 1,
        party: { type: 'SOLO', adults: 1, children: 0 },
        budget: null,
        interests: [],
        pace: null,
      },
      itinerary: {
        title: 'Một ngày ở Hội An',
        stay: { product, nights: 1 },
        days: [{ day: 1, title: 'Phố cổ', slots: [{ time: 'MORNING', product, note: 'Giá snapshot chưa xác định' }] }],
        estimatedTotal: null,
        currency: 'VND',
        budgetStatus: 'UNKNOWN',
      },
      warnings: [],
    };

    render(<AssistantResultPanel response={response} />);

    expect(screen.getByText('Một ngày ở Hội An')).toBeTruthy();
    expect(screen.getAllByText('Khách sạn từ API')).toHaveLength(2);
    expect(screen.getAllByText(/chưa đủ dữ liệu/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('region', { name: 'Bản đồ lịch trình' }).textContent).toMatch(/tọa độ/i);
  });

  it('offers only backend clarification values and submits the selected override', () => {
    const onIntentOverride = vi.fn();
    const response: Response = {
      status: 'NEEDS_CLARIFICATION',
      conversationId: 'api-session',
      question: 'Bạn muốn đi trong bao nhiêu ngày?',
      missingFields: ['days'],
      suggestedValues: { days: [2, 3] },
    };

    render(<AssistantResultPanel response={response} onIntentOverride={onIntentOverride} />);
    fireEvent.click(screen.getByRole('button', { name: '3 ngày' }));
    expect(onIntentOverride).toHaveBeenCalledWith({ days: 3 });
  });

  it('shows backend no-results message and suggestion', () => {
    const onSuggestion = vi.fn();
    const response: Response = {
      status: 'NO_RESULTS',
      conversationId: 'api-session',
      message: 'Backend chưa tìm được kết quả.',
      suggestions: ['Thử điểm đến khác'],
    };
    render(<AssistantResultPanel response={response} onSuggestion={onSuggestion} />);
    fireEvent.click(screen.getByRole('button', { name: 'Thử điểm đến khác' }));
    expect(onSuggestion).toHaveBeenCalledWith('Thử điểm đến khác');
  });

  it('renders fallback products from backend search results', () => {
    const response: Response = {
      status: 'FALLBACK',
      conversationId: 'api-session',
      message: 'Backend trả về lựa chọn gần nhất.',
      searchResults: { hotel: [product] },
    };
    render(<AssistantResultPanel response={response} />);
    expect(screen.getByText('Backend trả về lựa chọn gần nhất.')).toBeTruthy();
    expect(screen.getAllByText('Khách sạn từ API').length).toBeGreaterThan(0);
  });

  describe('completed itinerary actions', () => {
    const hotel: components['schemas']['ProductSummary'] = {
      ...product,
      productId: 'hotel-1',
      name: 'Khách sạn biển',
      unitPrice: 1_500_000,
      priceUnit: 'PER_NIGHT',
    };
    const ticket: components['schemas']['ProductSummary'] = {
      ...product,
      productId: 'ticket-1',
      name: 'Vé VinWonders',
      taxonomy: 'attraction',
      unitPrice: 850_000,
      priceUnit: 'PER_PERSON',
    };
    const soldOut: components['schemas']['ProductSummary'] = {
      ...product,
      productId: 'ticket-2',
      name: 'Vé hết chỗ',
      taxonomy: 'attraction',
      unitPrice: 300_000,
      priceUnit: 'PER_PERSON',
      available: false,
    };
    const completed: Response = {
      status: 'COMPLETED',
      conversationId: 'conv-1',
      intent: {
        destination: 'Nha Trang',
        startDate: '2026-10-01',
        days: 2,
        party: { type: 'FAMILY_WITH_KIDS', adults: 2, children: 1 },
        budget: 2_000_000,
        interests: [],
        pace: null,
      },
      itinerary: {
        title: 'Nha Trang 2 ngày',
        stay: { product: hotel, nights: 1 },
        days: [
          { day: 1, date: '2026-10-01', slots: [{ time: 'MORNING', product: ticket, note: null }, { time: 'EVENING', product: null, activityType: 'MEAL', note: 'Ăn tối ven biển' }] },
          { day: 2, date: '2026-10-02', slots: [{ time: 'AFTERNOON', product: ticket, note: null }, { time: 'NOON', product: soldOut, note: null }] },
        ],
        bookableCount: 2,
        estimatedTotal: 3_200_000,
        currency: 'VND',
        budgetStatus: 'OVER_BUDGET',
      },
      warnings: [{ code: 'OVER_BUDGET', message: 'Tổng vượt ngân sách.' }],
    };

    it('links every product card to its detail page', () => {
      render(<AssistantResultPanel response={completed} />);
      const links = screen.getAllByRole('link', { name: 'Xem chi tiết' });
      expect(links.map((link) => link.getAttribute('href'))).toEqual(
        expect.arrayContaining(['/product/hotel-1', '/product/ticket-1', '/product/ticket-2']),
      );
    });

    it('shows localized labels instead of raw enum keys and no backend wording', () => {
      const { container } = render(<AssistantResultPanel response={completed} />);
      const text = container.textContent ?? '';
      expect(text).toContain('Sáng');
      expect(text).toContain('Tối');
      expect(text).toContain('Vượt ngân sách');
      expect(text).toContain('Gia đình có trẻ em');
      expect(text).toContain('/ đêm');
      expect(text).toContain('Ăn uống');
      expect(text).not.toMatch(/MORNING|OVER_BUDGET|FAMILY_WITH_KIDS|PER_NIGHT|backend/);
    });

    it('collects each eligible product once with the itinerary dates', () => {
      expect(itineraryCartItems(completed.status === 'COMPLETED' ? completed.itinerary : (undefined as never))).toEqual([
        { product: hotel, usingDate: '2026-10-01', checkOutDate: '2026-10-02' },
        { product: ticket, usingDate: '2026-10-01' },
      ]);
    });

    it('books each hotel of a hotel change from the day of its first night (AC-AGT-04, contract 1.19.0)', () => {
      const south = { ...hotel, productId: 'hotel-2', name: 'Khách sạn Nam đảo' };
      const day = (n: number) => ({ day: n, date: `2026-10-0${n}`, slots: [] });
      const itinerary = {
        ...(completed.status === 'COMPLETED' ? completed.itinerary : (undefined as never)),
        stay: { product: hotel, nights: 2, fromNight: 1 },
        stays: [{ product: hotel, nights: 2, fromNight: 1 }, { product: south, nights: 2, fromNight: 3 }],
        days: [1, 2, 3, 4, 5].map(day),
      };
      expect(itineraryCartItems(itinerary)).toEqual([
        { product: hotel, usingDate: '2026-10-01', checkOutDate: '2026-10-03' },
        { product: south, usingDate: '2026-10-03', checkOutDate: '2026-10-05' },
      ]);
    });

    it('attaches the itinerary party to every cart item so the cart gets adults and children', () => {
      const party = { adults: 2, children: 1 };
      expect(itineraryCartItems(completed.status === 'COMPLETED' ? completed.itinerary : (undefined as never), party)).toEqual([
        { product: hotel, usingDate: '2026-10-01', checkOutDate: '2026-10-02', party },
        { product: ticket, usingDate: '2026-10-01', party },
      ]);
    });

    it('pays the whole itinerary in one go and books single items, with the intent party', () => {
      const onAddToCart = vi.fn();
      const onBookNow = vi.fn();
      render(<AssistantResultPanel response={completed} onAddToCart={onAddToCart} onBookNow={onBookNow} />);
      const party = { adults: 2, children: 1 };                                 // intent.party của fixture
      fireEvent.click(screen.getByRole('button', { name: /Thanh toán tất cả \(2\)/ }));
      expect(onBookNow).toHaveBeenLastCalledWith([
        { product: hotel, usingDate: '2026-10-01', checkOutDate: '2026-10-02', party },
        { product: ticket, usingDate: '2026-10-01', party },
      ]);
      // Khách sạn chỉ đặt trực tiếp: Thêm vào giỏ chỉ có ở vé ngày 1 và ngày 2; vé hết chỗ không có nút nào.
      expect(screen.getAllByRole('button', { name: 'Thêm vào giỏ' })).toHaveLength(2);
      fireEvent.click(screen.getAllByRole('button', { name: 'Thêm vào giỏ' })[1]);
      expect(onAddToCart).toHaveBeenLastCalledWith([{ product: ticket, usingDate: '2026-10-02', party }]);
      // Đặt ngay có ở mọi mục đặt được: khách sạn + vé ngày 1 + vé ngày 2.
      expect(screen.getAllByRole('button', { name: 'Đặt ngay' })).toHaveLength(3);
      fireEvent.click(screen.getAllByRole('button', { name: 'Đặt ngay' })[0]);
      expect(onBookNow).toHaveBeenLastCalledWith([{ product: hotel, usingDate: '2026-10-01', checkOutDate: '2026-10-02', party }]);
    });

    it('hides the booking buttons when the price is unknown', () => {
      const unknownPrice: Response = { ...completed, itinerary: { ...completed.itinerary, stay: { product, nights: 1 }, days: [] } } as Response;
      render(<AssistantResultPanel response={unknownPrice} onAddToCart={vi.fn()} onBookNow={vi.fn()} />);
      expect(screen.queryByRole('button', { name: 'Thêm vào giỏ' })).toBeNull();
      expect(screen.queryByRole('button', { name: 'Đặt ngay' })).toBeNull();
      expect(screen.queryByRole('button', { name: /Thanh toán tất cả/ })).toBeNull();
    });

    it('offers quick edits that stay within 1–7 days and name the replaced product', () => {
      const onIntentOverride = vi.fn();
      const onSuggestion = vi.fn();
      render(<AssistantResultPanel response={completed} onIntentOverride={onIntentOverride} onSuggestion={onSuggestion} />);
      fireEvent.click(screen.getByRole('button', { name: 'Thêm 1 ngày' }));
      expect(onIntentOverride).toHaveBeenCalledWith({ days: 3 });
      fireEvent.click(screen.getByRole('button', { name: 'Bớt 1 ngày' }));
      expect(onIntentOverride).toHaveBeenCalledWith({ days: 1 });
      fireEvent.click(screen.getAllByRole('button', { name: 'Đổi lựa chọn khác' })[0]);
      expect(onSuggestion).toHaveBeenCalledWith('Đổi Vé VinWonders (ngày 1, buổi sáng) sang lựa chọn khác');
      fireEvent.click(screen.getByRole('button', { name: 'Giảm chi phí cho vừa ngân sách' }));
      expect(onSuggestion).toHaveBeenCalledWith('Giảm chi phí để vừa ngân sách');
    });

    it('caps days at 7 and disables edits while the agent is running', () => {
      const sevenDays = { ...completed, intent: { ...(completed.status === 'COMPLETED' ? completed.intent : undefined), days: 7 } } as Response;
      const { rerender } = render(<AssistantResultPanel response={sevenDays} onIntentOverride={vi.fn()} onSuggestion={vi.fn()} />);
      expect((screen.getByRole('button', { name: 'Thêm 1 ngày' }) as HTMLButtonElement).disabled).toBe(true);
      rerender(<AssistantResultPanel response={completed} onIntentOverride={vi.fn()} onSuggestion={vi.fn()} busy />);
      expect((screen.getByRole('button', { name: 'Bớt 1 ngày' }) as HTMLButtonElement).disabled).toBe(true);
    });

    it('hides edit controls for saved or shared itineraries', () => {
      render(<AssistantResultPanel response={completed} onIntentOverride={vi.fn()} onSuggestion={vi.fn()} readOnly />);
      expect(screen.queryByRole('button', { name: 'Thêm 1 ngày' })).toBeNull();
      expect(screen.queryByRole('button', { name: 'Đổi lựa chọn khác' })).toBeNull();
    });
  });
});
