"""Part 10 — dataset scale (100k / 1m) → bench_out/data/<scale>/{items.parquet, vectors.npy, query_vectors.npy, queries.jsonl, gt.npz, stats.json}.

--vectors amplify (spec-fasttrack §3, dùng hôm nay): khuếch đại từ vector THẬT của catalog — nội suy giữa seed và láng giềng
    + nhiễu nhỏ, metadata kế thừa. Cùng không gian bge-m3 → dùng lại đúng query vector của catalog. Chỉ dùng cho hiệu năng và
    hành vi filter, KHÔNG cho chất lượng tìm kiếm; số 1M chỉ dùng khi qua kiểm LID / gần trùng (ghi stats.json).
--vectors fake: vector cụm như Part 2 + metadata lấy mẫu từ catalog — chạy thử khung, không tải gì.
--vectors cohere-vi: hoãn (fasttrack §7 "Tuần này, chạy nền").
Sau khi dựng: tự gọi `queries --scale S` (amplify: --reuse-query-vectors catalog) và `gt --scale S`.
"""
from __future__ import annotations

import json
import logging
import time
import uuid

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .. import paths
from ..config import VBenchConfig
from ..embed import fake_item_vectors, fake_query_vectors, l2_normalize
from ..groundtruth import compute_gt, topk_exact
from ..querygen import run_queries
from ..results import dump_json, sha256_file

log = logging.getLogger("vbench.scale")

SEED_OFFSET_AMPLIFY = 10000
SEED_OFFSET_META = 10001
SEED_OFFSET_PILOT = 10002
SEED_OFFSET_FAKE = 10003

SCALE_SCHEMA = pa.schema([
    ("row", pa.int32()), ("id", pa.string()), ("variant", pa.string()), ("taxonomy", pa.string()),
    ("destination", pa.string()), ("province", pa.string()), ("name", pa.string()), ("available", pa.bool_()),
    ("amenity_ids", pa.list_(pa.int16())), ("unit_price", pa.float64()), ("star_rating", pa.float32()),
    ("lat", pa.float64()), ("lon", pa.float64()), ("embed_text", pa.string()), ("lex_text", pa.string()),
    ("text_hash", pa.string()), ("description_derived", pa.bool_()), ("n_children", pa.int16()),
    ("property_type", pa.string()), ("seed_row", pa.int32()),
])


# ---------------------------------------------------------------- tiện ích
def lid_mle(x: np.ndarray, k: int) -> np.ndarray:
    """LID MLE (fasttrack §3.5a): LID(x) = −[(1/k) Σ_{i=1..k} ln(d_i / d_k)]⁻¹, Euclid trên vector chuẩn hoá, láng giềng trong chính tập x.

    Bỏ khoảng cách 0 (bản trùng) để ln không vô hạn.
    """
    x = l2_normalize(x)
    n = len(x)
    out = np.empty(n)
    for a in range(0, n, 2048):
        s = x[a:a + 2048] @ x.T
        d = np.sqrt(np.clip(2.0 - 2.0 * s, 0.0, None))
        d[np.arange(len(d)), np.arange(a, a + len(d))] = np.inf          # bỏ chính nó
        d[d <= 1e-6] = np.inf                                            # bỏ bản trùng
        part = np.partition(d, k - 1, axis=1)[:, :k]
        part.sort(axis=1)
        dk = part[:, -1:]
        with np.errstate(divide="ignore", invalid="ignore"):
            m = np.log(part / dk).mean(axis=1)
            out[a:a + len(d)] = -1.0 / m
    return out


