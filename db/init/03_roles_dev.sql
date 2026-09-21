-- Login role cho môi trường DEV (docker-compose). KHÔNG dùng mật khẩu này ngoài local.
-- Hai connection string trong .env — backend không bao giờ dùng chung một connection cho app và CDP:
--   DATABASE_URL     = postgresql://vota_app_login:vota@localhost:5432/vota     (catalog + app, chỉ SELECT cdp.products)
--   CDP_DATABASE_URL = postgresql://cdp_client_login:cdp@localhost:5432/vota    (LocalCdpClient: cdp.* only)
\connect vota
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vota_app_login') THEN
        CREATE ROLE vota_app_login LOGIN PASSWORD 'vota' IN ROLE vota_app;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cdp_client_login') THEN
        CREATE ROLE cdp_client_login LOGIN PASSWORD 'cdp' IN ROLE cdp_writer;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cdp_eval_login') THEN
        CREATE ROLE cdp_eval_login LOGIN PASSWORD 'eval' IN ROLE cdp_reader;   -- evaluation: chỉ đọc CDP
    END IF;
END $$;
-- Insider clone service dùng superuser postgres trên database `insider` ở dev (service riêng, storage riêng).
