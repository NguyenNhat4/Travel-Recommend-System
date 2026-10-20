# Trang nhật ký HA hiển thị log của mọi service

- Ngày: 2026-10-14
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/monitor-log-tat-ca-service
- Trạng thái: dang dở (code, test, validate xong; chưa plan với state, chưa merge)
- Phạm vi: infra (staging-ha), scripts (allowlist CD)

## Mục tiêu

Trang `vota-ha HA: nhật ký` chỉ có bốn khung lọc sẵn (lỗi backend, request chậm, container dừng/OOM, job cào từ WARNING trở lên). Thiếu log của frontend, container khác và probe Patroni. Yêu cầu: trang hiển thị log của mọi service.

## Thay đổi

Khung log theo service, mọi mức, cộng khung lỗi gộp:

- Lỗi mọi service (ERROR trở lên), cả nhóm VM.
- Backend (mọi mức), frontend (mọi mức), job cào (mọi mức; trước đây chỉ WARNING trở lên).
- Container khác: stdout/stderr thô của container không in JSON (proxy, pgbouncer, Patroni). Lọc `logName:"docker_json" AND NOT jsonPayload.service:*`. Không có tên service trong các dòng này, chỉ có mã container trong đường dẫn file.
- Cụm DB Patroni: dòng probe mỗi phút (`patroni_cluster_probe`).
- Sự kiện container (dừng đột ngột / OOM, không tính helper) và request chậm > 1 s, giữ như cũ.

Tám khung log, trước là bốn. `dashboard.tf` có năm bộ lọc mới: `log_filter_all_errors`, `log_filter_frontend`, `log_filter_raw_containers`, `log_filter_patroni`; và `log_filter_crawler` bỏ điều kiện severity.

Không đưa syslog của VM vào trang: khối lượng lớn (khoảng 700 dòng mỗi giờ) và không phải service.

## Kiểm tra

- Mỗi bộ lọc mới trả về log thật trong giờ qua: frontend 171, job cào 8, container khác 83, probe Patroni 120. Không có dòng ERROR nào trong giờ đó.
- `test_dashboard.py` 23 OK; `test_alerts.py` OK.
- `terraform fmt -check -recursive`: sạch. `terraform validate`: kết quả ghi trong lần chạy cuối.
- Allowlist CD: thêm `google_monitoring_dashboard.ha_logs|update` có chú thích.

## Còn lại

- Plan chỉ đọc với state GCP (kỳ vọng: chỉ `ha_logs` đổi). Chưa chạy.
- Tám khung log trên một trang làm trang tải chậm hơn; có thể tách thêm nếu cần.
- Chưa merge. Sau merge, CD sẽ cập nhật trang này.
