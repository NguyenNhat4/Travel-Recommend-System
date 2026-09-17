import type { Application } from 'express';

export function registerHealthRoutes(app: Application) {
  app.get('/api/health', (_req, res) => {
    res.json({
      status: 'ok',
      service: 'v-ota-recsys-demo',
      timestamp: new Date().toISOString(),
    });
  });
}
