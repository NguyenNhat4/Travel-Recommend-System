# V-OTA frontend

Next.js App Router frontend for the V-OTA travel application. Assistant requests are streamed through the same-origin Next.js BFF to the FastAPI backend; assistant conversations are not served by the local Express health server.

## Run Locally

Setup and run commands live in the [root README](../../README.md) (`make web` starts FastAPI and Next.js together). This file only describes frontend-specific details.

Auth goes through the Next.js BFF (`src/app/api/auth/*`, logic in `src/services/server/`): the browser only holds the HttpOnly `vota_sid` cookie and the readable `vota_csrf` cookie, never a token. Set `AUTH_SERVICE_TOKEN` to the same value as the backend and `SESSION_REDIS_URL` to the Redis from `docker compose up -d redis` (empty = in-memory store, dev only). All browser requests go through `src/services/http.ts` (`apiFetch`), which adds `X-CSRF-Token` on writes. Spec: `docs/spec/hop-dong-tich-hop-auth.md`.

Cart, checkout and booking pages call `/api/v1/cart*` and `/api/v1/bookings*` through the same BFF (`src/services/booking.ts`). Pressing **Thanh toán** creates a 30-minute hold and redirects the browser to Stripe Checkout (test mode); the backend needs the Stripe variables from `src/backend/README.md` (§Booking và thanh toán Stripe). Stripe returns to `/booking/{referenceCode}?payment=return`, which polls the booking until the webhook confirms it.

The optional `npm run dev:api` process serves the independent Express health endpoint on port 3001. It is not an assistant backend. Regenerate OpenAPI types with `npm run generate:api-types` after contract updates.

Catalog data comes only from the API (`src/services/catalog.ts`: `/products`, `/products/{id}`, `/products/{id}/similar`, `POST /events`); there is no local product catalog. Hotels (`level: property`) and flight routes (`level: route`) are view-only — the product page lists their rooms/flights via `GET /products?parentProductId=` and adds the chosen one to the cart. Missing images use `public/placeholders/<taxonomy>.svg`.
