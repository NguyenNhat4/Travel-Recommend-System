# Cold-start gợi ý: tối đa 2 món mỗi taxonomy

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành (bench HTTP chưa chạy được, xem "Còn lại")
- Phạm vi: backend, docs
- Liên quan: `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` (quyết định 6)

## Mục tiêu

`_top_products` của cold-start `/recommendations` xếp theo lượt mua mà không có trần theo taxonomy. Vì lượt mua chuyến bay dồn về tuyến, 2 món đầu ở Phú Quốc, Đà Nẵng, Nha Trang và Đà Lạt đều là tuyến bay. Người dùng chốt sửa lỗi lệch này cùng đợt với kệ Phổ biến. Spec §4.8 vốn đã ghi "tối đa 2 mỗi taxonomy" cho nhánh toàn hệ thống, nhưng code chưa làm. Phục vụ FR-REC-01 (khách chưa có lịch sử: phổ biến theo điểm đến) và chỉ số Diversity ở test-plan §2.5.

## File thay đổi

- `src/backend/app/application/recommendation/use_cases.py` — sửa:
  - thêm helper `_cap_per_taxonomy(order, taxonomy, k, cap)`;
  - áp trần `self.max_per_vertical` vào `_top_products`, vào danh sách phẳng ghép từ các section, và vào nhánh `reviewCount`.
- `src/backend/tests/unit/application/test_recommendation_cold_start_cap.py` — thêm, 4 test:
  - có `destination`: tối đa 2 tuyến bay, giữ thứ tự popular;
  - chế độ eval (`None`) giữ thứ tự cũ;
  - danh sách ghép từ nhiều section cũng có trần;
  - nhánh `reviewCount` có trần.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §4.8 thêm trần cho nhánh có `destination`, và đoạn giải thích phạm vi áp trần.
- `history/2026-10-12-cold-start-toi-da-2-moi-taxonomy.md` — thêm: entry này.

## Quyết định

- **Dùng `self.max_per_vertical`** (= `MAX_PER_VERTICAL` = 2 ở production; `None` ở harness eval), không thêm hằng chữ hoa vào `profile.py`. Lý do: bench băm các hằng đó vào `configHash`, nên `regress` với baseline_v6 sẽ báo lệch cấu hình. Chế độ eval của bench không đổi.
- **Trần theo taxonomy của engine:** golf là taxonomy riêng, giống nhánh cá nhân hoá (`mmr_select`). Đây không phải các nhóm của `diversify` ở `/products`.
- **Có thể trả ít hơn k món** khi điểm đến chỉ có một loại, giống `mmr_select` ở nhánh cá nhân hoá.
- **Nhánh cá nhân hoá không đổi.** Chỉ các khách chưa có chuyến, khách vãng lai và đường lui khi CDP lỗi đi qua code này.

## Kiểm tra

- `pytest -q -p no:cacheprovider src/backend/tests/unit/application/test_recommendation_cold_start_cap.py`: 4 passed.
- Các test recommendation, engine và cold-start trong `src/backend/tests/unit/application` và `unit/domain` (`-k "recommend or engine or cold"`): 46 passed.
- `pytest -q src/evaluation/recsys_bench/tests` (gồm parity trong tiến trình `test_parity.py`): 186 passed, 6 skipped (các test cần DB/vector).

## Còn lại / rủi ro

- **Bench HTTP và `user --id VP0000004` chưa chạy được.** Container Postgres prodcopy (`vota-prodcopy-pg`, cổng 55433, chứa `vota_prodcopy`, `vota_append_eval_20261005`, `vota_g6pref_v1`) không còn trên máy ngày 2026-10-12. Theo plan đã duyệt, không tự dựng lại.
  - Muốn có report cold-start trên dữ liệu prodcopy thì khôi phục container rồi chạy lại các lệnh ở `src/evaluation/reports/eval-2026-10-09-recsys-coldstart-ac-rec-baseline-v2.md` §5.
- Các dòng cold-start trong bench ở chế độ prod sẽ đổi có chủ đích. Chế độ eval không đổi.
