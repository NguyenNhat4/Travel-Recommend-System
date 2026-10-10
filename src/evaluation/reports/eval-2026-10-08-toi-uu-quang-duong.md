# Đo xếp lịch ít di chuyển: ngân sách và phương án khác (AC-AGT-04)

- Ngày chạy: 2026-10-08
- Code: commit `16bb5bf9` + thay đổi chưa commit của đợt "tối ưu quãng đường nhiều khách sạn" và "chọn theo ngân sách,
  phương án khác" (history `2026-10-07-toi-uu-quang-duong-nhieu-khach-san.md`,
  `2026-10-08-khach-san-theo-ngan-sach-va-phuong-an-khac.md`).
- Dữ liệu: Postgres local nạp từ staging ngày 07/10/2026 (14.935 sản phẩm còn bán), chỉ đọc.
- Cấu hình: seed 42; 30 mẫu mỗi ô; mỗi mẫu 10 điểm tham quan và 10 hạng phòng còn bán, có giá, có toạ độ; 2 người lớn;
  không vé máy bay.
- Phục vụ: FR-AGT-03, AC-AGT-04 (đề xuất `docs/prd/update-archive/2026-10-08-khach-san-theo-ngan-sach-va-phuong-an-khac.md`).

## Lệnh tái sinh số

```bash
DATABASE_URL=postgresql://vota_app_login:vota@localhost:5432/vota \
    .venv/bin/python -m src.evaluation.agent.routing_bench --samples 30 --seed 42
```

## Ba mức ngân sách

- **không**: không có ngân sách. Luật "gần trước, chênh dưới 2 km thì rẻ hơn", giống bản trước ngày 08/10.
- **chặt (p25)**: tiền hoạt động + số đêm × giá phòng ở phân vị 25% của 10 phòng trong mẫu.
- **rộng (p75)**: như trên, với phân vị 75%.

Tiền hoạt động lấy từ lịch không ngân sách, nên hai mức ngân sách chỉ khác nhau ở phần khách sạn.

## Kết quả

Nguyên văn output. Các cột:
- **km TB**: quãng đường cả chuyến, đường chim bay, trung bình.
- **Khách sạn TB**: tiền khách sạn cả chuyến, trung bình, triệu ₫.
- **Có phương án khác**: tỉ lệ mẫu có mục Phương án khác.
- **Gần hơn / Rẻ hơn**: trung vị chênh tiền và chênh km so với lịch được chọn. Phía gần hơn lấy phương án rẻ nhất; phía
  rẻ hơn lấy phương án rẻ nhất. Số trong ngoặc là số mẫu có phương án ở phía đó.

