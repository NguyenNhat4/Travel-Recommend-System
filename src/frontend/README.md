# V-OTA frontend

Next.js App Router frontend for the V-OTA travel application. Assistant requests are streamed through the same-origin Next.js BFF to the FastAPI backend; assistant conversations are not served by the local Express health server.

## Run Locally

**Prerequisites:** Node.js and the FastAPI backend running at `http://127.0.0.1:8000` (see [backend setup](../backend/README.md)).


1. Install dependencies: `npm install`
2. Copy `.env.example` to `.env.local`; set `BACKEND_BASE_URL` to the FastAPI base URL (default `http://127.0.0.1:8000`).
3. Run the frontend: `npm run dev` (Next.js on port 3000).

Auth goes through the Next.js BFF (`src/app/api/auth/*`, logic in `src/services/server/`): the browser only holds the HttpOnly `vota_sid` cookie and the readable `vota_csrf` cookie, never a token. Set `AUTH_SERVICE_TOKEN` to the same value as the backend and `SESSION_REDIS_URL` to the Redis from `docker compose up -d redis` (empty = in-memory store, dev only). All browser requests go through `src/services/http.ts` (`apiFetch`), which adds `X-CSRF-Token` on writes. Spec: `docs/spec/hop-dong-tich-hop-auth.md`.

The optional `npm run dev:api` process serves the independent Express health endpoint on port 3001. It is not an assistant backend. Regenerate OpenAPI types with `npm run generate:api-types` after contract updates.
