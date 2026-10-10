import { describe, expect, it } from 'vitest';
import cases from '../../../shared/contracts/tests/booking-rules-cases.json';
import {
  adultFrom, ageOn, checkCheckout, checkContact, checkItems, checkParty, fareTypeOn, flightDatesOf, formatDmy, isInfantOn, isValidIso,
  isValidNamePart, maskDmy, messageFor, orderPartyCap, parseDmy, splitFullName,
  type CartFacts, type ContactInput, type ItemInput, type TravelerInput, type Violation,
} from '../../src/components/checkout/checkoutRules';
import { childUnitPrice, estimateFares } from '../../src/components/checkout/fareEstimate';

/**
 * Cùng bộ ca với Backend (`src/backend/tests/unit/domain/booking/test_party_rules.py`): hai phía phải cho cùng kết quả.
 * Nguồn: src/shared/contracts/tests/booking-rules-cases.json (spec checkout-nhieu-buoc-hanh-khach.md §12).
 */
type Case = { name: string; scope: 'party' | 'items' | 'all'; override: Record<string, unknown>; expect: Array<{ field: string; reason: string; cartItemId?: string }> };
const base = cases.base as Record<string, any>;
const key = (v: { field: string; reason: string; cartItemId?: string }) => `${v.field}|${v.reason}|${v.cartItemId ?? ''}`;

function build(c: Case) {
  const data = { ...base, ...c.override } as any;
  const contact: ContactInput = data.contact;
  const travelers: TravelerInput[] = data.travelers;
  const cart: CartFacts[] = data.cart;
  const details: ItemInput[] = data.itemDetails;
  return { contact, travelers, cart, details, today: data.today as string };
}

describe('checkout rules match the shared cases', () => {
  for (const c of cases.checkout as Case[]) {
    it(c.name, () => {
      const { contact, travelers, cart, details, today } = build(c);
      const earliest = cart.map((x) => x.usingDate).sort()[0];
      const maxParty = orderPartyCap(cart);
      let got: Violation[];
      if (c.scope === 'party') {
        got = [...checkContact(contact), ...checkParty(travelers, { earliest, today, flightDates: flightDatesOf(cart), maxParty }).violations];
      } else if (c.scope === 'items') {
        got = checkItems(checkParty(travelers, { earliest, today, flightDates: flightDatesOf(cart), maxParty }).travelers, details, cart);
      } else {
        got = checkCheckout(contact, travelers, details, cart, today).violations;
      }
      expect(got.map(key).sort()).toEqual(c.expect.map(key).sort());
    });
  }
});

describe('party limit messages (FR-BKG-08) match the backend wording', () => {
  const msg = (field: string, reason: string, params?: Record<string, string | number>) => messageFor({ field, reason, params });
  it('per item, per room and per order', () => {
    expect(msg('guests', 'PARTY_TOO_LARGE')).toBe('Mỗi đơn tối đa 9 khách. Vui lòng tách thành nhiều đơn.');
    expect(msg('travelers', 'PARTY_TOO_LARGE', { maxParty: 9 })).toBe('Mỗi đơn tối đa 9 khách. Vui lòng tách thành nhiều đơn.');
    expect(msg('travelers', 'PARTY_TOO_LARGE', { maxParty: 18 })).toBe('Mỗi đơn tối đa 18 khách. Vui lòng tách thành nhiều đơn.');
    expect(msg('guests', 'PARTY_TOO_LARGE', { maxParty: 18, rooms: 2 })).toBe('Mỗi phòng tối đa 9 khách (18 khách cho 2 phòng). Vui lòng thêm phòng.');
    expect(msg('itemDetails', 'PARTY_TOO_LARGE', { scope: 'mixed', itemName: 'Lucky Sun' })).toBe('Lucky Sun trên 9 khách phải đặt riêng, không gộp với dịch vụ khác.');
    expect(msg('quantity', 'ROOMS_TOO_MANY', { maxRooms: 9 })).toBe('Mỗi lần đặt tối đa 9 phòng.');
  });

  it('order cap: hotel-only follows the largest hotel, any other item caps the party at 9', () => {
    expect(orderPartyCap([{ taxonomy: 'hotel', quantity: 2 }])).toBe(18);
    expect(orderPartyCap([{ taxonomy: 'hotel', quantity: 2 }, { taxonomy: 'hotel', quantity: 3 }])).toBe(27);
    expect(orderPartyCap([{ taxonomy: 'hotel', quantity: 2 }, { taxonomy: 'flight', quantity: 2 }])).toBe(9);
    expect(orderPartyCap([])).toBe(9);
  });
});

describe('age rules match the shared cases', () => {
  for (const c of cases.age) {
    it(c.name, () => {
      expect(ageOn(c.birth, c.day)).toBe(c.age);
      expect(isInfantOn({ type: 'CHILD', birth: c.birth }, c.day)).toBe(c.infant);
    });
  }
  for (const c of cases.turnsAdult) {
    it(`turns adult: ${c.name}`, () => {
      expect(adultFrom(c.birth)).toBe(c.on);
      expect(fareTypeOn({ type: 'CHILD', birth: c.birth }, c.on)).toBe('ADULT');
      const dayBefore = new Date(`${c.on}T00:00:00Z`);
      dayBefore.setUTCDate(dayBefore.getUTCDate() - 1);
      expect(fareTypeOn({ type: 'CHILD', birth: c.birth }, dayBefore.toISOString().slice(0, 10))).toBe('CHILD');
    });
  }
  it('a child without a valid birth date is priced as a child and never an infant', () => {
    expect(fareTypeOn({ type: 'CHILD', birth: null }, '2026-10-17')).toBe('CHILD');
    expect(isInfantOn({ type: 'CHILD', birth: null }, '2026-10-17')).toBe(false);
  });
});

