import { describe, expect, it } from 'vitest';
import { parseAssistantText, splitBoldTitle } from '../../src/components/assistant/inlineBold';

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

describe('parseAssistantText', () => {
  it('splits plain text, bold headings and product links in order', () => {
    expect(parseAssistantText('**Ngày 1**\n• Cả ngày — [Tour Ninh Bình](product:t1) (850.000 ₫).')).toEqual([
      { kind: 'bold', text: 'Ngày 1' },
      { kind: 'text', text: '\n• Cả ngày — ' },
      { kind: 'product', text: 'Tour Ninh Bình', productId: 't1' },
      { kind: 'text', text: ' (850.000 ₫).' },
    ]);
  });

  it('reads bold inside text around several links', () => {
    const parts = parseAssistantText('[A](product:a) và **B** rồi [C](product:c)');
    expect(parts.filter((part) => part.kind === 'product').map((part) => part.kind === 'product' && part.productId)).toEqual(['a', 'c']);
    expect(parts.some((part) => part.kind === 'bold' && part.text === 'B')).toBe(true);
  });

  it('leaves other markdown and raw html as plain text', () => {
    expect(parseAssistantText('[link](https://x.test) <b>x</b> [a](product:)')).toEqual([
      { kind: 'text', text: '[link](https://x.test) <b>x</b> [a](product:)' },
    ]);
  });

  it('reads a saved link whose catalog name has square brackets', () => {
    const text = '• Buổi sáng, [[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)](product:e35d0af0-91c4-55b8-a74f-aaaffea153f8) nhé.';
    expect(parseAssistantText(text)).toEqual([
      { kind: 'text', text: '• Buổi sáng, ' },
      { kind: 'product', text: 'Grand World Phú Quốc - Vé đi thuyền Venice (Water Taxi)', productId: 'e35d0af0-91c4-55b8-a74f-aaaffea153f8' },
      { kind: 'text', text: ' nhé.' },
    ]);
  });

  it('returns no parts for empty text', () => {
    expect(parseAssistantText('')).toEqual([]);
  });
});
