# Grid trọng số RecSys trên LLBO và coldstart (append-v1, 07/10/2026)

- Phục vụ: FR-REC-01, FR-REC-04; kiểm thêm cho đề xuất đã áp dụng `docs/prd/update-archive/2026-10-06-recsys-trong-so-ngan-han-pho-bien.md`
  (W_SHORT / W_POP / W_LONG = 0,7 / 0,15 / 0,15). Trước đây grid đầy đủ chỉ chạy trên temporal; LLBO và coldstart chỉ có điểm 0,7.
- Commit: `c47fc35` + working tree (thay đổi duy nhất chạm engine: hằng W_* trong `profile.py`; mọi run dùng `--override` tường minh
  nên không phụ thuộc giá trị mặc định).
- Dữ liệu: DB local `vota_append_eval_20261005` (cổng 55433), as_of 2026-10-05, vector `npy:bench_out/recsys-append-20261005/vec_append_e5-small`
  (3.393 search unit, e5-small 384 chiều).
- Split đóng băng: `split-llbo-append-v1-asof20261005.json` (sha256 9ad7c6da3bea…, 4.021 khách),
  `split-coldstart-append-v1-asof20261005.json` (sha256 dddbd56b83b1…, 5.231 khách).
- Arm: `engine` (list 20 món, chế độ eval) và `engine_prod` (list 5 món như production). W_LONG = 0,15, λ MMR = 0,7, W_POP = 0,85 − W_SHORT.

| Run id | Override | configHash |
|---|---|---|
| `20261007-append-v1-{llbo,coldstart}-grid-ws0.6` (mốc chạy lại) | W_SHORT=0.6, W_POP=0.25 | b0aee886 |
| `20261007-append-v1-{llbo,coldstart}-grid-ws0.65` | W_SHORT=0.65, W_POP=0.2 | 807e1a73 |
| `20261005-append-v1-{llbo,coldstart}-grid-ws0.7` (run 05/10) | W_SHORT=0.7, W_POP=0.15 | c893694f |
| `20261007-append-v1-{llbo,coldstart}-grid-ws0.75` | W_SHORT=0.75, W_POP=0.1 | ec49102e |
| `20261007-append-v1-{llbo,coldstart}-grid-ws0.8` | W_SHORT=0.8, W_POP=0.05 | a6c21b27 |

Mốc 0,6 chạy lại cho top-20 ids trùng 100 % với run `…-v5` ngày 05/10 ở cả hai split và hai arm → run 0,7 của 05/10 so cặp hợp lệ với mốc mới.

## Kết quả (nguyên văn output)

Δ = trọng số mới − mốc 0,60/0,25, điểm %, paired bootstrap 10.000 lượt seed 42 (`recsys_bench.metrics.paired_bootstrap`);
`*` = CI95 không chứa 0.

