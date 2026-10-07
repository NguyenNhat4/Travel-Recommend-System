/**
 * Session store của BFF (docs/spec/hop-dong-tich-hop-auth.md §3.3, §16.1). CHỈ chạy phía server:
 * không import file này từ client component.
 *
 * Redis giữ phần phù du: `session:{sid}` (TTL = idle timeout), `lock:refresh:{sid}`,
 * `idx:user_sessions:{userId}`. Mất Redis = mọi người bị đăng xuất, chấp nhận được.
 * `MemorySessionStore` chỉ cho test và dev không có Redis; production bắt buộc SESSION_REDIS_URL.
 */
import { createClient } from 'redis';

export type SessionState = 'anonymous' | 'pending_mfa' | 'authenticated';

export interface SessionUser {
  userId: string;
  cdpUserId: string;
  email: string;
  fullName: string;
  /** Số điện thoại hồ sơ (FR-USR-04); vắng mặt khi chưa có. */
  phone?: string | null;
}

export interface SessionRecord {
  v: 1;
  state: SessionState;
  user: SessionUser | null;
  anonId: string | null;
  amr: string[];
  accessToken: string | null;
  accessTokenExp: number | null; // giây epoch
  refreshToken: string | null;
  csrfToken: string;
  createdAt: number;
  lastSeenAt: number;
  absoluteExp: number;
  uaHash: string;
}

export interface SessionStore {
  get(sid: string): Promise<SessionRecord | null>;
  set(sid: string, record: SessionRecord, ttlSeconds: number): Promise<void>;
  del(sid: string): Promise<void>;
  /** SET NX PX — khoá chống refresh đồng thời giữa nhiều tab (§3.4). */
  tryLock(key: string, ttlMs: number): Promise<boolean>;
  unlock(key: string): Promise<void>;
  addUserSession(userId: string, sid: string): Promise<void>;
  removeUserSession(userId: string, sid: string): Promise<void>;
  userSessions(userId: string): Promise<string[]>;
}

const sessionKey = (sid: string) => `session:${sid}`;
const userIndexKey = (userId: string) => `idx:user_sessions:${userId}`;

type RedisClient = ReturnType<typeof createClient>;

export class RedisSessionStore implements SessionStore {
  constructor(private readonly client: RedisClient) {}

  async get(sid: string) {
    const raw = await this.client.get(sessionKey(sid));
    return raw ? (JSON.parse(String(raw)) as SessionRecord) : null;
  }

  async set(sid: string, record: SessionRecord, ttlSeconds: number) {
    await this.client.set(sessionKey(sid), JSON.stringify(record), { EX: Math.max(1, Math.floor(ttlSeconds)) });
  }

  async del(sid: string) {
    await this.client.del(sessionKey(sid));
  }

  async tryLock(key: string, ttlMs: number) {
    return (await this.client.set(key, '1', { NX: true, PX: ttlMs })) === 'OK';
  }

  async unlock(key: string) {
    await this.client.del(key);
  }

  async addUserSession(userId: string, sid: string) {
    await this.client.sAdd(userIndexKey(userId), sid);
  }

  async removeUserSession(userId: string, sid: string) {
    await this.client.sRem(userIndexKey(userId), sid);
  }

  async userSessions(userId: string) {
    return [...(await this.client.sMembers(userIndexKey(userId)))].map(String);
  }
}

export class MemorySessionStore implements SessionStore {
  private readonly values = new Map<string, { value: string; expiresAt: number }>();
  private readonly sets = new Map<string, Set<string>>();

  constructor(private readonly now: () => number = () => Date.now()) {}

  private read(key: string) {
    const entry = this.values.get(key);
    if (!entry) return null;
    if (entry.expiresAt <= this.now()) {
      this.values.delete(key);
      return null;
    }
    return entry.value;
  }

  async get(sid: string) {
    const raw = this.read(sessionKey(sid));
    return raw ? (JSON.parse(raw) as SessionRecord) : null;
  }

  async set(sid: string, record: SessionRecord, ttlSeconds: number) {
    this.values.set(sessionKey(sid), { value: JSON.stringify(record), expiresAt: this.now() + ttlSeconds * 1000 });
  }

  async del(sid: string) {
    this.values.delete(sessionKey(sid));
  }

  async tryLock(key: string, ttlMs: number) {
    if (this.read(key) !== null) return false;
    this.values.set(key, { value: '1', expiresAt: this.now() + ttlMs });
    return true;
  }

  async unlock(key: string) {
    this.values.delete(key);
  }

  async addUserSession(userId: string, sid: string) {
    const set = this.sets.get(userIndexKey(userId)) ?? new Set<string>();
    set.add(sid);
    this.sets.set(userIndexKey(userId), set);
  }

  async removeUserSession(userId: string, sid: string) {
    this.sets.get(userIndexKey(userId))?.delete(sid);
  }

  async userSessions(userId: string) {
    return [...(this.sets.get(userIndexKey(userId)) ?? [])];
  }
}

// Một store cho cả tiến trình; giữ trên globalThis để HMR của `next dev` không mở thêm kết nối.
const globalStore = globalThis as unknown as { __votaSessionStore?: SessionStore; __votaSessionStoreReady?: Promise<SessionStore> };

export function setSessionStoreForTests(store: SessionStore | undefined) {
  globalStore.__votaSessionStore = store;
  globalStore.__votaSessionStoreReady = store ? Promise.resolve(store) : undefined;
}

export function getSessionStore(): Promise<SessionStore> {
  if (globalStore.__votaSessionStoreReady) return globalStore.__votaSessionStoreReady;
  const url = process.env.SESSION_REDIS_URL;
  if (!url) {
    if (process.env.NODE_ENV === 'production' && process.env.APP_ENV !== 'development') {
      throw new Error('SESSION_REDIS_URL là bắt buộc ở production');
    }
    console.warn(JSON.stringify({ event: 'session.store.memory', reason: 'SESSION_REDIS_URL trống' }));
    globalStore.__votaSessionStore = new MemorySessionStore();
    globalStore.__votaSessionStoreReady = Promise.resolve(globalStore.__votaSessionStore);
    return globalStore.__votaSessionStoreReady;
  }
  const client = createClient({ url });
  client.on('error', (error) => console.error(JSON.stringify({ event: 'session.store.error', message: String(error) })));
  globalStore.__votaSessionStoreReady = client.connect().then(() => {
    globalStore.__votaSessionStore = new RedisSessionStore(client as RedisClient);
    return globalStore.__votaSessionStore;
  }).catch((error) => {
    globalStore.__votaSessionStoreReady = undefined; // lần sau thử kết nối lại
    throw error;
  });
  return globalStore.__votaSessionStoreReady;
}
