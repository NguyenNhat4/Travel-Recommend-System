import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  // Nút "N" của Next.js đè lên khung chat trợ lý ở góc dưới; lỗi biên dịch/runtime vẫn hiện.
  devIndicators: false,
  images: {
    // Ảnh local trong public/ không đổi theo đường dẫn; cache tối ưu 7 ngày (mặc định Next chỉ 60 giây).
    minimumCacheTTL: 604800,
  },
};

export default nextConfig;
