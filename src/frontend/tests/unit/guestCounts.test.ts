import { describe, expect, it } from 'vitest';
import type { CartState } from '../../src/components/checkout/allocation';
import {
  MAX_PACKAGES, canChange, capacityIssue, cartPayload, changeCount, guestModeOf, guestsText, initialCounts, isValidCounts,
  maxOccupancyFromAttributes, partyCartRequest, totalGuests,
} from '../../src/components/checkout/guestCounts';

const state = (adults: number, children: number, quantity = adults + children): CartState => ({ quantity, guests: { adults, children } });

describe('guestModeOf', () => {
  it('khách sạn theo phòng, combo theo gói, còn lại theo người', () => {
    expect(guestModeOf('hotel')).toBe('hotel');
    expect(guestModeOf('combo')).toBe('package');
    expect(['flight', 'attraction', 'golf'].map(guestModeOf)).toEqual(['person', 'person', 'person']);
  });
});

describe('dịch vụ tính theo người', () => {
  it('khởi đầu 1 người lớn; số lượng luôn bằng người lớn + trẻ em', () => {
    expect(initialCounts()).toEqual({ quantity: 1, guests: { adults: 1, children: 0 } });
    const next = changeCount('person', changeCount('person', state(1, 0), 'children', 1), 'adults', 1);
    expect(next).toEqual({ quantity: 3, guests: { adults: 2, children: 1 } });
  });

  it('người lớn ≥ 1, trẻ em ≥ 0, tổng ≤ 9; bộ đếm số lượng bị khoá', () => {
    expect(canChange('person', state(1, 0), 'adults', -1)).toBe(false);
    expect(canChange('person', state(1, 0), 'children', -1)).toBe(false);
    expect(canChange('person', state(5, 4), 'adults', 1)).toBe(false);
    expect(canChange('person', state(5, 4), 'children', 1)).toBe(false);
    expect(canChange('person', state(5, 4), 'children', -1)).toBe(true);
    expect(canChange('person', state(2, 1), 'quantity', 1)).toBe(false);
  });

  it('nút bị chặn thì trả nguyên trạng thái', () => {
    const full = state(5, 4);
    expect(changeCount('person', full, 'adults', 1)).toBe(full);
  });

  it('gửi guests và quantity = tổng số khách', () => {
    expect(cartPayload('person', state(2, 1))).toEqual({ quantity: 3, guests: { adults: 2, children: 1 } });
  });
});

