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

  it('while destinations load, shows chip-shaped skeletons instead of a spinner line, then the real chips', async () => {
    let answer!: (value: unknown) => void;
    global.fetch = vi.fn().mockReturnValue(new Promise((resolve) => { answer = resolve; }));
    render(<TripDetailsForm form={baseForm} onConfirm={vi.fn()} />);

    const skeleton = screen.getByRole('status', { name: 'Đang tải điểm đến…' });
    expect(skeleton.querySelectorAll('.skeleton-wave.rounded-full')).toHaveLength(5);
    expect(screen.queryByRole('button', { name: 'Điểm 0' })).toBeNull();

    answer({ ok: true, status: 200, json: async () => ({ destinations: [{ destination: 'Điểm 0', productCount: 9 }] }) });
    expect(await screen.findByRole('button', { name: 'Điểm 0' })).toBeTruthy();
    expect(screen.queryByRole('status', { name: 'Đang tải điểm đến…' })).toBeNull();
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

describe('TripDetailsForm shows exactly what it sends', () => {
  const originalFetch = global.fetch;
  const unknownForm: ClarificationForm = {
    fields: ['destination', 'days', 'startDate', 'party'],
    defaults: { destination: null, startDate: null, days: null, party: null, budget: null, interests: [], pace: null },
    startDateMin: '2026-10-12',
  };

  afterEach(() => {
    cleanup();
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('leaves an unknown start date empty and blocks confirming until a destination and date are chosen', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200,
      json: async () => ({ destinations: [{ destination: 'Đà Nẵng', productCount: 9 }] }) });
    const onConfirm = vi.fn();
    render(<TripDetailsForm form={unknownForm} onConfirm={onConfirm} />);

    const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
    expect(dateInput.value).toBe('');
    const confirm = screen.getByRole('button', { name: 'Xác nhận' });
    expect(confirm.hasAttribute('disabled')).toBe(true);

    fireEvent.click(await screen.findByRole('button', { name: 'Đà Nẵng' }));
    expect(confirm.hasAttribute('disabled')).toBe(true);
    // 12/10/2026 là thứ Hai: "Thứ 7 này" là 17/10, "Thứ 7 tuần sau" là 24/10.
    expect(screen.getByRole('button', { name: 'Thứ 7 tuần sau (24/10)' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Thứ 7 này (17/10)' }));
    expect(dateInput.value).toBe('2026-10-17');
    fireEvent.click(confirm);

    // Số ngày và số người đang hiện trên form (1 ngày, 1 người lớn) cũng có trong câu gửi đi.
    expect(onConfirm).toHaveBeenCalledWith('Lên lịch trình 1 ngày tại Đà Nẵng, bắt đầu từ ngày 17/10/2026, cho 1 người lớn.');
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
      'Lên lịch trình 3 ngày tại Đà Nẵng, bắt đầu từ ngày 01/10/2026, cho 2 người lớn và 1 trẻ em, ngân sách khoảng 5 triệu.',
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

describe('TripDetailsForm departure city (AC-AGT-02, AC-AGT-03)', () => {
  const originalFetch = global.fetch;
  const originForm: ClarificationForm = { ...baseForm, fields: [...baseForm.fields, 'origin'] };
  const routes = {
    results: [
      { productId: 'r1', name: 'Hà Nội - Đà Nẵng', taxonomy: 'flight', destination: 'Đà Nẵng', unitPrice: null, priceUnit: 'PER_PERSON',
        currency: 'VND', available: true, attributes: { level: 'route', originCity: 'Hà Nội', originLatitude: 21.2187, originLongitude: 105.8042 } },
      { productId: 'r2', name: 'TP. Hồ Chí Minh - Đà Nẵng', taxonomy: 'flight', destination: 'Đà Nẵng', unitPrice: null, priceUnit: 'PER_PERSON',
        currency: 'VND', available: true, attributes: { level: 'route', originCity: 'TP. Hồ Chí Minh', originLatitude: 10.8188, originLongitude: 106.652 } },
    ],
    total: 2, limit: 50, offset: 0, requestId: 'r',
  };

  afterEach(() => {
    cleanup();
    global.fetch = originalFetch;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('adds the departure city to the request sentence', () => {
    expect(tripDetailsPrompt({ ...baseForm.defaults, origin: 'Hà Nội' })).toContain('đi từ Hà Nội');
    expect(tripDetailsPrompt(baseForm.defaults)).not.toContain('đi từ');
  });

  it('asks for the location only on click and sends just the nearest catalog city', async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: string) => ({
      ok: true, status: 200, json: async () => (String(url).includes('/products') ? routes : { destinations: [] }),
    }));
    global.fetch = fetchMock;
    const getCurrentPosition = vi.fn((success: PositionCallback) =>
      success({ coords: { latitude: 20.84, longitude: 106.69 } } as GeolocationPosition));
    vi.stubGlobal('navigator', { ...navigator, geolocation: { getCurrentPosition } });
    const onConfirm = vi.fn();

    render(<TripDetailsForm form={originForm} onConfirm={onConfirm} />);
    expect(getCurrentPosition).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Dùng vị trí hiện tại/ }));
    expect(getCurrentPosition).toHaveBeenCalledTimes(1);

    const input = screen.getByLabelText('Nơi đi') as HTMLInputElement;
    await vi.waitFor(() => expect(input.value).toBe('Hà Nội'));
    fireEvent.click(screen.getByRole('button', { name: /Xác nhận/ }));
    expect(onConfirm.mock.calls[0][0]).toContain('đi từ Hà Nội');
    // Toạ độ không rời trình duyệt: không request nào mang vĩ độ/kinh độ.
    for (const [url, init] of fetchMock.mock.calls) {
      expect(`${url} ${JSON.stringify(init ?? {})}`).not.toMatch(/20\.84|106\.69/);
    }
  });

  it('keeps the field for typing when permission is denied', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ destinations: [] }) });
    const getCurrentPosition = vi.fn((_: PositionCallback, failure: PositionErrorCallback) =>
      failure({ code: 1, PERMISSION_DENIED: 1 } as GeolocationPositionError));
    vi.stubGlobal('navigator', { ...navigator, geolocation: { getCurrentPosition } });

    render(<TripDetailsForm form={originForm} onConfirm={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /Dùng vị trí hiện tại/ }));
    expect(await screen.findByText(/chưa cho phép dùng vị trí/)).toBeTruthy();
    expect((screen.getByLabelText('Nơi đi') as HTMLInputElement).disabled).toBe(false);
  });
});

