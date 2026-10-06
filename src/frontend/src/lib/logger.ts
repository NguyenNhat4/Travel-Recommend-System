/**
 * Logger chung của Next.js (docs/spec/logging-schema.md). CHỈ chạy phía server.
 *
 * Mỗi sự kiện là một dòng JSON ra stdout: `ts` (giờ Hà Nội +07:00), `ts_utc`, `severity`, `service`, `event`,
 * `request_id`... Mọi trường đều đi qua `redact()` (mục 4 schema) trước khi ghi. Không dùng `console.*` trong
 * code server; gọi `log.info('bff.proxy', { ... })`.
 */
import { createHash } from 'node:crypto';
import pino, { type DestinationStream, type Logger } from 'pino';

export const MASK = '***';

// --- redact -------------------------------------------------------------------------------------

// Khoá bị che: không phân biệt hoa thường, khớp "chứa".
const SENSITIVE_KEYS = [
  'password', 'passwd', 'token', 'secret', 'authorization', 'cookie', 'api_key', 'apikey', 'dsn', 'connection',
  'email', 'phone', 'mobile', 'passport', 'idnumber', 'cccd', 'dob', 'birth', 'address', 'card', 'cvv', 'cvc', 'iban',
  'x-guest-id',
];
// `name` chỉ bị che khi nằm dưới nhánh hành khách/liên hệ.
const PERSON_BRANCH = /passenger|traveler|traveller|contact|guest|customer|holder|payer/i;
const NAME_KEYS = new Set(['name', 'fullname', 'full_name', 'firstname', 'lastname', 'first_name', 'last_name']);

// Thứ tự quan trọng: mẫu đặc thù trước mẫu chung.
const VALUE_PATTERNS: RegExp[] = [
  /[a-z][a-z0-9+.-]*:\/\/[^\s/:@]*:[^\s/@]+@[^\s'"]+/gi, // DSN scheme://user:pass@host
  /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*/g, // JWT
  /Bearer\s+[A-Za-z0-9._~+/=-]+/gi,
  /\b(?:sk|pk|rk|whsec)_[A-Za-z0-9_]{6,}/g,
  /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, // email
  /\b\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{1,7}\b/g, // thẻ có dấu cách
  /\b\d{13,19}\b/g, // thẻ liền
  /(?<![\w])(?:\+84|0)[ .-]?\d{2,3}[ .-]?\d{3}[ .-]?\d{3,4}(?![\w])/g, // số điện thoại VN
];

export function redactString(value: string): string {
  let out = value;
  for (const pattern of VALUE_PATTERNS) out = out.replace(pattern, MASK);
  return out;
}

function sensitiveKey(key: string, parentIsPerson: boolean): boolean {
  const lower = key.toLowerCase();
  if (SENSITIVE_KEYS.some((k) => lower.includes(k))) return true;
  return parentIsPerson && NAME_KEYS.has(lower);
}

/** Che đệ quy theo khoá rồi theo mẫu giá trị. Không đổi object gốc. */
export function redact(value: unknown, parentKey = '', depth = 0): unknown {
  if (value == null) return value;
  if (typeof value === 'string') return redactString(value);
  if (typeof value !== 'object') return value;
  if (depth > 8) return MASK;
  if (value instanceof Error) return serializeError(value);
  if (Array.isArray(value)) return value.map((item) => redact(item, parentKey, depth + 1));
  const personBranch = PERSON_BRANCH.test(parentKey);
  const out: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    out[key] = sensitiveKey(key, personBranch) ? MASK : redact(item, key, depth + 1);
  }
  return out;
}

/** `error.type/message/stack` đã làm sạch (DSN, URL có token, email trong message). */
export function serializeError(error: unknown): { type: string; message: string; stack?: string } {
  if (error instanceof Error) {
    return {
      type: error.name || 'Error',
      message: redactString(error.message),
      ...(error.stack ? { stack: redactString(error.stack) } : {}),
    };
  }
  return { type: 'Error', message: redactString(String(error)) };
}