| Điểm đến | Ngày | Ngân sách | km TB | Khách sạn TB (tr) | Vừa ngân sách | Có phương án khác | Gần hơn: trung vị (số mẫu) | Rẻ hơn: trung vị (số mẫu) | p95 ms |
|---|---|---|---|---|---|---|---|---|---|
| Phú Quốc | 3 | không | 9.9 | 15.7 | 100% | 90% | – | −4.7 tr → +69.0 km (27) | 4 |
| Phú Quốc | 3 | chặt (p25) | 38.6 | 2.2 | 100% | 90% | +3.3 tr → −44.3 km (20) | −0.8 tr → +63.9 km (21) | 4 |
| Phú Quốc | 3 | rộng (p75) | 13.9 | 4.6 | 100% | 90% | +24.9 tr → −3.2 km (5) | −2.7 tr → +68.1 km (26) | 4 |
| Phú Quốc | 5 | không | 41.8 | 19.5 | 100% | 90% | +16.8 tr → −4.8 km (2) | −7.2 tr → +114.9 km (27) | 51 |
| Phú Quốc | 5 | chặt (p25) | 85.9 | 4.7 | 100% | 90% | +4.1 tr → −20.2 km (20) | −2.1 tr → +87.1 km (23) | 52 |
| Phú Quốc | 5 | rộng (p75) | 42.9 | 10.4 | 100% | 90% | +26.1 tr → −4.8 km (6) | −5.6 tr → +114.3 km (27) | 51 |
| Nha Trang | 3 | không | 9.2 | 5.9 | 100% | 73% | – | −6.0 tr → +11.6 km (22) | 2 |
| Nha Trang | 3 | chặt (p25) | 14.7 | 0.9 | 100% | 73% | +7.4 tr → −9.2 km (18) | −0.1 tr → +5.8 km (13) | 3 |
| Nha Trang | 3 | rộng (p75) | 13.1 | 1.6 | 100% | 73% | +10.3 tr → −10.4 km (11) | −0.5 tr → +6.7 km (16) | 3 |
| Nha Trang | 5 | không | 22.7 | 13.6 | 100% | 93% | +1.8 tr → −2.9 km (6) | −11.4 tr → +18.9 km (23) | 21 |
| Nha Trang | 5 | chặt (p25) | 33.7 | 1.9 | 100% | 97% | +5.2 tr → −8.7 km (25) | −0.3 tr → +4.2 km (14) | 21 |
| Nha Trang | 5 | rộng (p75) | 29.2 | 5.4 | 100% | 93% | +5.5 tr → −10.5 km (18) | −2.8 tr → +7.0 km (18) | 21 |
| Hà Nội | 3 | không | 28.8 | 6.8 | 100% | 73% | – | −2.1 tr → +10.3 km (22) | 3 |
| Hà Nội | 3 | chặt (p25) | 32.7 | 1.2 | 100% | 73% | +1.3 tr → −4.7 km (16) | −0.4 tr → +9.8 km (16) | 4 |
| Hà Nội | 3 | rộng (p75) | 29.2 | 2.7 | 100% | 73% | +24.3 tr → −4.3 km (2) | −1.7 tr → +9.7 km (22) | 3 |
| Hà Nội | 5 | không | 78.7 | 13.2 | 100% | 97% | – | −11.5 tr → +13.0 km (29) | 60 |
| Hà Nội | 5 | chặt (p25) | 86.8 | 2.4 | 100% | 97% | +2.7 tr → −5.6 km (23) | −0.7 tr → +9.9 km (18) | 63 |
| Hà Nội | 5 | rộng (p75) | 80.3 | 8.0 | 100% | 97% | +7.1 tr → −3.4 km (7) | −3.4 tr → +11.1 km (28) | 61 |
| Hội An | 3 | không | 29.7 | 4.8 | 100% | 60% | – | −5.0 tr → +5.8 km (18) | 1 |
| Hội An | 3 | chặt (p25) | 45.1 | 1.0 | 100% | 70% | +2.7 tr → −3.2 km (14) | −0.5 tr → +4.8 km (10) | 1 |
| Hội An | 3 | rộng (p75) | 37.6 | 1.9 | 100% | 60% | +8.9 tr → −31.2 km (9) | −2.2 tr → +3.6 km (15) | 1 |
| Hội An | 5 | không | 70.6 | 9.0 | 100% | 87% | – | −5.0 tr → +16.7 km (26) | 8 |
| Hội An | 5 | chặt (p25) | 87.8 | 2.0 | 100% | 87% | +2.1 tr → −4.7 km (19) | −0.9 tr → +8.9 km (15) | 8 |
| Hội An | 5 | rộng (p75) | 78.3 | 4.4 | 100% | 87% | +7.4 tr → −19.6 km (8) | −2.2 tr → +9.4 km (25) | 8 |
| Huế | 3 | không | 0.0 | 0.6 | 100% | 0% | – | – | 0 |
| Huế | 3 | chặt (p25) | 0.0 | 0.6 | 100% | 0% | – | – | 0 |
| Huế | 3 | rộng (p75) | 0.0 | 0.6 | 100% | 0% | – | – | 0 |
| Huế | 5 | không | 0.2 | 1.2 | 100% | 0% | – | – | 3 |
| Huế | 5 | chặt (p25) | 0.2 | 1.2 | 100% | 0% | – | – | 3 |
| Huế | 5 | rộng (p75) | 0.2 | 1.2 | 100% | 0% | – | – | 3 |
| Vũng Tàu | 3 | không | – | – | – | – | – | – | – |
| Vũng Tàu | 3 | chặt (p25) | – | – | – | – | – | – | – |
| Vũng Tàu | 3 | rộng (p75) | – | – | – | – | – | – | – |
| Vũng Tàu | 5 | không | – | – | – | – | – | – | – |
| Vũng Tàu | 5 | chặt (p25) | – | – | – | – | – | – | – |
| Vũng Tàu | 5 | rộng (p75) | – | – | – | – | – | – | – |

## Đọc số

- **Ngân sách làm đúng việc.**
  - Ngân sách chặt: tiền khách sạn còn khoảng 1/7–1/5 so với khi không có ngân sách. Đổi lại quãng đường dài hơn (Phú
    Quốc 3 ngày: 9,9 → 38,6 km).
  - Ngân sách rộng: kết quả gần với khi không có ngân sách.
  - 100% mẫu vừa ngân sách, vì mức chặt (p25) luôn có ít nhất một phòng vừa.