describe('khách sạn', () => {
  it('số người lớn không xuống dưới số phòng; thêm phòng mà chưa đủ người lớn thì tự thêm một người lớn', () => {
    expect(canChange('hotel', state(2, 0, 2), 'adults', -1)).toBe(false);          // 2 phòng cần ≥ 2 người lớn
    const next = changeCount('hotel', state(1, 1, 1), 'quantity', 1);
    expect(next).toEqual({ quantity: 2, guests: { adults: 2, children: 1 } });
  });

  it('9 khách mỗi phòng: 2 phòng nhận tới 18 khách, 1 phòng không nhận khách thứ 10 (FR-BKG-08)', () => {
    expect(canChange('hotel', state(8, 1, 1), 'adults', 1)).toBe(false);          // 1 phòng đã đủ 9
    expect(canChange('hotel', state(8, 1, 2), 'adults', 1)).toBe(true);           // 2 phòng còn chỗ tới 18
    expect(canChange('hotel', state(10, 8, 2), 'children', 1)).toBe(false);       // 18/18
    expect(canChange('hotel', state(10, 7, 2), 'children', 1)).toBe(true);
    expect(isValidCounts('hotel', state(10, 8, 2), null)).toBe(true);
    expect(isValidCounts('hotel', state(10, 9, 2), null)).toBe(false);            // 19 khách cho 2 phòng
    expect(isValidCounts('hotel', state(10, 0, 1), null)).toBe(false);            // 10 khách cho 1 phòng
  });

  it('thêm phòng nâng trần: thêm được khi còn chỗ, hoặc đã có người lớn cho phòng mới', () => {
    expect(canChange('hotel', state(1, 8, 1), 'quantity', 1)).toBe(true);          // 9 khách < trần 18 của 2 phòng, tự thêm 1 người lớn
    expect(canChange('hotel', state(2, 7, 1), 'quantity', 1)).toBe(true);
    expect(changeCount('hotel', state(1, 8, 1), 'quantity', 1)).toEqual({ quantity: 2, guests: { adults: 2, children: 8 } });
  });

  it('tối đa 9 phòng; bớt phòng bị chặn khi số khách còn vượt trần của số phòng sau khi bớt', () => {
    expect(canChange('hotel', state(9, 0, 9), 'quantity', 1)).toBe(false);
    expect(isValidCounts('hotel', state(10, 0, 10), null)).toBe(false);
    expect(isValidCounts('hotel', state(45, 36, 9), null)).toBe(true);            // 81 khách, 9 phòng
    expect(canChange('hotel', state(10, 8, 2), 'quantity', -1)).toBe(false);      // 18 khách không vừa 1 phòng
    expect(canChange('hotel', state(5, 4, 2), 'quantity', -1)).toBe(true);        // 9 khách vừa 1 phòng
  });

  it('sức chứa hạng phòng lớn hơn 9 vẫn bị cắt ở 9 khách mỗi phòng', () => {
    expect(capacityIssue('hotel', state(10, 0, 1), 12)).toEqual({ capacity: 9, suggestedRooms: 2 });
    expect(isValidCounts('hotel', state(10, 8, 2), 12)).toBe(true);
  });

  it('bớt phòng giữ nguyên số khách; số phòng tối thiểu 1', () => {
    expect(changeCount('hotel', state(2, 1, 2), 'quantity', -1)).toEqual({ quantity: 1, guests: { adults: 2, children: 1 } });
    expect(canChange('hotel', state(1, 0, 1), 'quantity', -1)).toBe(false);
  });

  it('sức chứa: vượt C × số phòng thì báo cần thêm phòng; không có C thì không kiểm', () => {
    expect(capacityIssue('hotel', state(2, 2, 1), 3)).toEqual({ capacity: 3, suggestedRooms: 2 });
    expect(capacityIssue('hotel', state(2, 1, 1), 3)).toBeNull();
    expect(capacityIssue('hotel', state(4, 3, 1), null)).toBeNull();
    expect(capacityIssue('person', state(9, 0), 2)).toBeNull();
  });

  it('isValidCounts: cần người lớn cho mỗi phòng, không vượt sức chứa, tối đa 9 khách', () => {
    expect(isValidCounts('hotel', state(2, 1, 1), 3)).toBe(true);
    expect(isValidCounts('hotel', state(2, 2, 1), 3)).toBe(false);                 // vượt sức chứa
    expect(isValidCounts('hotel', state(1, 0, 2), 3)).toBe(false);                 // 2 phòng, 1 người lớn
    expect(isValidCounts('person', state(9, 1), null)).toBe(false);                // 10 khách
    expect(isValidCounts('person', state(0, 2), null)).toBe(false);                // không có người lớn
  });

  it('gửi số phòng và số khách', () => {
    expect(cartPayload('hotel', state(2, 1, 1))).toEqual({ quantity: 1, guests: { adults: 2, children: 1 } });
  });

  it('đọc sức chứa từ attributes', () => {
    expect(maxOccupancyFromAttributes({ maxOccupancy: 3 })).toBe(3);
    expect(maxOccupancyFromAttributes({ maxOccupancy: 0 })).toBeNull();
    expect(maxOccupancyFromAttributes({ maxOccupancy: '3' })).toBeNull();
    expect(maxOccupancyFromAttributes(undefined)).toBeNull();
  });
});

