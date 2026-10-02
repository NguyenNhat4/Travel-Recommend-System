import React from 'react';

/** Dòng đầu dạng `**Tiêu đề**` (backend dùng cho câu báo giá trị không hợp lệ) tách khỏi phần thân. */
export function splitBoldTitle(text: string): { title: string | null; body: string } {
  const [first, ...rest] = text.split('\n');
  const match = /^\*\*(.+)\*\*$/.exec(first.trim());
  return match ? { title: match[1].trim(), body: rest.join('\n').replace(/^\n+/, '') } : { title: null, body: text };
}

/** Hiển thị `**đậm**` thành chữ đậm; chỉ tạo React node, không chèn HTML thô. */
export function InlineBold({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*\n]+\*\*)/g).map((part, index) => (
        /^\*\*[^*\n]+\*\*$/.test(part)
          ? <strong key={index} className="font-bold">{part.slice(2, -2)}</strong>
          : <React.Fragment key={index}>{part}</React.Fragment>
      ))}
    </>
  );
}

export type AssistantTextPart =
  | { kind: 'text'; text: string }
  | { kind: 'bold'; text: string }
  | { kind: 'product'; text: string; productId: string };

// Nhãn chịu được một tầng ngoặc vuông: tin nhắn đã lưu trước bản vá 01/10 có tên catalog dạng
// "[[Grand World Phú Quốc] - Vé…](product:id)"; backend nay đã bỏ ngoặc khỏi tên trước khi dựng link.
const PRODUCT_LINK = /\[((?:[^[\]\n]|\[[^[\]\n]*\]){1,200})\]\(product:([^()\s]{1,200})\)/g;

/** Tách câu trợ lý thành chữ thường, `**đậm**` và link sản phẩm `[Tên](product:id)` (lời diễn giải lịch trình). */
export function parseAssistantText(text: string): AssistantTextPart[] {
  const parts: AssistantTextPart[] = [];
  const pushText = (chunk: string) => {
    for (const piece of chunk.split(/(\*\*[^*\n]+\*\*)/g)) {
      if (!piece) continue;
      parts.push(/^\*\*[^*\n]+\*\*$/.test(piece) ? { kind: 'bold', text: piece.slice(2, -2) } : { kind: 'text', text: piece });
    }
  };
  let last = 0;
  for (const match of text.matchAll(PRODUCT_LINK)) {
    pushText(text.slice(last, match.index));
    parts.push({ kind: 'product', text: match[1].replace(/[[\]]/g, ' ').replace(/\s+/g, ' ').trim(), productId: match[2] });
    last = (match.index ?? 0) + match[0].length;
  }
  pushText(text.slice(last));
  return parts;
}

/**
 * Như `InlineBold`, thêm link sản phẩm: có `onProduct` thì tên sản phẩm là nút focus thẻ đó ở khung lịch trình,
 * không có thì chỉ hiện tên. Chỉ tạo React node, không chèn HTML thô.
 */
export function AssistantText({ text, onProduct, plainIds }: {
  text: string;
  onProduct?: (productId: string) => void;
  /** Sản phẩm đã có thẻ ngay dưới lời diễn giải: tên chỉ in đậm, không làm link (thẻ là chỗ bấm). */
  plainIds?: ReadonlySet<string>;
}) {
  return (
    <>
      {parseAssistantText(text).map((part, index) => {
        if (part.kind === 'bold') return <strong key={index} className="font-bold">{part.text}</strong>;
        if (part.kind === 'text') return <React.Fragment key={index}>{part.text}</React.Fragment>;
        return onProduct && !plainIds?.has(part.productId) ? (
          <button key={index} type="button" onClick={() => onProduct(part.productId)}
            className="inline text-left font-semibold text-blue-700 underline decoration-blue-300 underline-offset-2 hover:text-blue-900">
            {part.text}
          </button>
        ) : <span key={index} className="font-semibold">{part.text}</span>;
      })}
    </>
  );
}
