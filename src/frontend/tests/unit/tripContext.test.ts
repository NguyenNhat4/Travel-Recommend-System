import { describe, expect, it } from 'vitest';
import {
  addDaysIso, describeTripContext, parseTripContext, serializeTripContext, todayVN,
} from '../../src/features/search/tripContext';

const TODAY = '2026-09-29';
const parse = (query: string) => parseTripContext(new URLSearchParams(query), TODAY);

describe('parseTripContext', () => {
  it('reads a full valid context', () => {
    expect(parse('checkIn=2026-10-15&checkOut=2026-10-17&adults=2&children=1&rooms=1')).toEqual({
      checkIn: '2026-10-15', checkOut: '2026-10-17', adults: 2, children: 1, rooms: 1,
    });
  });

  it('drops past or malformed dates silently', () => {
    expect(parse('checkIn=2026-09-28')).toEqual({});
    expect(parse('checkIn=2026-02-30')).toEqual({});
    expect(parse('checkIn=15/10/2026')).toEqual({});
    expect(parse('checkIn=2026-09-29')).toEqual({ checkIn: '2026-09-29' });
  });

  it('needs checkOut strictly after checkIn, and ignores checkOut alone', () => {
    expect(parse('checkIn=2026-10-15&checkOut=2026-10-15')).toEqual({ checkIn: '2026-10-15' });
    expect(parse('checkIn=2026-10-15&checkOut=2026-10-10')).toEqual({ checkIn: '2026-10-15' });
    expect(parse('checkOut=2026-10-17')).toEqual({});
  });

  it('keeps the party within 1–9 guests per item (FR-BKG-08)', () => {
    expect(parse('adults=9')).toEqual({ adults: 9 });
    expect(parse('adults=10')).toEqual({});
    expect(parse('adults=0')).toEqual({});
    expect(parse('adults=8&children=2')).toEqual({ adults: 8 });
    expect(parse('adults=2&children=x')).toEqual({ adults: 2 });
  });

  it('rejects more rooms than adults', () => {
    expect(parse('adults=2&rooms=3')).toEqual({ adults: 2 });
    expect(parse('adults=2&rooms=2')).toEqual({ adults: 2, rooms: 2 });
    expect(parse('rooms=2')).toEqual({ rooms: 2 });
  });
});

describe('serializeTripContext', () => {
  it('round-trips through parse', () => {
    const ctx = { checkIn: '2026-10-15', checkOut: '2026-10-17', adults: 2, children: 1, rooms: 1 };
    expect(parse(serializeTripContext(ctx))).toEqual(ctx);
  });

  it('is empty for an empty context and skips zero children and orphan checkOut', () => {
    expect(serializeTripContext({})).toBe('');
    expect(serializeTripContext({ adults: 2, children: 0 })).toBe('adults=2');
    expect(serializeTripContext({ checkOut: '2026-10-17' })).toBe('');
  });
});

describe('describeTripContext', () => {
  it('summarises dates and party in Vietnamese', () => {
    expect(describeTripContext({ checkIn: '2026-10-15', checkOut: '2026-10-17', rooms: 1, adults: 2 })).toBe('15/10 – 17/10 · 1 phòng, 2 người lớn');
    expect(describeTripContext({ checkIn: '2026-10-15', adults: 2, children: 1 })).toBe('15/10 · 2 người lớn, 1 trẻ em');
    expect(describeTripContext({})).toBe('');
  });
});

describe('date helpers', () => {
  it('adds days across month ends', () => {
    expect(addDaysIso('2026-09-30', 1)).toBe('2026-10-01');
    expect(addDaysIso('2026-12-31', 2)).toBe('2027-01-02');
  });

  it('uses the Vietnam calendar day, not UTC', () => {
    expect(todayVN(new Date('2026-09-29T18:30:00Z'))).toBe('2026-09-30'); // 01:30 ngày 30 giờ Việt Nam
    expect(todayVN(new Date('2026-09-29T16:59:00Z'))).toBe('2026-09-29');
  });
});
