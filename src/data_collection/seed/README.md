# data_collection.seed

Claude Code sinh package này theo `docs/MOCK_DATA_SPEC.md` §1 (gen_products → load_products → parse_combos → seed_histories → seed_app → seed_insider).
Chạy: `python -m data_collection.seed --as-of YYYY-MM-DD --seed 42 --reset`. Kiểm tra: `psql "$SEED_DATABASE_URL" -f db/verify.sql`.
