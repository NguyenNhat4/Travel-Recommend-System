import { Writable } from 'node:stream';
import { describe, expect, it } from 'vitest';
import { createLogger, redact, redactString, routeOf, timestamps } from '../../src/lib/logger';

function capture(level = 'debug') {
  const lines: string[] = [];
  const stream = new Writable({
    write(chunk, _enc, done) {
      lines.push(...String(chunk).split('\n').filter(Boolean));
      done();
    },
  });
  return { logger: createLogger(stream, level), lines, parsed: () => lines.map((l) => JSON.parse(l)) };
}

const JWT = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.c2lnbmF0dXJl';
const DSN = 'postgresql://vota:hunter2@10.0.0.5:5432/vota';

describe('logger schema', () => {
  it('ghi một dòng JSON có ts +07:00, ts_utc, severity, service, event', () => {
    const { logger, lines, parsed } = capture();
    logger.info('bff.proxy', { request_id: 'web-abc', method: 'GET', status: 200, upstream_ms: 12 });
    expect(lines).toHaveLength(1);
    const [row] = parsed();
    expect(row.severity).toBe('INFO');
    expect(row.service).toBe('frontend');
    expect(row.event).toBe('bff.proxy');
    expect(row.request_id).toBe('web-abc');
    expect(row.ts).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+07:00$/);
    expect(row.ts_utc).toMatch(/Z$/);
    expect(Date.parse(row.ts)).toBe(Date.parse(row.ts_utc));
    expect(row).not.toHaveProperty('pid');
    expect(row).not.toHaveProperty('level');
  });

  it('ánh xạ mức sang tên severity của Cloud Logging', () => {
    const { logger, parsed } = capture();
    logger.debug('a'); logger.info('b'); logger.warn('c'); logger.error('d'); logger.fatal('e');
    expect(parsed().map((r) => r.severity)).toEqual(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']);
  });

  it('LOG_LEVEL lọc dòng thấp hơn', () => {
    const { logger, parsed } = capture('warn');
    logger.debug('a'); logger.info('b'); logger.warn('c');
    expect(parsed().map((r) => r.event)).toEqual(['c']);
  });

  it('timestamps đổi sang giờ Hà Nội đúng', () => {
    expect(timestamps(Date.UTC(2026, 9, 6, 3, 49, 50, 955))).toEqual({
      ts: '2026-10-06T10:49:50.955+07:00', ts_utc: '2026-10-06T03:49:50.955Z',
    });
  });

  it('message là trường message, đã được làm sạch', () => {
    const { logger, parsed } = capture();
    logger.info('x.y', { message: 'login a@b.com thất bại' });
    expect(parsed()[0].message).toBe('login *** thất bại');
  });

  it('routeOf bỏ id khỏi đường dẫn', () => {
    expect(routeOf('/api/v1/bookings/VOTA-1234')).toBe('/api/v1/bookings/{id}');
    expect(routeOf('/api/v1/search')).toBe('/api/v1/search');
  });
});

describe('redact', () => {
  it('che khoá nhạy cảm và tên hành khách', () => {
    const out = redact({
      password: 'hunter2', accessToken: 'abc', Authorization: 'x', cookie: 'vota_sid=1', email: 'a@b.com',
      contact: { name: 'Nguyen Van A', note: 'ok' }, route: '/api/v1/search',
    }) as Record<string, any>;
    expect(out.password).toBe('***');
    expect(out.accessToken).toBe('***');
    expect(out.Authorization).toBe('***');
    expect(out.cookie).toBe('***');
    expect(out.email).toBe('***');
    expect(out.contact.name).toBe('***');
    expect(out.contact.note).toBe('ok');
    expect(out.route).toBe('/api/v1/search');
  });

  it('che mẫu giá trị trong chuỗi tự do', () => {
    for (const secret of [
      JWT, `Bearer ${JWT}`, 'Bearer abc.def-123', DSN, 'redis://:p4ss@redis:6379', 'user@example.com', '0912345678', '+84912345678',
      '4111111111111111', '4111 1111 1111 1111', 'sk_live_abcdef123456', 'pk_test_abcdef123456', 'whsec_abcdef123456',
    ]) {
      expect(redactString(`lỗi với ${secret} tại đây`), secret).not.toContain(secret);
    }
  });

  it('không che giá trị vô hại', () => {
    expect(redactString('GET /api/v1/search 200 in 35ms')).toBe('GET /api/v1/search 200 in 35ms');
  });

  it('stdout không chứa bí mật bơm vào bất kỳ trường nào', () => {
    const { logger, lines } = capture();
    logger.error('bff.proxy.upstream_error', {
      message: `kết nối ${DSN} lỗi, token ${JWT}`,
      password: 'hunter2',
      headers: { authorization: `Bearer ${JWT}`, cookie: 'vota_sid=s_secret' },
      nested: { contact_email: 'khach@example.com', card: '4111111111111111', cvv: '123', phone: '0912345678' },
      error: Object.assign(new Error(`ECONNREFUSED ${DSN} cho khach@example.com`), { stack: `Error: x\n at ${DSN}` }),
    });
    const out = lines.join('\n');
    for (const secret of ['hunter2', JWT, 'vota_sid=s_secret', 'khach@example.com', '4111111111111111', '0912345678']) {
      expect(out, secret).not.toContain(secret);
    }
    expect(out).toContain('ECONNREFUSED');
    expect(JSON.parse(lines[0]).error.type).toBe('Error');
  });
});
