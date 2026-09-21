# Travel Recommendation Product

## Dựng database demo local

Yêu cầu: Docker Compose, Python 3.10+ và môi trường Python đã cài dependency trong `src/data_collection/requirements.txt`.

```bash
conda activate vsf
python -m pip install -r src/data_collection/requirements.txt
make demo-db
```

`make demo-db` thực hiện ba việc: chạy PostgreSQL 16 + pgvector bằng Docker, kiểm tra/bung snapshot catalog 10.320 sản phẩm và seed hai database `vota`/`insider`, sau đó chạy các câu verify chính thức. Mỗi thành viên có Docker volume riêng trên máy; không chia sẻ hoặc commit volume.

Lần đầu dùng `make demo-db`. Khi database local đã có dữ liệu và cần dựng lại từ đầu:

```bash
make demo-db-reset
```

Lệnh `demo-db-reset` xóa state demo hiện có trong hai database local trước khi nạp lại. Target này cố định URL vào PostgreSQL Docker `localhost:5432`, không đọc URL staging từ shell. Có thể cố định ngày cửa sổ dữ liệu bằng `make demo-db AS_OF=2026-09-21`.

## Chạy Backend

```bash
make backend
```

`make backend` build và chạy Backend trong Docker Compose; Compose cũng khởi động PostgreSQL nếu service đó chưa chạy. Kiểm tra `http://localhost:8000/health` sau khi server khởi động. Để xem log hoặc dừng riêng Backend, dùng `make backend-logs` hoặc `make backend-stop`; dữ liệu PostgreSQL vẫn được giữ.

Để chạy Backend trực tiếp trên máy với reload khi sửa code, cài dependency rồi dùng `make backend-local`:

```bash
python -m pip install -r src/backend/requirements.txt
make backend-local
```

Snapshot catalog có version nằm tại `src/data_collection/snapshots/`; JSONL đã bung, artifact seed và database volume đều là runtime local, không nằm trong Git.
