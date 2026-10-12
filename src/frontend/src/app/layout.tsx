import type { Metadata } from 'next';
import Providers from './providers';
import './globals.css';

export const metadata: Metadata = {
  title: 'Sota - Nền tảng Du lịch Thông minh AI',
  description: 'Nền tảng du lịch cá nhân hóa Sota với gợi ý thông minh, tìm kiếm ngữ nghĩa và trợ lý lịch trình AI.',
  openGraph: {
    title: 'Sota - Nền tảng Du lịch Thông minh AI',
    description: 'Nền tảng du lịch cá nhân hóa Sota với gợi ý thông minh, tìm kiếm ngữ nghĩa và trợ lý lịch trình AI.',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* Cal Sans: tiêu đề và điều hướng (chỉ có một độ đậm). Inter: nội dung. Token ở globals.css. */}
        <link
          href="https://fonts.googleapis.com/css2?family=Cal+Sans&family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
