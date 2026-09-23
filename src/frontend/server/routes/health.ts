import type { Application } from 'express';

export function healthPayload() {
  return {
    status: 'ok',
    service: 'v-ota-recsys-demo',
    timestamp: new Date().toISOString(),
  };
}

export function registerHealthRoutes(app: Application) {
  app.get('/api/health', (_req, res) => {
    res.json(healthPayload());
  });
}