describe('combo', () => {
  it('chỉ chỉnh số gói (1…20), khách khoá; chỉ gửi quantity', () => {
    const one = initialCounts();
    expect(canChange('package', one, 'adults', 1)).toBe(false);
    expect(canChange('package', one, 'children', 1)).toBe(false);
    expect(canChange('package', one, 'quantity', -1)).toBe(false);
    expect(changeCount('package', one, 'quantity', 1).quantity).toBe(2);
    expect(canChange('package', { ...one, quantity: MAX_PACKAGES }, 'quantity', 1)).toBe(false);
    expect(cartPayload('package', { ...one, quantity: 2 })).toEqual({ quantity: 2 });
  });
});

describe('câu tóm tắt', () => {
  it('bỏ vế trẻ em khi không có trẻ em', () => {
    expect(guestsText({ adults: 2, children: 1 })).toBe('2 người lớn · 1 trẻ em');
    expect(guestsText({ adults: 2, children: 0 })).toBe('2 người lớn');
    expect(totalGuests(state(2, 1))).toBe(3);
  });
});

describe('partyCartRequest (trợ lý, spec §6.9)', () => {
  const party = { adults: 2, children: 1 };
  it('dịch vụ tính theo người: guests = đoàn, số lượng = tổng khách', () => {
    expect(partyCartRequest('attraction', party, null)).toEqual({ quantity: 3, guests: party });
    expect(partyCartRequest('flight', party, null)).toEqual({ quantity: 3, guests: party });
  });

  it('khách sạn: min(người lớn, max(1, ⌈khách / C⌉)) phòng; không có C thì 1 phòng', () => {
    expect(partyCartRequest('hotel', party, 2).quantity).toBe(2);                    // ⌈3/2⌉ = 2
    expect(partyCartRequest('hotel', party, 3).quantity).toBe(1);
    expect(partyCartRequest('hotel', { adults: 1, children: 2 }, 2).quantity).toBe(1);   // ⌈3/2⌉ = 2 nhưng chỉ có 1 người lớn: 1 phòng (Backend sẽ từ chối vì vượt sức chứa)
    expect(partyCartRequest('hotel', { adults: 4, children: 4 }, 2).quantity).toBe(4);   // ⌈8/2⌉ = 4 ≤ 4 người lớn
    expect(partyCartRequest('hotel', party, null).quantity).toBe(1);
    expect(partyCartRequest('hotel', party, 2).guests).toEqual(party);
  });

  it('khách sạn: đoàn đông được chia theo 9 khách mỗi phòng thay vì bị cắt ở 9', () => {
    expect(partyCartRequest('hotel', { adults: 10, children: 8 }, null)).toEqual({ quantity: 2, guests: { adults: 10, children: 8 } });
    expect(partyCartRequest('hotel', { adults: 3, children: 15 }, null)).toEqual({ quantity: 2, guests: { adults: 3, children: 15 } });
    expect(partyCartRequest('hotel', { adults: 1, children: 17 }, null)).toEqual({ quantity: 1, guests: { adults: 1, children: 8 } });
    expect(partyCartRequest('hotel', { adults: 40, children: 60 }, null)).toEqual({ quantity: 9, guests: { adults: 40, children: 41 } });
  });

  it('combo: 1 gói và guests = đoàn', () => {
    expect(partyCartRequest('combo', party, null)).toEqual({ quantity: 1, guests: party });
  });

  it('kéo đoàn về giới hạn: ≥ 1 người lớn, tối đa 9 khách, số nguyên', () => {
    expect(partyCartRequest('attraction', { adults: 12, children: 3 }, null)).toEqual({ quantity: 9, guests: { adults: 9, children: 0 } });
    expect(partyCartRequest('attraction', { adults: 0, children: 2 }, null).guests).toEqual({ adults: 1, children: 2 });
    expect(partyCartRequest('attraction', { adults: 6, children: 6 }, null).guests).toEqual({ adults: 6, children: 3 });
    expect(partyCartRequest('attraction', { adults: 2.7, children: -1 }, null).guests).toEqual({ adults: 2, children: 0 });
  });
});