def _uuid(scale: str, i: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vbench:{scale}:{i}"))


def _load_catalog() -> tuple[pa.Table, np.ndarray]:
    d = paths.data_dir("catalog", create=False)
    items = pq.read_table(d / paths.ITEMS)
    v0 = np.load(d / paths.VECTORS)
    if v0.shape[0] != items.num_rows:
        raise ValueError("catalog vectors.npy không khớp items.parquet — chạy `vb embed --scale catalog` trước")
    return items, v0


def _neighbors(v0: np.ndarray, dest_codes: np.ndarray, k: int) -> np.ndarray:
    """k láng giềng cosine của mỗi seed; ưu tiên cùng destination khi destination có đủ k seed khác, không thì toàn cục."""
    s = v0 @ v0.T
    np.fill_diagonal(s, -np.inf)
    n0 = len(v0)
    out = np.empty((n0, k), dtype=np.int64)
    for dc in np.unique(dest_codes):
        rows = np.flatnonzero(dest_codes == dc)
        if len(rows) - 1 >= k:
            sub = s[np.ix_(rows, rows)]
            nn = np.argpartition(-sub, k - 1, axis=1)[:, :k]
            out[rows] = rows[nn]
        else:
            nn = np.argpartition(-s[rows], k - 1, axis=1)[:, :k]
            out[rows] = nn
    return out


def _gen_block(rng: np.random.Generator, v0: np.ndarray, nbrs: np.ndarray, t: np.ndarray, sigma: float,
               alpha: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    """v = normalize((1−α)·V0[i] + α·V0[j] + σ·g/√d), i = t mod N0, j = láng giềng ngẫu nhiên của i. Trả (v fp32, cos(v, seed))."""
    n0, d = v0.shape
    i = t % n0
    j = nbrs[i, rng.integers(nbrs.shape[1], size=len(t))]
    a = rng.uniform(alpha[0], alpha[1], size=(len(t), 1)).astype(np.float32)
    g = rng.standard_normal(size=(len(t), d), dtype=np.float32)
    v = (1.0 - a) * v0[i] + a * v0[j] + np.float32(sigma) * g / np.float32(np.sqrt(d))
    v = l2_normalize(v)
    cos_seed = np.einsum("ij,ij->i", v, v0[i])
    return v, cos_seed


def _inherit_meta(items: pa.Table, seed_rows: np.ndarray, cfg: VBenchConfig, rng: np.random.Generator, scale: str,
                  offset: int) -> pa.Table:
    """Metadata kế thừa từ seed i (fasttrack §3.4)."""
    am = cfg.fast.amplify
    n = len(seed_rows)
    col = {c: items.column(c).to_numpy(zero_copy_only=False) for c in
           ("variant", "taxonomy", "destination", "province", "name", "star_rating", "unit_price", "lat", "lon", "available")}
    variant = col["variant"][seed_rows]
    # available ~ Bernoulli(tỷ lệ available của variant)
    avail = np.empty(n, dtype=bool)
    for v in np.unique(col["variant"]):
        rate = float(col["available"][col["variant"] == v].mean())
        sel = variant == v
        avail[sel] = rng.random(int(sel.sum())) < rate
    # amenity: bỏ mỗi id với xác suất amenity_drop; thêm 1 id phổ biến (theo tần suất trong cùng variant) với xác suất amenity_add
    la = items.column("amenity_ids").combine_chunks()
    off0 = la.offsets.to_numpy()
    val0 = la.flatten().to_numpy(zero_copy_only=False).astype(np.int16)
    lens = (off0[seed_rows + 1] - off0[seed_rows]).astype(np.int64)
    starts = np.repeat(off0[seed_rows], lens)
    within = np.arange(int(lens.sum())) - np.repeat(np.cumsum(lens) - lens, lens)
    flat = val0[starts + within]
    keep = rng.random(len(flat)) >= am.amenity_drop
    row_of_flat = np.repeat(np.arange(n), lens)
    flat, row_of_flat = flat[keep], row_of_flat[keep]
    popular: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for v in np.unique(col["variant"]):
        rows_v = np.flatnonzero(col["variant"] == v)
        if len(rows_v) == 0:
            continue
        ids_v = np.concatenate([val0[off0[r]:off0[r + 1]] for r in rows_v]) if len(rows_v) else np.empty(0, np.int16)
        if len(ids_v):
            u, c = np.unique(ids_v, return_counts=True)
            popular[v] = (u, c / c.sum())
    add_rows = np.flatnonzero(rng.random(n) < am.amenity_add)
    add_ids = np.full(len(add_rows), -1, dtype=np.int32)
    for k_, r in enumerate(add_rows):
        pv = popular.get(variant[r])
        if pv is not None:
            add_ids[k_] = int(rng.choice(pv[0], p=pv[1]))
    ok = add_ids >= 0
    flat = np.concatenate([flat, add_ids[ok].astype(np.int16)])
    row_of_flat = np.concatenate([row_of_flat, add_rows[ok]])
    # gộp theo dòng, bỏ trùng, sắp tăng
    order = np.lexsort((flat, row_of_flat))
    flat, row_of_flat = flat[order], row_of_flat[order]
    dup = np.zeros(len(flat), dtype=bool)
    dup[1:] = (flat[1:] == flat[:-1]) & (row_of_flat[1:] == row_of_flat[:-1])
    flat, row_of_flat = flat[~dup], row_of_flat[~dup]
    counts = np.bincount(row_of_flat, minlength=n)
    offsets = np.concatenate([[0], np.cumsum(counts)]).astype(np.int32)
    amen = pa.ListArray.from_arrays(pa.array(offsets, pa.int32()), pa.array(flat, pa.int16()))
    # giá × exp(N(0, price_log_sd)); null giữ null
    price = col["unit_price"][seed_rows].astype(np.float64) * np.exp(rng.normal(0.0, am.price_log_sd, size=n))
    # lat/lon + N(0, geo_jitter_m)
    lat0 = col["lat"][seed_rows].astype(np.float64)
    lon0 = col["lon"][seed_rows].astype(np.float64)
    dy = rng.normal(0.0, am.geo_jitter_m, size=n)
    dx = rng.normal(0.0, am.geo_jitter_m, size=n)
    lat = lat0 + dy / 111_320.0
    lon = lon0 + dx / (111_320.0 * np.cos(np.radians(lat0)))
    ids = [_uuid(scale, int(offset + t)) for t in range(n)]
    empty = pa.array([""] * n, pa.string())
    return pa.table({
        "row": pa.array(np.arange(offset, offset + n, dtype=np.int32)), "id": pa.array(ids, pa.string()),
        "variant": pa.array(variant, pa.string()), "taxonomy": pa.array(col["taxonomy"][seed_rows], pa.string()),
        "destination": pa.array(col["destination"][seed_rows], pa.string()),
        "province": pa.array(col["province"][seed_rows], pa.string()), "name": pa.array(col["name"][seed_rows], pa.string()),
        "available": pa.array(avail), "amenity_ids": amen,
        "unit_price": pa.array(price, pa.float64(), mask=np.isnan(price)),
        "star_rating": pa.array(col["star_rating"][seed_rows].astype(np.float32), pa.float32(),
                                mask=np.isnan(col["star_rating"][seed_rows].astype(np.float64))),
        "lat": pa.array(lat), "lon": pa.array(lon), "embed_text": empty, "lex_text": empty, "text_hash": empty,
        "description_derived": pa.array(np.zeros(n, dtype=bool)), "n_children": pa.array(np.zeros(n, dtype=np.int16)),
        "property_type": pa.array([None] * n, pa.string()), "seed_row": pa.array(seed_rows.astype(np.int32)),
    }, schema=SCALE_SCHEMA)


def _checks(cfg: VBenchConfig, v0: np.ndarray, sample: np.ndarray, cos_seed: np.ndarray) -> dict:
    am = cfg.fast.amplify
    lid0 = lid_mle(v0, am.lid_k)
    lid1 = lid_mle(sample, am.lid_k)
    m0, m1 = float(np.nanmedian(lid0)), float(np.nanmedian(lid1))
    ratio = m1 / m0 if m0 > 0 else float("nan")
    near = float((cos_seed >= am.near_dup_cos).mean())
    return {"lid_median_catalog": m0, "lid_median_synthetic": m1, "lid_ratio": ratio,
            "lid_pass": bool(am.lid_ratio[0] <= ratio <= am.lid_ratio[1]),
            "near_dup_rate": near, "near_dup_pass": bool(near < am.near_dup_max_rate),
            "cos_seed_median": float(np.median(cos_seed))}


# ---------------------------------------------------------------- amplify
def build_amplify(cfg: VBenchConfig, scale: str, n: int) -> dict:
    am = cfg.fast.amplify
    t0 = time.perf_counter()
    items, v0h = _load_catalog()
    v0 = l2_normalize(v0h.astype(np.float32))
    n0, dim = v0.shape
    dest = items.column("destination").combine_chunks().dictionary_encode().indices.to_numpy()
    nbrs = _neighbors(v0, dest, am.k_nn)

    # 2. hiệu chỉnh sigma: c1 = median cosine cặp 1-NN thật; chọn sigma có median cos(v, seed) gần c1 nhất
    s = v0 @ v0.T
    np.fill_diagonal(s, -np.inf)
    c1 = float(np.median(s.max(axis=1)))
    del s
    rng_cal = np.random.default_rng(cfg.run.seed + SEED_OFFSET_AMPLIFY)
    t_cal = rng_cal.integers(0, n, size=am.calib_samples)
    calib = []
    for sg in am.sigmas:
        _, cs = _gen_block(rng_cal, v0, nbrs, t_cal, sg, am.alpha)
        calib.append({"sigma": sg, "median_cos_seed": float(np.median(cs))})
    sigmas = sorted(am.sigmas)
    best = min(calib, key=lambda c: abs(c["median_cos_seed"] - c1))["sigma"]

    # 5. kiểm tra trên mẫu thử N0 điểm; trượt thì đổi sigma theo hướng cần (LID cao → giảm nhiễu; gần trùng → tăng nhiễu)
    attempts = []
    idx = sigmas.index(best)
    tried: set[float] = set()
    chosen = None
    while 0 <= idx < len(sigmas) and sigmas[idx] not in tried:
        sg = sigmas[idx]
        tried.add(sg)
        rng_p = np.random.default_rng(cfg.run.seed + SEED_OFFSET_PILOT)
        tp = rng_p.integers(0, n, size=n0)
        vp, csp = _gen_block(rng_p, v0, nbrs, tp, sg, am.alpha)
        ck = _checks(cfg, v0, vp, csp)
        attempts.append({"sigma": sg, **ck})
        log.info("amplify pilot sigma=%.3f: LID ratio %.3f (%s), gần trùng %.4f (%s)", sg, ck["lid_ratio"], ck["lid_pass"],
                 ck["near_dup_rate"], ck["near_dup_pass"])
        if ck["lid_pass"] and ck["near_dup_pass"]:
            chosen = sg
            break
        if not ck["near_dup_pass"] or ck["lid_ratio"] < am.lid_ratio[0]:
            idx += 1
        else:
            idx -= 1
    sigma = chosen if chosen is not None else best

    # 3. sinh theo khối, ghi memmap fp16
    d = paths.data_dir(scale)
    vec_p = d / paths.VECTORS
    out = np.lib.format.open_memmap(vec_p, mode="w+", dtype=np.float16, shape=(n, dim))
    rng = np.random.default_rng(cfg.run.seed + SEED_OFFSET_AMPLIFY + 1)
    rng_m = np.random.default_rng(cfg.run.seed + SEED_OFFSET_META)
    near_cnt, cos_acc = 0, []
    writer = pq.ParquetWriter(d / paths.ITEMS, SCALE_SCHEMA)
    for a in range(0, n, am.block_rows):
        b = min(a + am.block_rows, n)
        t = np.arange(a, b)
        v, cs = _gen_block(rng, v0, nbrs, t, sigma, am.alpha)
        out[a:b] = v.astype(np.float16)
        near_cnt += int((cs >= am.near_dup_cos).sum())
        cos_acc.append(cs[:: max(1, len(cs) // 2000)])
        writer.write_table(_inherit_meta(items, t % n0, cfg, rng_m, scale, a))
        log.info("amplify %s: %d/%d", scale, b, n)
    writer.close()
    out.flush()
    del out
    gen_s = time.perf_counter() - t0

    # 5. kiểm tra trên dữ liệu thật đã sinh: mẫu N0 dòng cho LID, gần trùng trên toàn bộ
    vecs = np.load(vec_p, mmap_mode="r")
    rng_s = np.random.default_rng(cfg.run.seed + SEED_OFFSET_AMPLIFY + 2)
    samp = np.sort(rng_s.choice(n, size=n0, replace=False))
    lid_final = _checks(cfg, v0, np.asarray(vecs[samp], dtype=np.float32), np.concatenate(cos_acc))
    lid_final["near_dup_rate"] = near_cnt / n
    lid_final["near_dup_pass"] = bool(near_cnt / n < am.near_dup_max_rate)

    # 5c. thông tin: phân bố cosine top-10 của 200 query thật trên V0 so với trên tập khuếch đại
    info = {}
    qv_p = paths.data_dir("catalog", create=False) / paths.QUERY_VECTORS
    if qv_p.exists():
        qv = np.load(qv_p)
        qsel = np.random.default_rng(cfg.run.seed + SEED_OFFSET_AMPLIFY + 3).choice(len(qv), size=min(am.info_queries, len(qv)),
                                                                                    replace=False)
        _, s0 = topk_exact(v0h, qv[qsel], am.info_k, cfg.groundtruth.chunk_rows)
        _, s1 = topk_exact(vecs, qv[qsel], am.info_k, cfg.groundtruth.chunk_rows)

        def pct(x):
            return {p: float(np.nanpercentile(x, p)) for p in (10, 50, 90)}
        info = {"n_queries": int(len(qsel)), "catalog_top1": pct(s0[:, 0]), "catalog_top10": pct(s0[:, -1]),
                "amplified_top1": pct(s1[:, 0]), "amplified_top10": pct(s1[:, -1])}

    stats = {
        "scale": scale, "vectors": "amplify", "n": n, "dim": dim, "n0_seeds": n0, "seed": cfg.run.seed,
        "embed_model": json.loads((paths.data_dir("catalog", create=False) / paths.EMBED_META).read_text(encoding="utf-8")).get("model"),
        "params": am.model_dump(), "c1_median_1nn_cos": c1, "calibration": calib, "sigma_calibrated": best,
        "pilot_attempts": attempts, "sigma": sigma, "sigma_pilot_pass": chosen is not None,
        "checks": lid_final, "checks_pass": bool(lid_final["lid_pass"] and lid_final["near_dup_pass"]),
        "info_topk_cosine": info, "seconds_generate": round(gen_s, 1), "seconds_total": round(time.perf_counter() - t0, 1),
        "bytes_downloaded": 0, "correlation": "inherited (metadata kế thừa từ seed → tương quan với vùng vector)",
        "note": "Dữ liệu KHUẾCH ĐẠI: chỉ dùng cho hiệu năng và hành vi filter, không cho chất lượng tìm kiếm.",
        "vectors_sha256": sha256_file(vec_p),
    }
    dump_json(d / paths.STATS, stats)
    print(f"amplify {scale}: n={n} · sigma={sigma} (hiệu chỉnh {best}, c1={c1:.4f}) · LID ratio {lid_final['lid_ratio']:.3f} "
          f"({'PASS' if lid_final['lid_pass'] else 'FAIL'}) · gần trùng {lid_final['near_dup_rate']:.4%} "
          f"({'PASS' if lid_final['near_dup_pass'] else 'FAIL'}) · {gen_s:.0f}s")
    return stats


# ---------------------------------------------------------------- fake
def build_fake(cfg: VBenchConfig, scale: str, n: int) -> dict:
    t0 = time.perf_counter()
    items, _ = _load_catalog()
    n0 = items.num_rows
    rng = np.random.default_rng(cfg.run.seed + SEED_OFFSET_FAKE)
    seeds = rng.integers(0, n0, size=n)       # "khuôn" lấy đều trên search unit → theo tỷ lệ variant
    d = paths.data_dir(scale)
    dim = cfg.embedding.dim
    vec_p = d / paths.VECTORS
    out = np.lib.format.open_memmap(vec_p, mode="w+", dtype=np.float16, shape=(n, dim))
    writer = pq.ParquetWriter(d / paths.ITEMS, SCALE_SCHEMA)
    rng_m = np.random.default_rng(cfg.run.seed + SEED_OFFSET_META)
    bs = cfg.fast.amplify.block_rows
    for a in range(0, n, bs):
        b = min(a + bs, n)
        tb = _inherit_meta(items, seeds[a:b], cfg, rng_m, scale, a)
        out[a:b] = fake_item_vectors(tb.column("id").to_pylist(), tb.column("destination").to_pylist(),
                                     tb.column("variant").to_pylist(), dim, cfg.run.seed)
        writer.write_table(tb)
    writer.close()
    out.flush()
    del out
    vecs = np.load(vec_p, mmap_mode="r")
    nq = cfg.dataset.scale.n_queries
    qv = fake_query_vectors([f"{scale}:{i}" for i in range(nq)], np.asarray(vecs[: min(n, 200_000)]), cfg.run.seed)
    np.save(d / paths.QUERY_VECTORS, qv)
    stats = {"scale": scale, "vectors": "fake", "n": n, "dim": dim, "seed": cfg.run.seed, "bytes_downloaded": 0,
             "correlation": "fake (tâm cụm theo destination/variant)", "seconds_total": round(time.perf_counter() - t0, 1),
             "vectors_sha256": sha256_file(vec_p), "note": "Vector FAKE — chỉ để chạy thử khung."}
    dump_json(d / paths.STATS, stats)
    print(f"fake {scale}: n={n} · {stats['seconds_total']}s")
    return stats


def run_scale_data(cfg: VBenchConfig, *, scale: str, vectors: str | None, correlation: str | None) -> int:
    vectors = vectors or cfg.dataset.scale.vectors
    if scale not in cfg.dataset.scale.sizes:
        raise ValueError(f"scale '{scale}' không có trong dataset.scale.sizes {list(cfg.dataset.scale.sizes)}")
    n = cfg.dataset.scale.sizes[scale]
    if vectors == "cohere-vi":
        raise NotImplementedError("--vectors cohere-vi hoãn ở fast-track (fasttrack §3 cách B, §7); dùng --vectors amplify hoặc fake")
    if correlation not in (None, "none"):
        raise NotImplementedError("--correlation cluster chỉ áp dụng cho cohere-vi (chưa cài)")
    if vectors == "amplify":
        stats = build_amplify(cfg, scale, n)
        run_queries(cfg, scale=scale, reuse_query_vectors="catalog")
    elif vectors == "fake":
        stats = build_fake(cfg, scale, n)
        run_queries(cfg, scale=scale)
    else:
        raise ValueError(f"--vectors không hợp lệ: {vectors}")
    gt = compute_gt(cfg, scale)
    ok_gt = gt["self_check_top1_self"]["pass"] and gt["self_check_naive"]["pass"]
    qs = json.loads((paths.data_dir(scale) / paths.QUERIES_STATS).read_text(encoding="utf-8"))
    if qs.get("shortfall"):
        log.warning("bucket thiếu quota ở %s: %s", scale, qs["shortfall"])
    if vectors == "amplify" and not stats["checks_pass"]:
        log.error("dữ liệu khuếch đại TRƯỢT kiểm tra LID/gần trùng — số đo ở %s không được dùng để chốt", scale)
        return 2
    return 0 if ok_gt else 2