describe('fare estimate matches the shared cases', () => {
  for (const c of cases.fares as any[]) {
    it(c.name, () => {
      const got = estimateFares({ taxonomy: c.taxonomy, unitPrice: c.unitPrice, attributes: c.attributes, quantity: c.quantity,
        nights: c.nights, adults: c.guests.adults, children: c.guests.children });
      expect(got.lines).toEqual(c.expect.lines);
      expect(got.total).toBe(c.expect.total);
    });
  }
  it('child price is used only for tickets and golf', () => {
    expect(childUnitPrice('attraction', 1_500_000, { childPrice: 504000 })).toBe(504000);
    expect(childUnitPrice('flight', 634_000, { childPrice: 100_000 })).toBeNull();
    expect(childUnitPrice('attraction', 100_000, { childPrice: 450_000 })).toBeNull();
    expect(childUnitPrice('attraction', 100_000, { childPrice: 0 })).toBeNull();
  });
});

describe('messages are the Vietnamese sentences of spec §5.6', () => {
  it('names the date a child turns twelve', () => {
    expect(messageFor({ field: 'travelers[2].birthDate', reason: 'CHILD_AGE_INVALID', params: { turned12On: '2026-10-17' } }))
      .toBe('Bé đã đủ 12 tuổi vào 17/10/2026. Vui lòng chọn loại Người lớn.');
  });
  it('tells which room is over capacity', () => {
    expect(messageFor({ field: 'itemDetails[0].rooms[0]', reason: 'OCCUPANCY_EXCEEDED', params: { roomNo: 1, maxOccupancy: 3 } }))
      .toBe('Phòng 1 chứa tối đa 3 khách.');
  });
  it('picks the sentence by scope for ADULT_REQUIRED', () => {
    expect(messageFor({ field: 'travelers', reason: 'ADULT_REQUIRED', params: { scope: 'party' } })).toBe('Cần ít nhất 1 người lớn (từ 12 tuổi).');
    expect(messageFor({ field: 'x', reason: 'ADULT_REQUIRED', params: { scope: 'room' } })).toBe('Mỗi phòng cần ít nhất 1 người lớn.');
    expect(messageFor({ field: 'x', reason: 'ADULT_REQUIRED', params: { scope: 'item' } }))
      .toBe('Trẻ em cần đi cùng ít nhất 1 người lớn trong dịch vụ này.');
  });
  it('asks for the right name part', () => {
    expect(messageFor({ field: 'travelers[0].surname', reason: 'REQUIRED' })).toBe('Vui lòng nhập họ.');
    expect(messageFor({ field: 'travelers[0].givenNames', reason: 'REQUIRED' })).toBe('Vui lòng nhập tên đệm và tên.');
  });
});

describe('date and name helpers', () => {
  it('reads dd/mm/yyyy only when it is a real calendar date', () => {
    expect(parseDmy('12/05/2019')).toBe('2019-05-12');
    expect(parseDmy('30/02/2019')).toBeNull();
    expect(parseDmy('12/5/2019')).toBeNull();
    expect(parseDmy('12/05/1800')).toBeNull();
    expect(isValidIso('2024-02-29')).toBe(true);
    expect(isValidIso('2026-02-29')).toBe(false);
    expect(formatDmy('2026-10-17')).toBe('17/10/2026');
  });
  it('inserts slashes while typing digits and leaves deletions alone', () => {
    expect(maskDmy('', '1')).toBe('1');
    expect(maskDmy('1', '12')).toBe('12/');
    expect(maskDmy('12/', '12/0')).toBe('12/0');
    expect(maskDmy('12/0', '12/05')).toBe('12/05/');
    expect(maskDmy('12/05/', '12/05/2019')).toBe('12/05/2019');
    expect(maskDmy('12/05/2019', '12/05/201')).toBe('12/05/201');
    expect(maskDmy('12/05/', '12/05')).toBe('12/05');                 // xoá lùi dấu "/": để nguyên
    expect(maskDmy('12/05/2019', '17102014')).toBe('17/10/2014');     // dán đè giá trị khác: định dạng lại từ các chữ số
  });
  it('splits the account name into surname and given names', () => {
    expect(splitFullName('  Nguyễn   Minh Anh ')).toEqual(['Nguyễn', 'Minh Anh']);
    expect(splitFullName('Sơn')).toEqual(['Sơn', '']);
    expect(splitFullName('')).toEqual(['', '']);
  });
});

describe('isValidNamePart', () => {
  it('chỉ nhận chữ cái (kể cả dấu tiếng Việt), khoảng trắng, dấu nháy, gạch nối; tối đa 50 ký tự; không nhận chuỗi rỗng', () => {
    expect(['Nguyễn', 'Minh Anh', "O'Brien", 'Jean-Luc', 'Đặng Thị Hồng'].map(isValidNamePart)).toEqual([true, true, true, true, true]);
    expect(['', 'test 01', 'An2', 'Anh@', 'Anh_Minh'].map(isValidNamePart)).toEqual([false, false, false, false, false]);
    expect(isValidNamePart('a'.repeat(50))).toBe(true);
    expect(isValidNamePart('a'.repeat(51))).toBe(false);
  });
});