```text

=== llbo · users 4021 · rerun 0.6 khớp ids run v5: {'engine': 4021, 'engine_prod': 4021}
  [engine_prod] mốc 0.60/0.25: hit@20=0.5755  ndcg@10=0.4314  ndcg@5=0.4269
    0.65/0.20: hit@20 +0.45 [+0.00;+0.90]  ndcg@10 +0.53*[+0.25;+0.81]  ndcg@5 +0.53*[+0.26;+0.82]
    0.70/0.15: hit@20 +0.70*[+0.07;+1.32]  ndcg@10 +1.77*[+1.30;+2.24]  ndcg@5 +1.59*[+1.11;+2.08]
    0.75/0.10: hit@20 +0.35 [-0.45;+1.12]  ndcg@10 +2.39*[+1.70;+3.08]  ndcg@5 +1.48*[+0.75;+2.23]
    0.80/0.05: hit@20 -0.05 [-1.12;+0.99]  ndcg@10 -0.92 [-1.89;+0.07]  ndcg@5 -3.09*[-4.15;-2.01]
  [engine] mốc 0.60/0.25: hit@20=0.8508  ndcg@10=0.4935  ndcg@5=0.4553
    0.65/0.20: hit@20 -0.70*[-1.07;-0.35]  ndcg@10 +0.25*[+0.02;+0.47]  ndcg@5 +0.49*[+0.23;+0.76]
    0.70/0.15: hit@20 -1.84*[-2.36;-1.32]  ndcg@10 +1.17*[+0.77;+1.58]  ndcg@5 +1.58*[+1.12;+2.06]
    0.75/0.10: hit@20 -3.18*[-3.88;-2.51]  ndcg@10 +1.17*[+0.55;+1.80]  ndcg@5 +1.15*[+0.42;+1.88]
    0.80/0.05: hit@20 -5.72*[-6.62;-4.82]  ndcg@10 -4.14*[-5.07;-3.19]  ndcg@5 -4.10*[-5.13;-3.07]

=== coldstart · users 5231 · rerun 0.6 khớp ids run v5: {'engine': 5231, 'engine_prod': 5231}
  [engine_prod] mốc 0.60/0.25: hit@20=0.6060  ndcg@10=0.3601  ndcg@5=0.3556
    0.65/0.20: hit@20 +6.35*[+5.68;+7.02]  ndcg@10 +7.03*[+6.63;+7.43]  ndcg@5 +7.09*[+6.68;+7.49]
    0.70/0.15: hit@20 +10.82*[+9.96;+11.70]  ndcg@10 +22.90*[+22.22;+23.60]  ndcg@5 +22.98*[+22.30;+23.69]
    0.75/0.10: hit@20 +13.84*[+12.88;+14.82]  ndcg@10 +33.68*[+32.81;+34.56]  ndcg@5 +33.72*[+32.83;+34.61]
    0.80/0.05: hit@20 +15.31*[+14.28;+16.38]  ndcg@10 +36.82*[+35.89;+37.77]  ndcg@5 +36.85*[+35.90;+37.81]
  [engine] mốc 0.60/0.25: hit@20=0.8153  ndcg@10=0.4112  ndcg@5=0.3718
    0.65/0.20: hit@20 +0.02 [-0.27;+0.32]  ndcg@10 +5.61*[+5.31;+5.89]  ndcg@5 +7.08*[+6.70;+7.47]
    0.70/0.15: hit@20 -0.32 [-0.73;+0.10]  ndcg@10 +19.98*[+19.40;+20.57]  ndcg@5 +22.79*[+22.13;+23.47]
    0.75/0.10: hit@20 -0.80*[-1.34;-0.27]  ndcg@10 +29.46*[+28.72;+30.21]  ndcg@5 +32.59*[+31.73;+33.45]
    0.80/0.05: hit@20 -1.70*[-2.37;-1.03]  ndcg@10 +31.49*[+30.67;+32.30]  ndcg@5 +34.82*[+33.88;+35.75]
```

## Đọc

1. LLBO: 0,7 là điểm duy nhất mà `engine_prod` tăng có ý nghĩa ở cả hit@20, NDCG@10, NDCG@5. 0,75 tăng NDCG@10 nhiều hơn nhưng hit@20
   của list 5 món hết ý nghĩa và list 20 món mất −3,18 (so với −1,84 ở 0,7). 0,8 gãy (NDCG@5 prod −3,09, hit@20 list 20 −5,72).
2. Coldstart tăng đơn điệu theo W_SHORT — không dùng để chọn: khách mới thường đã xem đúng món ngay trước khi mua.
3. Kết hợp với temporal (0,75: hit@20 −2,07) và nexttrip (0,8: hit@20 −3,54) của `eval-2026-10-06-recsys-search-tong-hop.md` §6:
   0,7 / 0,15 / 0,15 vẫn là điểm cân bằng; giữ như đã áp dụng.

## Caveat

