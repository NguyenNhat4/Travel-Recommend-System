import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts', 'tests/**/*.test.tsx'],
    environment: 'node',
    clearMocks: true,
    // CI chạy cả bộ song song; các test polling/render thật vượt 5 s mặc định dưới tải (2026-10-12).
    testTimeout: 20000,
  },
});
