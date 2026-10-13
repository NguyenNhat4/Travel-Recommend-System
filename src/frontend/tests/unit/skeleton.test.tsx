// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ProductCardSkeleton, SkeletonBlock, SkeletonStatus } from '../../src/components/common/Skeleton';

describe('Skeleton — khung chờ dùng chung (product.md §4.0)', () => {
  afterEach(cleanup);

  it('SkeletonStatus là một vùng trạng thái có tên, báo đang bận; các khối bên trong bị ẩn khỏi trình đọc màn hình', () => {
    render(
      <SkeletonStatus label="Đang tải giỏ hàng" className="grid gap-4">
        <SkeletonBlock className="h-4 w-20" />
        <SkeletonBlock />
      </SkeletonStatus>,
    );
    const status = screen.getByRole('status', { name: 'Đang tải giỏ hàng' });
    expect(status.getAttribute('aria-busy')).toBe('true');
    expect(status.className).toBe('grid gap-4');
    expect(status.textContent).toBe('Đang tải giỏ hàng');
    const blocks = status.querySelectorAll('.skeleton-wave');
    expect(blocks).toHaveLength(2);
    blocks.forEach((block) => expect(block.getAttribute('aria-hidden')).toBe('true'));
    expect(blocks[0].className).toBe('skeleton-wave h-4 w-20');
  });

  it('ProductCardSkeleton giữ khung thẻ grid: ảnh 16:10, hai dòng tên, giá; không có chữ hay liên kết', () => {
    const { container } = render(<ProductCardSkeleton />);
    const card = container.firstElementChild!;
    expect(card.getAttribute('aria-hidden')).toBe('true');
    expect(card.querySelector('.aspect-16\\/10')).toBeTruthy();
    expect(card.querySelectorAll('.skeleton-wave').length).toBeGreaterThanOrEqual(5);
    expect(card.textContent).toBe('');
    expect(card.querySelector('a, button')).toBeNull();
  });
});