describe('trip preferences: fixed options and a note (contract 1.26.0, AC-AGT-01)', () => {
  const originalFetch = global.fetch;
  const form: ClarificationForm = {
    ...baseForm,
    fields: [...baseForm.fields, 'interests'],
    defaults: { ...baseForm.defaults, interests: ['Phù hợp trẻ nhỏ', 'ẩm thực'] },
    interestOptions: ['Hồ bơi', 'Phù hợp trẻ nhỏ', 'View biển', 'Có bữa sáng', 'Spa'],
  };

  afterEach(() => {
    cleanup();
    global.fetch = originalFetch;
  });

  it('ticks known options, keeps other known interests in the note and sends both without calling the AI', () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ destinations: [] }) });
    global.fetch = fetchMock;
    const onConfirm = vi.fn();
    render(<TripDetailsForm form={form} onConfirm={onConfirm} />);
    expect(screen.getByRole('button', { name: 'Phù hợp trẻ nhỏ' }).getAttribute('aria-pressed')).toBe('true');
    const note = screen.getByLabelText('Mong muốn khác') as HTMLInputElement;
    expect(note.value).toBe('ẩm thực');
    expect(note.maxLength).toBe(150);
    expect(screen.queryByRole('button', { name: /Viết bằng AI/ })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Hồ bơi' }));
    fireEvent.change(note, { target: { value: 'gần chợ đêm,   đi chậm' } });
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
    expect(onConfirm).toHaveBeenCalledWith(expect.stringMatching(/ưu tiên khách sạn có Phù hợp trẻ nhỏ, Hồ bơi\. Gần chợ đêm, đi chậm$/));
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('preferences'))).toBe(false);
  });

  it('builds the prompt from options only, and ignores interests outside the options without a note', () => {
    const prompt = tripDetailsPrompt({ ...baseForm.defaults, interests: ['Spa', 'ẩm thực'] }, ['Spa'], '  ');
    expect(prompt).toContain('ưu tiên khách sạn có Spa.');
    expect(prompt).not.toContain('ẩm thực');
  });
});
