import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { createApiApp } from '../../server/app';

const app = createApiApp();

describe('V-OTA API contract', () => {
  it('returns the documented health response', async () => {
    const response = await request(app).get('/api/health').expect(200);

    expect(response.body).toMatchObject({
      status: 'ok',
      service: 'v-ota-recsys-demo',
    });
    expect(response.body.timestamp).toEqual(expect.any(String));
  });

  it('keeps chat validation and fallback response shape', async () => {
    await request(app)
      .post('/api/assistant/chat')
      .send({})
      .expect(400);

    const response = await request(app)
      .post('/api/assistant/chat')
      .send({ message: 'Gợi ý lịch trình Nha Trang', locale: 'vi' })
      .expect(200);

    expect(response.body).toMatchObject({
      success: true,
      role: 'general',
      source: 'v-ota-fallback-assistant',
    });
    expect(response.body.reply).toEqual(expect.any(String));
    expect(response.body.suggestedFollowUps).toEqual(expect.any(Array));
  });

  it('keeps assistant plan fallback response shape', async () => {
    const response = await request(app)
      .post('/api/assistant/plan')
      .send({ prompt: 'Lên lịch trình', destination: 'Nha Trang', days: 3 })
      .expect(200);

    expect(response.body).toMatchObject({
      success: true,
      source: 'v-ota-grounded-engine',
    });
    expect(response.body.aiNarrative).toEqual(expect.any(String));
  });

  it('creates and retrieves shared trips through the store interface', async () => {
    const createResponse = await request(app)
      .post('/api/trips/share')
      .send({ plan: { title: 'Nha Trang demo' }, senderName: 'Khoa' })
      .expect(200);

    expect(createResponse.body.success).toBe(true);
    expect(createResponse.body.trip.views).toBe(1);

    const getResponse = await request(app)
      .get(`/api/trips/share/${createResponse.body.shareId}`)
      .expect(200);

    expect(getResponse.body.success).toBe(true);
    expect(getResponse.body.trip.views).toBe(2);
  });

  it('returns 404 for an unknown shared trip', async () => {
    await request(app)
      .get('/api/trips/share/does-not-exist')
      .expect(404);
  });
});
