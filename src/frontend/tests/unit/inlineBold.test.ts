import { describe, expect, it } from 'vitest';
import { splitBoldTitle } from '../../src/components/assistant/inlineBold';

describe('splitBoldTitle', () => {
  it('splits a bold first line from the rest', () => {
    expect(splitBoldTitle('**Ngày khởi hành không hợp lệ**\nNgày 28/09/2026 đã qua.\nChọn ngày khác nhé.')).toEqual({
      title: 'Ngày khởi hành không hợp lệ',
      body: 'Ngày 28/09/2026 đã qua.\nChọn ngày khác nhé.',
    });
  });

  it('leaves text without a bold first line untouched', () => {
    expect(splitBoldTitle('Bạn muốn đi đâu?')).toEqual({ title: null, body: 'Bạn muốn đi đâu?' });
    expect(splitBoldTitle('Xin chào **bạn**\nđi đâu?')).toEqual({ title: null, body: 'Xin chào **bạn**\nđi đâu?' });
  });

  it('accepts a title with no body', () => {
    expect(splitBoldTitle('**Chỉ có tiêu đề**')).toEqual({ title: 'Chỉ có tiêu đề', body: '' });
  });

  it('splits the fixed NO_RESULTS and FALLBACK messages the backend sends', () => {
    expect(splitBoldTitle('**Chưa tìm thấy sản phẩm phù hợp**\nMình chưa tìm thấy sản phẩm phù hợp trong dữ liệu hiện có.')).toEqual({
      title: 'Chưa tìm thấy sản phẩm phù hợp',
      body: 'Mình chưa tìm thấy sản phẩm phù hợp trong dữ liệu hiện có.',
    });
  });

  it('splits an out-of-scope error message the same way', () => {
    expect(splitBoldTitle('**Ngoài phạm vi hỗ trợ**\nTôi hỗ trợ tư vấn lịch trình du lịch.').title).toBe('Ngoài phạm vi hỗ trợ');
  });
});
