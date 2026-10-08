import { describe, expect, it } from 'vitest';
import { PANEL_CLASS, chipClass, controlClass, primaryClass, rowClass } from '../../src/components/layout/nav/headerStyles';

/**
 * Khóa hệ kích thước của header: mọi điều khiển cùng cao 40 px (44 px trên màn cảm ứng), bo tròn hoàn toàn, chữ Cal Sans.
 * Nếu ai thêm một điều khiển với `rounded-lg` hay chiều cao riêng thì test này nhắc lại lý do có hệ chung.
 */
const controls: Record<string, string> = {
  'group overlay': controlClass('overlay'),
  'group solid': controlClass('solid'),
  'group active': controlClass('solid', { active: true }),
  'locale (compact)': controlClass('overlay', { compact: true }),
  'icon-only': controlClass('solid', { iconOnly: true }),
  'account chip overlay': chipClass('overlay'),
  'account chip solid': chipClass('solid'),
  primary: primaryClass(),
};

describe('header controls share one size system', () => {
  it.each(Object.entries(controls))('%s is 40 px tall (44 px on touch), fully rounded, Cal Sans', (_name, cls) => {
    expect(cls).toMatch(/(^| )h-10( |$)/);
    expect(cls).toContain('pointer-coarse:h-11');
    expect(cls).toMatch(/(^| )rounded-full( |$)/);
    expect(cls).toMatch(/(^| )font-display( |$)/);
    expect(cls).not.toMatch(/rounded-(lg|xl|2xl|md)\b/);
  });

  it('icon-only controls are circles of the same height', () => {
    expect(controls['icon-only']).toContain('w-10');
    expect(controls['icon-only']).not.toMatch(/(^| )px-/);
  });

  it('text controls use 12 px padding, 16 px from xl, so the 1024–1279 px range fits', () => {
    expect(controls['group solid']).toContain('px-3 xl:px-4');
  });

  it('only the primary action is filled blue', () => {
    expect(primaryClass()).toContain('bg-brand-600');
    for (const [name, cls] of Object.entries(controls)) if (name !== 'primary') expect(cls).not.toContain('bg-brand-600');
  });
});

describe('dropdown panels', () => {
  it('share one shell: 24 px corners, 8 px padding, concentric 16 px rows at least 44 px tall', () => {
    expect(PANEL_CLASS).toContain('rounded-3xl');
    expect(PANEL_CLASS).toMatch(/(^| )p-2( |$)/);
    for (const variant of ['default', 'selected', 'accent', 'danger'] as const) {
      const row = rowClass(variant);
      expect(row).toContain('rounded-2xl');
      expect(row).toContain('min-h-11');
    }
  });
});