/** Băm một định danh (user id, sid) để nối log mà không lộ giá trị gốc. */
export const hashId = (value: string | null | undefined): string | null =>
  value ? createHash('sha256').update(value).digest('hex').slice(0, 12) : null;

/** `/api/v1/bookings/VOTA-1234` → `/api/v1/bookings/{id}`: bỏ id khỏi đường dẫn để gom nhóm. */
export function routeOf(pathname: string): string {
  return pathname
    .split('/')
    .map((segment) => (!segment || /^v\d+$/.test(segment) ? segment
      : /\d/.test(segment) || segment.length >= 24 ? '{id}' : segment))
    .join('/');
}

// --- thời gian và mức log -----------------------------------------------------------------------

const HANOI_OFFSET_MS = 7 * 3600 * 1000;

export function timestamps(now = Date.now()): { ts: string; ts_utc: string } {
  return {
    ts: new Date(now + HANOI_OFFSET_MS).toISOString().replace('Z', '+07:00'),
    ts_utc: new Date(now).toISOString(),
  };
}

const SEVERITY: Record<string, string> = {
  trace: 'DEBUG', debug: 'DEBUG', info: 'INFO', warn: 'WARNING', error: 'ERROR', fatal: 'CRITICAL',
};
const LEVEL_NAMES: Record<string, string> = {
  DEBUG: 'debug', INFO: 'info', WARNING: 'warn', WARN: 'warn', ERROR: 'error', CRITICAL: 'fatal',
};

const configuredLevel = () => LEVEL_NAMES[(process.env.LOG_LEVEL || 'INFO').toUpperCase()] ?? 'info';

// --- logger -------------------------------------------------------------------------------------

export type LogFields = Record<string, unknown>;
type Level = 'debug' | 'info' | 'warn' | 'error' | 'fatal';

export interface AppLogger {
  debug(event: string, fields?: LogFields): void;
  info(event: string, fields?: LogFields): void;
  warn(event: string, fields?: LogFields): void;
  error(event: string, fields?: LogFields): void;
  fatal(event: string, fields?: LogFields): void;
}

export function createLogger(destination?: DestinationStream, level = configuredLevel()): AppLogger {
  const base: Logger = pino(
    {
      level,
      base: null, // không pid/hostname
      messageKey: 'message',
      timestamp: () => {
        const { ts, ts_utc } = timestamps();
        return `,"ts":"${ts}","ts_utc":"${ts_utc}"`;
      },
      formatters: { level: (label) => ({ severity: SEVERITY[label] ?? 'INFO' }) },
      // Lớp phòng thủ thứ hai cho đường dẫn nhạy cảm, kể cả khi ai đó gọi pino trực tiếp.
      redact: {
        paths: ['*.password', '*.token', '*.accessToken', '*.refreshToken', '*.authorization', '*.cookie',
          'headers.authorization', 'headers.cookie', 'req.headers.authorization', 'req.headers.cookie'],
        censor: MASK,
      },
    },
    // Mặc định ghi qua process.stdout (đồng bộ với pipe/file của container, và test chặn được).
    destination ?? { write: (line: string) => { process.stdout.write(line); } },
  );
  const emit = (lvl: Level, event: string, fields: LogFields = {}) => {
    if (!base.isLevelEnabled(lvl)) return;
    const { message, ...rest } = redact(fields) as LogFields;
    base[lvl]({ service: 'frontend', event, ...rest }, typeof message === 'string' ? message : undefined);
  };
  return {
    debug: (e, f) => emit('debug', e, f),
    info: (e, f) => emit('info', e, f),
    warn: (e, f) => emit('warn', e, f),
    error: (e, f) => emit('error', e, f),
    fatal: (e, f) => emit('fatal', e, f),
  };
}

export const log: AppLogger = createLogger();