- Dữ liệu lịch sử tổng hợp (append-v1); kết luận phụ thuộc phân bố nhóm chốt.
- W_LONG và λ MMR không quét trong grid này.
- Không đọc latency từ các run này (4 tiến trình song song).

## Tái sinh

```bash
export PYTHONPATH=$PWD:$PWD/src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONUTF8=1
export DATABASE_URL=postgresql://vota_app_login:vota@127.0.0.1:55433/vota_append_eval_20261005
export CDP_DATABASE_URL=postgresql://cdp_eval_login:eval@127.0.0.1:55433/vota_append_eval_20261005
export EVAL_DATABASE_URL=$CDP_DATABASE_URL RECSYS_HOME=bench_out/recsys-append-20261005
V=npy:bench_out/recsys-append-20261005/vec_append_e5-small
for sp in llbo coldstart; do for p in "0.6 0.25" "0.65 0.2" "0.75 0.1" "0.8 0.05"; do set -- $p
  python -m src.evaluation.recsys_bench run --arm engine --arm engine_prod --split $sp --as-of 2026-10-05 --vectors $V \
    --split-file src/evaluation/recsys_bench/frozen/split-$sp-append-v1-asof20261005.json \
    --override W_SHORT=$1 --override W_POP=$2 --run-id 20261007-append-v1-$sp-grid-ws$1
done; done
```

Bảng sinh bằng script dưới (đọc `per_user.jsonl`, không cần DB; chạy từ repo root với `PYTHONPATH=.`):

```python
import json, numpy as np
from src.evaluation.recsys_bench.metrics import paired_bootstrap
R = "bench_out/recsys-append-20261005/runs/"
def load(run):
    out = {}
    for l in open(R + run + "/per_user.jsonl"):
        d = json.loads(l); ids, t = d.get("ids") or [], d["target"]
        out.setdefault(d["arm"], {})[d["user"]] = (ids, t)
    return out
def met(rows, m):
    r = {}
    for u, (ids, t) in rows.items():
        if m == "hit@20": r[u] = float(t in ids[:20])
        elif m == "ndcg@10": r[u] = 1/np.log2(ids[:10].index(t)+2) if t in ids[:10] else 0.0
        elif m == "ndcg@5": r[u] = 1/np.log2(ids[:5].index(t)+2) if t in ids[:5] else 0.0
    return r
for sp in ["llbo", "coldstart"]:
    base = load(f"20261007-append-v1-{sp}-grid-ws0.6")
    v5 = load(f"20261005-append-v1-{sp}-v5")
    same = {a: sum(base[a][u][0] == v5[a][u][0] for u in base[a]) for a in ("engine", "engine_prod")}
    print(f"\n=== {sp} · users {len(base['engine'])} · rerun 0.6 khớp ids run v5: {same}")
    runs = [("0.65/0.20", f"20261007-append-v1-{sp}-grid-ws0.65"), ("0.70/0.15", f"20261005-append-v1-{sp}-grid-ws0.7"),
            ("0.75/0.10", f"20261007-append-v1-{sp}-grid-ws0.75"), ("0.80/0.05", f"20261007-append-v1-{sp}-grid-ws0.8")]
    for arm in ("engine_prod", "engine"):
        b = {m: met(base[arm], m) for m in ("hit@20", "ndcg@10", "ndcg@5")}
        print(f"  [{arm}] mốc 0.60/0.25: " + "  ".join(f"{m}={np.mean(list(v.values())):.4f}" for m, v in b.items()))
        for name, run in runs:
            x = load(run)[arm]; cells = []
            for m in ("hit@20", "ndcg@10", "ndcg@5"):
                pb = paired_bootstrap(b[m], met(x, m)); lo, hi = pb["ci95"]
                sig = "*" if lo > 0 or hi < 0 else " "
                cells.append(f"{m} {pb['delta']:+.2f}{sig}[{lo:+.2f};{hi:+.2f}]")
            print(f"    {name}: " + "  ".join(cells))
```
