import { fold } from '../../catalog/landing/searchHref';

export interface LabelPart {
  text: string;
  match: boolean;
}

const WORD = /[\p{L}\p{N}]+/gu;

/**
 * Tách nhãn thành đoạn thường và đoạn khớp để in đậm (FR-SRC-05). Cùng luật với Backend: khớp ở đầu từ, không phân
 * biệt dấu và hoa thường, nên gõ "ha" in đậm "Hà" trong "Hà Nội" và giữ nguyên dấu khi hiển thị.
 */
export function highlightParts(label: string, query: string): LabelPart[] {
  const tokens = fold(query).split(/[^a-z0-9]+/).filter(Boolean).sort((a, b) => b.length - a.length);
  const text = label.normalize('NFC');
  if (tokens.length === 0) return [{ text, match: false }];

  const parts: LabelPart[] = [];
  const push = (chunk: string, match: boolean) => {
    if (!chunk) return;
    const last = parts[parts.length - 1];
    if (last && last.match === match) last.text += chunk;
    else parts.push({ text: chunk, match });
  };

  let cursor = 0;
  for (const found of text.matchAll(WORD)) {
    const word = found[0];
    const start = found.index ?? 0;
    const folded = fold(word);
    const token = tokens.find((t) => folded.startsWith(t));
    push(text.slice(cursor, start), false);
    // Ký tự nào fold ra khác độ dài (hiếm) thì không đoán vị trí cắt, để nguyên từ.
    if (token && folded.length === word.length) {
      push(word.slice(0, token.length), true);
      push(word.slice(token.length), false);
    } else {
      push(word, false);
    }
    cursor = start + word.length;
  }
  push(text.slice(cursor), false);
  return parts;
}
