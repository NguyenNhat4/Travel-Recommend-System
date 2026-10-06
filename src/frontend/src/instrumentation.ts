/**
 * Hook khởi động của Next.js: ghi `app.startup`/`app.shutdown` và `render.error` (docs/spec/logging-schema.md).
 * Chỉ chạy trên runtime Node; edge không có `process.on`.
 */
import type { Instrumentation } from 'next';

export async function register() {
  if (process.env.NEXT_RUNTIME !== 'nodejs') return;
  const { log } = await import('./lib/logger');
  log.info('app.startup', {
    message: 'frontend started',
    node_env: process.env.NODE_ENV,
    log_level: process.env.LOG_LEVEL || 'INFO',
    backend_configured: Boolean(process.env.BACKEND_BASE_URL),
  });
  for (const signal of ['SIGTERM', 'SIGINT'] as const) {
    process.once(signal, () => {
      log.info('app.shutdown', { signal });
      // Đã có handler của ta nên Node không tự thoát nữa; thoát sau khi dòng log được ghi.
      setTimeout(() => process.exit(0), 50).unref();
    });
  }
}

/** Lỗi render/route phía server. `digest` trùng với digest mà `app/error.tsx` hiển thị ở trình duyệt. */
export const onRequestError: Instrumentation.onRequestError = async (error, request, context) => {
  if (process.env.NEXT_RUNTIME !== 'nodejs') return;
  const { log, routeOf } = await import('./lib/logger');
  const digest = typeof error === 'object' && error !== null && 'digest' in error ? String(error.digest) : undefined;
  log.error('render.error', {
    route: context.routePath ?? routeOf(request.path.split('?')[0]),
    method: request.method,
    route_type: context.routeType,
    render_source: context.renderSource,
    digest,
    error,
  });
};
