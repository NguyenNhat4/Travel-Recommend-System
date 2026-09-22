// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AssistantResultPanel } from '../../src/components/assistant/AssistantResultPanel';
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
});
