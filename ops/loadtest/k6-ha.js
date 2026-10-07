// Tải thử cho tầng app sau LB. Chạy: k6 run -e BASE_URL=http://<lb-ip> ops/loadtest/k6-ha.js
// Mục tiêu (docs/plan/2026-10-05-ha-load-balancing.md §5): p95 < 800ms, lỗi < 1%, autoscaler tăng
// số VM khi CPU > 60% và giảm lại sau khi hết tải. Kịch bản failover: xoá 1 VM giữa lúc chạy, lỗi vẫn < 1%.
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:3000';

export const options = {
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      startVUs: 5,
      stages: [
        { duration: '2m', target: 50 },
        { duration: '10m', target: 150 },
        { duration: '3m', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<800'],
  },
};

export default function () {
  const ready = http.get(`${BASE}/health/ready`);
  check(ready, { 'ready 200': (r) => r.status === 200 });
  const search = http.get(`${BASE}/api/v1/search?q=${encodeURIComponent('khách sạn Phú Quốc')}`);
  check(search, { 'search < 500': (r) => r.status < 500 });
  sleep(1);
}
