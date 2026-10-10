'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="min-h-screen flex items-center justify-center p-6">
      <div className="max-w-md text-center space-y-4">
        <h1 className="text-2xl font-black text-slate-900">Đã xảy ra lỗi</h1>
        <p className="text-slate-600">Vui lòng thử lại hoặc quay về trang chủ.</p>
        <button
          type="button"
          onClick={() => reset()}
          className="rounded-xl bg-brand-600 px-4 py-2 font-bold text-white"
        >
          Thử lại
        </button>
      </div>
    </main>
  );
}
