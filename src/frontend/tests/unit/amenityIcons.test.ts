import { Bath, Check, DoorOpen, Lock, Snowflake, ShowerHead, Tv, Utensils, Waves, Wifi } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import { amenityIcon, pickHighlights } from '../../src/components/detail/amenityIcons';

describe('amenityIcon', () => {
  it('nhận ra tiện ích theo chữ tiếng Việt, không phân biệt dấu và kiểu dấu thanh', () => {
    expect(amenityIcon('Wifi miễn phí')).toBe(Wifi);
    expect(amenityIcon('Điều hoà không khí')).toBe(Snowflake);
    expect(amenityIcon('Điều hòa nhiệt độ')).toBe(Snowflake);
    expect(amenityIcon('Bồn tắm')).toBe(Bath);
    expect(amenityIcon('Vòi sen đứng')).toBe(ShowerHead);
    expect(amenityIcon('TV màn hình phẳng')).toBe(Tv);
    expect(amenityIcon('Truyền hình cáp/vệ tinh')).toBe(Tv);
    expect(amenityIcon('Ban công/Sân hiên')).toBe(DoorOpen);
    expect(amenityIcon('Két an toàn')).toBe(Lock);
    expect(amenityIcon('Bể bơi ngoài trời')).toBe(Waves);
    expect(amenityIcon('Bữa sáng rất tốt')).toBe(Utensils);
  });

  it('không nhận nhầm "cản sáng" là "ăn sáng"; chữ lạ thì dấu tích', () => {
    expect(amenityIcon('Rèm cản sáng')).toBe(Check);
    expect(amenityIcon('Giữ hành lý')).toBe(Check);
    expect(amenityIcon('')).toBe(Check);
  });
});

describe('pickHighlights', () => {
  const items = ['Két an toàn', 'Điện thoại', 'Wifi miễn phí', 'Ấm đun nước', 'Truyền hình cáp/vệ tinh', 'Wi-Fi ở sảnh', 'Điều hoà không khí',
    'Bồn tắm', 'Vòi sen đứng', 'Giữ hành lý'];

  it('lấy tiện ích quan trọng trước, mỗi loại icon một lần, tối đa theo giới hạn', () => {
    expect(pickHighlights(items, 5)).toEqual(['Wifi miễn phí', 'Điều hoà không khí', 'Bồn tắm', 'Vòi sen đứng', 'Truyền hình cáp/vệ tinh']);
    expect(pickHighlights(items, 2)).toEqual(['Wifi miễn phí', 'Điều hoà không khí']);
  });

  it('không có tiện ích nhận ra được thì rỗng', () => {
    expect(pickHighlights(['Giữ hành lý', 'Dịch vụ đánh thức'])).toEqual([]);
    expect(pickHighlights([])).toEqual([]);
  });
});
