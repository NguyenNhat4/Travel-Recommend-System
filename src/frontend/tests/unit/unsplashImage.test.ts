import { describe, expect, it } from 'vitest';
import { UNSPLASH_DEFAULT_WIDTH, unsplashSrcSet, unsplashUrl } from '../../src/lib/unsplash';

const PHOTO = '1582719508461-905c673771fd';

describe('unsplashUrl', () => {
  it('dựng URL theo chiều rộng yêu cầu, giữ tham số chất lượng và định dạng tự động', () => {
    expect(unsplashUrl(PHOTO, 960)).toBe(
      `https://images.unsplash.com/photo-${PHOTO}?q=80&w=960&auto=format&fit=crop`,
    );
  });
});

describe('unsplashSrcSet', () => {
  it('liệt kê các cỡ từ nhỏ đến lớn, mỗi cỡ kèm đơn vị w để trình duyệt chọn theo viewport', () => {
    const entries = unsplashSrcSet(PHOTO).split(', ');
    expect(entries.map((entry) => entry.split(' ')[1])).toEqual(['640w', '960w', '1280w', '1920w']);
    expect(entries[0]).toBe(`${unsplashUrl(PHOTO, 640)} 640w`);
  });

  it('không có cỡ nào lớn hơn 2000 px, tức là không còn ảnh w=2000 mặc định cho mọi màn hình', () => {
    expect(unsplashSrcSet(PHOTO)).not.toContain('w=2000');
  });

  it('cỡ mặc định của src nằm trong srcSet', () => {
    expect(unsplashSrcSet(PHOTO)).toContain(`${unsplashUrl(PHOTO, UNSPLASH_DEFAULT_WIDTH)} ${UNSPLASH_DEFAULT_WIDTH}w`);
  });
});
