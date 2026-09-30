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