- **Phương án khác cho đúng con số để cân nhắc nâng ngân sách.** Ví dụ ở ngân sách chặt:
  - Phú Quốc 3 ngày: thêm khoảng 3,3 triệu thì bớt khoảng 44 km;
  - Phú Quốc 5 ngày: thêm 4,1 triệu thì bớt 20 km;
  - Nha Trang 5 ngày: thêm 5,2 triệu thì bớt 8,7 km.
- **Khi không có ngân sách,** lịch chính đã là lịch gần nhất, nên gần như chỉ có phương án rẻ hơn. Ví dụ Phú Quốc 5 ngày:
  bớt 7,2 triệu thì đi thêm 115 km.
- **Huế và Vũng Tàu không có phương án.** Gần như mọi điểm tham quan ở đó mang toạ độ tâm thành phố (chưa rõ vị trí), nên
  không có quãng đường để so. Vũng Tàu không ra lịch theo khoảng cách nào ("–").
- **Thời gian `compose_plan`:** p95 ≤ 63 ms (chuyến 5 ngày có đổi khách sạn).

## Caveat khi trích dẫn

- Km là đường chim bay. Ở đảo (Phú Quốc), đường thật dài hơn đáng kể.
- Hạng phòng dùng toạ độ của `catalog.product_meta`, có thể là toạ độ khách sạn cha. Đơn vị giá giả định: phòng
  `PER_NIGHT`, điểm tham quan `PER_PERSON`. Agent thật lấy `priceUnit` từ Search.
- Mẫu ngẫu nhiên 10 + 10 không giống ứng viên thật của agent: Search đã lọc theo câu hỏi, và có 6 ứng viên mỗi loại.
  Bảng này dùng để so luật với nhau, không phải số của sản phẩm.
- Không có vé máy bay. Vé chỉ trừ thẳng vào ngân sách, không đổi cách so.

## Đơn giá km→tiền (đã thử, không dùng)

Đo ngày 07/10/2026 trên cùng dữ liệu, 30 mẫu mỗi ô, bằng một bản sửa thử của `routing.py`. Khoá so là "tiền + km × đơn
giá"; số là km · tiền khách sạn cả chuyến. Bản sửa thử chỉ nằm trong scratchpad, đã bị xoá, nên **không tái sinh được bằng
lệnh**. Bảng giữ lại để giải thích vì sao người dùng chọn "ưu tiên gần, trong ngân sách" thay cho đơn giá.

| Điểm đến | Ngày | Luật gần trước (mức 2 km) | 100k ₫/km | 200k ₫/km | 500k ₫/km |
|---|---|---|---|---|---|
| Phú Quốc | 3 | 15,9 km · 6,1 tr | 21,8 km · 2,8 tr | 19,2 km · 3,2 tr | 16,4 km · 3,9 tr |
| Phú Quốc | 5 | 34,6 km · 18,4 tr | 57,6 km · 5,8 tr | 40,9 km · 7,8 tr | 37,7 km · 8,6 tr |
| Nha Trang | 3 | 10,8 km · 4,3 tr | 15,3 km · 0,8 tr | 15,1 km · 0,9 tr | 12,8 km · 1,7 tr |
| Nha Trang | 5 | 28,3 km · 8,2 tr | 36,7 km · 1,6 tr | 36,4 km · 1,6 tr | 31,9 km · 3,3 tr |
| Hà Nội | 3 | 37,7 km · 4,6 tr | 42,1 km · 1,1 tr | 41,3 km · 1,2 tr | 39,3 km · 1,8 tr |
| Hà Nội | 5 | 77,4 km · 7,9 tr | 82,1 km · 2,6 tr | 81,2 km · 2,7 tr | 79,6 km · 3,2 tr |
| Hội An | 3 | 34,8 km · 3,2 tr | 41,1 km · 0,7 tr | 38,1 km · 1,4 tr | 35,8 km · 2,1 tr |
| Hội An | 5 | 65,2 km · 12,3 tr | 84,1 km · 1,9 tr | 76,1 km · 3,2 tr | 72,7 km · 4,4 tr |

Bảng này dùng mẫu khác với bảng trên (sinh ngẫu nhiên bằng code khác), nên không so trực tiếp số giữa hai bảng.
