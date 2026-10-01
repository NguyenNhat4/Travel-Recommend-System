import React from 'react';

/** Màu ô hãng: chọn theo tên hãng nên một hãng luôn cùng màu; không dùng logo hay màu thương hiệu của hãng. */
const TINTS = [
  'bg-blue-700 text-blue-50',
  'bg-rose-700 text-rose-50',
  'bg-emerald-700 text-emerald-50',
  'bg-amber-600 text-amber-50',
  'bg-violet-700 text-violet-50',
  'bg-cyan-700 text-cyan-50',
];

function tintOf(name: string): string {
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return TINTS[hash % TINTS.length];
}

/** Ô chữ viết tắt của hãng (mã IATA khi có, không thì hai chữ cái đầu của tên). */
export const AirlineBadge: React.FC<{ name: string; code: string }> = ({ name, code }) => (
  <span aria-hidden="true"
    className={`inline-grid h-[22px] min-w-[42px] shrink-0 place-items-center rounded-md px-1.5 text-[11px] font-extrabold tracking-wider ${tintOf(name)}`}>
    {code || name.slice(0, 2).toUpperCase()}
  </span>
);
