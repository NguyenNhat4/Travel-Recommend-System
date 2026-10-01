import { describe, expect, it } from 'vitest';
import partyInvalid from '../../../shared/mocks/booking/createBooking.400-party-invalid.json';
import { mapValidationFields, type ErrorContext } from '../../src/components/checkout/serverErrors';

const ctx: ErrorContext = {
  travelerRefs: ['t1', 't2', 't3'],
  cartItemIds: ['ci-hotel', 'ci-vinwonders', 'ci-vj601'],
  travelerLabels: { t1: 'Người lớn 1', t2: 'Người lớn 2', t3: 'Trẻ em 1' },
  itemNames: { 'ci-hotel': 'Lucky Sun Hotel', 'ci-vinwonders': 'Vé VinWonders', 'ci-vj601': 'VietJet Air VJ601' },
};
const fieldsOf = (body: typeof partyInvalid) => body.error.details.fields;

describe('mapValidationFields — đưa 400 VALIDATION_ERROR về đúng bước và đúng trường', () => {
  it('lỗi ở travelers[i] gắn vào ô của đúng hành khách và về bước ①', () => {
    const mapped = mapValidationFields([
      { field: 'travelers[2].birthDate', reason: 'CHILD_AGE_INVALID', message: 'Bé đã đủ 12 tuổi.' },
      { field: 'travelers[1].surname', reason: 'REQUIRED', message: 'Vui lòng nhập họ.' },
      { field: 'contact.phone', reason: 'PHONE_INVALID', message: 'Số điện thoại không hợp lệ.' },
    ], ctx);
    expect(mapped.step).toBe('travelers');
    expect(mapped.fieldErrors).toEqual({ 'dob-t3': 'Bé đã đủ 12 tuổi.', 'sn-t2': 'Vui lòng nhập họ.', 'c-phone': 'Số điện thoại không hợp lệ.' });
    expect(mapped.summary.map((e) => [e.targetId, e.where])).toEqual([
      ['dob-t3', 'Trẻ em 1 · Ngày sinh'], ['sn-t2', 'Người lớn 2 · Họ'], ['c-phone', 'Người liên hệ · Số điện thoại']]);
  });

  it('FR-BKG-13: lỗi ở travelers[i].documents.* gắn vào đúng ô thông tin bay của hành khách và về bước ①', () => {
    const mapped = mapValidationFields([
      { field: 'travelers[0].documents.title', reason: 'REQUIRED', message: 'Chọn danh xưng.' },
      { field: 'travelers[0].documents.docNumber', reason: 'DOC_NUMBER_INVALID', message: 'Số CCCD gồm 12 chữ số.' },
      { field: 'travelers[1].documents.docExpiry', reason: 'DOC_EXPIRED', message: 'Hộ chiếu hết hạn trước ngày bay cuối cùng (19/10/2026).' },
      { field: 'travelers[2].documents.escortTravelerRef', reason: 'REQUIRED', message: 'Chọn người lớn đi kèm em bé.' },
      { field: 'travelers[1].birthDate', reason: 'ADULT_AGE_INVALID', message: 'Người lớn phải từ 12 tuổi tại ngày bay 19/10/2026.' },
    ], ctx);
    expect(mapped.step).toBe('travelers');
    expect(mapped.fieldErrors).toMatchObject({
      'x-title-t1': 'Chọn danh xưng.', 'x-docNo-t1': 'Số CCCD gồm 12 chữ số.', 'x-exp-t2': expect.stringContaining('Hộ chiếu hết hạn'),
      'x-with-t3': 'Chọn người lớn đi kèm em bé.', 'dob-t2': expect.stringContaining('từ 12 tuổi') });
    expect(mapped.summary.map((e) => e.where)).toEqual([
      'Người lớn 1 · Danh xưng', 'Người lớn 1 · Số giấy tờ', 'Người lớn 2 · Ngày hết hạn hộ chiếu', 'Trẻ em 1 · Người lớn đi kèm em bé', 'Người lớn 2 · Ngày sinh']);
  });

  it('lỗi ở itemDetails[j] gắn vào thẻ (hoặc phòng) của đúng dịch vụ và về bước ②', () => {
    const mapped = mapValidationFields([
      { field: 'itemDetails[0].rooms[1]', reason: 'OCCUPANCY_EXCEEDED', message: 'Phòng 2 chứa tối đa 3 khách.', cartItemId: 'ci-hotel' },
      { field: 'itemDetails[1]', reason: 'ITEM_WITHOUT_TRAVELER', message: 'Chọn ít nhất 1 khách.' },
    ], ctx);
    expect(mapped.step).toBe('services');
    expect(mapped.roomErrors).toEqual({ 'ci-hotel': { 1: ['Phòng 2 chứa tối đa 3 khách.'] } });
    expect(mapped.itemErrors).toEqual({ 'ci-vinwonders': ['Chọn ít nhất 1 khách.'] });   // cartItemId suy từ chỉ số khi Backend không gửi kèm
    expect(mapped.summary.map((e) => e.targetId)).toEqual(['room-ci-hotel-1', 'card-ci-vinwonders']);
    expect(mapped.mismatchedItems).toEqual([]);
  });

  it('lỗi ở cả hai bước: về bước sớm nhất và chỉ liệt kê lỗi của bước đó trong hộp tóm tắt', () => {
    const mapped = mapValidationFields(fieldsOf(partyInvalid), ctx);
    expect(mapped.step).toBe('travelers');
    expect(mapped.summary).toHaveLength(1);
    expect(mapped.summary[0].targetId).toBe('dob-t3');
    // lỗi của bước ② vẫn được giữ lại để hiện khi khách tới đó
    expect(mapped.roomErrors['ci-hotel'][0]).toEqual(['Phòng 1 chứa tối đa 3 khách.']);
    expect(mapped.mismatchedItems).toEqual(['ci-vj601']);
  });

  it('GUEST_COUNT_MISMATCH được đánh dấu để Web tải lại giỏ và tính lại phân bổ', () => {
    const mapped = mapValidationFields([
      { field: 'itemDetails[2]', reason: 'GUEST_COUNT_MISMATCH', message: 'Số khách vừa thay đổi.', cartItemId: 'ci-vj601' }], ctx);
    expect(mapped.step).toBe('services');
    expect(mapped.mismatchedItems).toEqual(['ci-vj601']);
  });

  it('lỗi không định vị được thì không có bước đích', () => {
    const mapped = mapValidationFields([{ field: 'unknown', reason: 'X', message: 'Lạ.' }], ctx);
    expect(mapped.step).toBeNull();
    expect(mapped.summary).toEqual([]);
  });

  it('lỗi ở cả đoàn (`travelers`) trỏ về bộ đếm số khách', () => {
    const mapped = mapValidationFields([{ field: 'travelers', reason: 'PARTY_TOO_LARGE', message: 'Tối đa 9 khách.' }], ctx);
    expect(mapped.step).toBe('travelers');
    expect(mapped.fieldErrors['party-counters']).toBe('Tối đa 9 khách.');
  });
});
