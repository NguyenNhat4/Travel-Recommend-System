// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  AssistantTripStarter,
  tripStarterMessage,
  type TripStarterSelection,
} from '../../src/components/assistant/AssistantTripStarter';

describe('AssistantTripStarter', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    cleanup();
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('shows immediately, loads route destinations, and submits the selected trip', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        destinations: [
          { destination: 'Hội An', productCount: 12 },
          { destination: 'Nha Trang', productCount: 34 },
        ],
      }),
    });
    const onSubmit = vi.fn();

    render(<AssistantTripStarter onSubmit={onSubmit} />);

    expect(screen.getByText('Tương tác cùng AI')).toBeTruthy();
    expect(screen.getByRole('status').textContent).toContain('Đang tải danh sách điểm đến');

    await screen.findByRole('button', { name: 'Nha Trang' });
    fireEvent.click(screen.getByRole('button', { name: 'Nha Trang' }));
    fireEvent.click(screen.getByRole('button', { name: '4 ngày (3 đêm)' }));
    fireEvent.click(screen.getByRole('button', { name: /Nhóm bạn trẻ/ }));
    fireEvent.click(screen.getByRole('button', { name: /Tối ưu chi phí/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Tạo lịch trình' }));

    expect(onSubmit).toHaveBeenCalledWith({
      destination: 'Nha Trang',
      days: 4,
      party: 'friends',
      style: 'budget',
    });
  });

  it('shows an explicit retry state when destinations cannot be loaded', async () => {
    global.fetch = vi.fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ destinations: [{ destination: 'Đà Lạt', productCount: 8 }] }),
      });

    render(<AssistantTripStarter onSubmit={vi.fn()} />);

    await screen.findByText('Chưa tải được danh sách điểm đến.');
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    await screen.findByRole('button', { name: 'Đà Lạt' });
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });
});

describe('tripStarterMessage', () => {
  it('builds the first natural-language assistant request', () => {
    const selection: TripStarterSelection = {
      destination: 'Phú Quốc',
      days: 3,
      party: 'couple',
      style: 'luxury',
    };

    expect(tripStarterMessage(selection)).toBe(
      'Tôi chọn đi Phú Quốc trong 3 ngày cho cặp đôi, ưu tiên nghỉ dưỡng sang trọng.',
    );
  });
});
