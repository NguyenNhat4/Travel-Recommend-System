import { describe, expect, it } from 'vitest';
import { newDrafts } from '../../src/components/checkout/allocation';

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
