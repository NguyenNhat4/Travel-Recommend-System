import { describe, expect, it } from 'vitest';
import { newDrafts, ticketName, toTravelerInputs } from '../../src/components/checkout/allocation';

describe('newDrafts — đoàn mặc định (spec §6.5)', () => {
  it('Người lớn 1 lấy họ tên từ tài khoản, các ô khác để trống, người lớn trước trẻ em', () => {
    const { drafts, seq } = newDrafts({ adults: 2, children: 1 }, 'Nguyễn Minh Anh');
    expect(seq).toBe(3);
    expect(drafts.map((d) => [d.ref, d.type, d.surname, d.givenNames, d.birthText])).toEqual([
      ['t1', 'ADULT', 'Nguyễn', 'Minh Anh', ''],
      ['t2', 'ADULT', '', '', ''],
      ['t3', 'CHILD', '', '', '']]);
  });

  it('tên tài khoản không dùng được làm họ tên trên giấy tờ (chữ số, một từ, ký hiệu) thì để trống cả hai ô', () => {
    for (const name of ['Khách test 01', 'Minh', '', 'An@ Bình', '  ']) {
      const { drafts } = newDrafts({ adults: 1, children: 0 }, name);
      expect([name, drafts[0].surname, drafts[0].givenNames]).toEqual([name, '', '']);
    }
  });

  it('chuẩn hoá khoảng trắng thừa trong tên tài khoản', () => {
    expect(newDrafts({ adults: 1, children: 0 }, '  Trần   Thu  Hà ').drafts[0]).toMatchObject({ surname: 'Trần', givenNames: 'Thu Hà' });
  });
});

describe('toTravelerInputs — khối giấy tờ cho vé máy bay (FR-BKG-13)', () => {
  const filled = () => {
    const { drafts } = newDrafts({ adults: 1, children: 1 }, 'Nguyễn Minh Anh');
    drafts[0].birthText = '14/03/1988';
    drafts[0].flight = { title: 'MS', nationality: 'KR', docType: 'PASSPORT', docNumber: ' c1234567 ', docExpiryText: '01/01/2031', escortRef: '' };
    drafts[1].birthText = '03/03/2025';
    drafts[1].flight = { title: 'MISS', nationality: 'VN', docType: 'CCCD', docNumber: 'không gửi', docExpiryText: '', escortRef: 't1' };
    return drafts;
  };

  it('không có vé bay thì không gửi giấy tờ và người lớn không gửi ngày sinh', () => {
    const [adult, child] = toTravelerInputs(filled());
    expect(adult).toEqual({ travelerRef: 't1', type: 'ADULT', surname: 'Nguyễn', givenNames: 'Minh Anh', birthDate: null });
    expect(child.birthDate).toBe('2025-03-03');
    expect(child).not.toHaveProperty('documents');
  });

  it('có vé bay: người lớn gửi ngày sinh ISO, loại và số giấy tờ, hạn hộ chiếu; trẻ em chỉ gửi danh xưng, quốc tịch, người đi kèm', () => {
    const [adult, child] = toTravelerInputs(filled(), true);
    expect(adult.birthDate).toBe('1988-03-14');
    expect(adult.documents).toEqual({ title: 'MS', nationality: 'KR', docType: 'PASSPORT', docNumber: 'c1234567', docExpiry: '2031-01-01' });
    expect(child.documents).toEqual({ title: 'MISS', nationality: 'VN', escortTravelerRef: 't1' });
  });

  it('ô còn trống thì bỏ khỏi request để Backend báo REQUIRED đúng trường; CCCD không gửi ngày hết hạn', () => {
    const { drafts } = newDrafts({ adults: 1, children: 0 }, 'Nguyễn Minh Anh');
    drafts[0].flight.docExpiryText = '01/01/2031';
    const [adult] = toTravelerInputs(drafts, true);
    expect(adult.documents).toEqual({ nationality: 'VN', docType: 'CCCD' });
  });
});

describe('ticketName', () => {
  it('bỏ dấu, viết hoa, tiếng Việt có đ', () => {
    expect(ticketName({ surname: 'Đặng', givenNames: 'Thu  Hà' })).toBe('DANG / THU HA');
    expect(ticketName({ surname: '', givenNames: '' })).toBe('— / —');
  });
});
