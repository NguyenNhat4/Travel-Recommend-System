import { describe, expect, it } from 'vitest';
import { highlightParts } from '../../src/features/search/instant/highlight';

const bold = (label: string, query: string) => highlightParts(label, query).filter((p) => p.match).map((p) => p.text);
const joined = (label: string, query: string) => highlightParts(label, query).map((p) => p.text).join('');

describe('highlightParts', () => {
  it('marks the matching start of each word, ignoring accents and case, and keeps the original text', () => {
    expect(highlightParts('Hà Nội', 'ha')).toEqual([{ text: 'Hà', match: true }, { text: ' Nội', match: false }]);
    expect(bold('Vinpearl Resort & Spa Hạ Long', 'HA')).toEqual(['Hạ']);
    expect(bold('Combo Hà Nội – Hạ Long 3N2Đ', 'ha lo')).toEqual(['Hà', 'Hạ', 'Lo']);
    expect(bold('Đà Nẵng', 'da n')).toEqual(['Đà', 'N']);
    expect(joined('Combo Hà Nội – Hạ Long 3N2Đ', 'ha lo')).toBe('Combo Hà Nội – Hạ Long 3N2Đ');
  });

  it('never marks the middle of a word', () => {
    expect(bold('Đêm nhạc Ký ức', 'ha')).toEqual([]);
    expect(bold('Hải Phòng', 'ha')).toEqual(['Hả']);
  });

  it('prefers the longest token and survives decomposed accents and empty queries', () => {
    expect(bold('VinWonders Nha Trang', 'vin vinw')).toEqual(['VinW']);
    expect(bold('Hạ Long'.normalize('NFD'), 'hạ')).toEqual(['Hạ']);
    expect(highlightParts('Hà Nội', '  ')).toEqual([{ text: 'Hà Nội', match: false }]);
  });
});
