// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TripDetailsForm, tripDetailsPrompt, type ClarificationForm } from '../../src/components/assistant/TripDetailsForm';

const baseForm: ClarificationForm = {
  fields: ['destination', 'days', 'startDate', 'party', 'budget'],
  defaults: {
    destination: 'Nha Trang',
    startDate: '2026-09-29',
    days: 1,
    party: { type: null, adults: 2, children: 0 },
    budget: null,
    interests: [],
    pace: null,
  },
  startDateMin: '2026-09-29',
};

describe('TripDetailsForm', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    cleanup();
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('shows at most a handful of destination options, not the whole catalog', async () => {
    const destinations = Array.from({ length: 20 }, (_, index) => ({ destination: `Điểm ${index}`, productCount: 20 - index }));
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ destinations }) });

    render(<TripDetailsForm form={baseForm} onConfirm={vi.fn()} />);

    await screen.findByRole('button', { name: 'Điểm 0' });
    const buttons = screen.getAllByRole('button').filter((button) => button.textContent?.startsWith('Điểm '));
    expect(buttons.length).toBeLessThanOrEqual(8);
  });

  it('clamps the day stepper to the 1–7 range', () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ destinations: [] }) });
    render(<TripDetailsForm form={baseForm} onConfirm={vi.fn()} />);

    const daysFieldset = screen.getByText('Số ngày').closest('fieldset')!;
    const plus = daysFieldset.querySelectorAll('button')[1];
    for (let i = 0; i < 10; i += 1) fireEvent.click(plus);
    expect(screen.getByText('7 ngày')).toBeTruthy();
  });

  it('does not allow a start date before startDateMin', () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ destinations: [] }) });
    render(<TripDetailsForm form={baseForm} onConfirm={vi.fn()} />);

    const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
    expect(dateInput.min).toBe('2026-09-29');
    fireEvent.change(dateInput, { target: { value: '2020-01-01' } });
    expect(dateInput.value).toBe('2026-09-29');
  });

  it('confirming only passes the prompt to onConfirm, it does not send anything itself', () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ destinations: [] }) });
    const onConfirm = vi.fn();
    render(<TripDetailsForm form={baseForm} onConfirm={onConfirm} />);

    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledWith(expect.stringContaining('Nha Trang'));
  });
});

describe('tripDetailsPrompt', () => {
  it('builds a complete natural-language request from the intent', () => {
    const prompt = tripDetailsPrompt({
      destination: 'Đà Nẵng',
      startDate: '2026-10-01',
      days: 3,
      party: { type: null, adults: 2, children: 1 },
      budget: 5_000_000,
      interests: [],
      pace: null,
    });

    expect(prompt).toBe(
      'Lên lịch trình 3 ngày tại Đà Nẵng, bắt đầu từ ngày 2026-10-01, cho 2 người lớn và 1 trẻ em, ngân sách khoảng 5 triệu.',
    );
  });

  it('omits optional parts that are not set', () => {
    const prompt = tripDetailsPrompt({
      destination: 'Hà Nội',
      startDate: null,
      days: 1,
      party: null,
      budget: null,
      interests: [],
      pace: null,
    });

    expect(prompt).toBe('Lên lịch trình 1 ngày tại Hà Nội.');
  });
});
