import express from 'express';
import { registerHealthRoutes } from './routes/health';

const PORT = Number(process.env.PORT || 3001);

export function createApiApp() {
  const app = express();
  app.use(express.json());
  registerHealthRoutes(app);
  return app;
}

export function startServer() {
  const app = createApiApp();
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`X-OTA API Server running on http://0.0.0.0:${PORT}`);
  });
}
