# Proxy staging-ha: nạp mime.types cho kho /_next/static

- Ngày: 2026-10-13
- Tác giả: hp09.com@gmail.com (yêu cầu) / Claude Code (agent)
- Nhánh: claude/proxy-mime-types
- Trạng thái: hoàn thành
- Phạm vi: infra (CI/CD)
- Liên quan: `2026-10-13-cd-staging-ha-mot-luong-hai-pha.md`, `2026-10-13-roll-script-qua-metadata.md`

## Mục tiêu

Sau lần deploy đầu tiên có kho tĩnh (App CD run 38347400998), kiểm `https://praxis.io.vn/_next/static/chunks/webpack-571154306a4310ab.js` thấy `content-type: text/plain`, `cf-cache-status: HIT`. `nginx.conf` của proxy không nạp `mime.types`.

Trình duyệt vẫn chạy JS (không có `nosniff`), nhưng sẽ từ chối CSS có MIME `text/plain`. CSS duy nhất của trang hiện tại (`7ddd19d7abf19ee1.css`) vẫn ra `text/css`, vì Cloudflare cache nó từ trước.

## File thay đổi

- `infra/terraform/environments/staging-ha/slot-deploy.sh` — sửa: `include /etc/nginx/mime.types; default_type application/octet-stream;` trong khối `http` của proxy.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — sửa: thêm test MIME.

## Quyết định

- Nạp `mime.types` có sẵn trong image `nginx:1.27-alpine`, đã kiểm trong container `vota-proxy` trên `vota-ha-app-fn9m`. Cấu hình mới có hiệu lực ở lần reload kế tiếp (pha switch của CD).

## Kiểm tra

- Test cấu trúc staging-ha: xem CI của PR. Kết quả sau CD: ghi trong báo cáo đánh giá ở phần trả lời của phiên làm việc.

## Còn lại / rủi ro

- Cloudflare đã cache vài chunk JS với `text/plain` và `max-age` 1 năm. JS vẫn chạy được, nhưng muốn sạch hẳn thì cần purge cache Cloudflare cho `/_next/static/*`. Agent không có quyền vào Cloudflare.
