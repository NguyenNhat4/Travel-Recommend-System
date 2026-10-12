import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  // Nút "N" của Next.js đè lên khung chat trợ lý ở góc dưới; lỗi biên dịch/runtime vẫn hiện.
  devIndicators: false,
};

export default nextConfig;
