# Frontend

Vị trí dành cho Next.js (App Router) + TypeScript + Tailwind CSS app. Code UI đặt trong `src/`, tổ chức theo feature; routing/layout đặt trong `src/app`; API types/client phải được sinh từ `../shared/contracts/openapi.yaml`.

Hợp đồng dữ liệu phía Web: `docs/spec/hop-dong-tich-hop-frontend.md`.

Sinh kiểu API (không sửa tay file sinh ra):

```bash
npx openapi-typescript ../shared/contracts/openapi.yaml -o src/types/api.gen.ts
```

Mock: bật `NEXT_PUBLIC_API_MOCK=1`, tầng `src/services` đọc fixture theo `../shared/mocks/index.json`; chọn ca biên bằng `?mock=<case>`.
