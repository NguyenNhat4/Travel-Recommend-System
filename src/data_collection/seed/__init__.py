"""Loader và mock data tuần 1 cho database `vota` + `insider`.

Chạy từ `src/`:
    python -m data_collection.seed --as-of YYYY-MM-DD --seed 42 [--reset]

Thứ tự bước (MOCK_DATA_SPEC §1): gen_products → load_products → parse_combos
→ seed_histories → seed_app → seed_insider → report.

Mỗi module tách làm hai nửa:
  * `build_*()` thuần — chỉ nhận (config, rng, as_of, dữ liệu vào) và trả về rows. Không chạm database,
    nên unit test chạy offline, không cần Postgres.
  * `write_*()` mỏng — mở transaction và COPY/batch insert. `psycopg` chỉ import bên trong nửa này.
"""

__all__ = ["main"]


def main(argv=None):
    """Điểm vào của CLI; tách khỏi __main__ để test gọi được."""
    from .__main__ import main as _main

    return _main(argv)
