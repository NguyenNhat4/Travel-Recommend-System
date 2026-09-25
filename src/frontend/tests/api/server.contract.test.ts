import { describe, expect, it } from 'vitest';
import { healthPayload } from '../../server/routes/health';

describe('V-OTA API contract', () => {
  it('returns the documented health response', () => {
    expect(healthPayload()).toMatchObject({
      status: 'ok',
      service: 'v-ota-recsys-demo',
    });
    expect(healthPayload().timestamp).toEqual(expect.any(String));
  });
});
