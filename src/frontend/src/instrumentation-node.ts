/** Phần chỉ chạy trên Node: tách file để bundle edge không thấy `process.on`/`process.exit`. */
import { log } from './lib/logger';

export function registerNode() {
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
