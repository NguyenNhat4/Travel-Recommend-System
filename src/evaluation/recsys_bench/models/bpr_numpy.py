"""`bpr_numpy` / `bpr_dest` — BPR viết bằng numpy với sampler negative cắm được (Day 5 Phase C; spec `recsys-algos-v1.md` §6.3).

Vì sao không dùng `implicit`: `BayesianPersonalizedRanking` 0.7.3 (CPU) không nhận phân phối negative — sampler cố định là "chỉ số
ô nnz đều" (tức theo popularity) và bỏ mẫu khi trúng item đã thích. `bpr_dest` cần negative **cùng destination với item dương**, nên viết
lại cùng công thức:

- khởi tạo như `implicit/gpu/bpr.py`: `Y` rồi `X` = `(rand − 0,5)/F` với F+1 cột (cột cuối = bias item; user giữ 1), hàng không tương
  tác = 0;
- mỗi epoch rút `nnz` mẫu có hoàn lại `(u, i⁺)` = ô nnz đều (user được chọn tỉ lệ số tương tác, như implicit);
- cập nhật theo `implicit/gpu/bpr.cu:45-63`, mọi vế dùng giá trị cũ: `x̂ = X_u·(Y_i − Y_j)`, `z = σ(−x̂)`,
  `Y_i += lr(z·X_u − reg·Y_i)`, `Y_j += lr(−z·X_u − reg·Y_j)`, `X_u[:F] += lr(z·(Y_i − Y_j)[:F] − reg·X_u[:F])`; `z < 0,5` → mẫu đúng
  (train AUC trong fit log).

Sampler negative:

- `global` — `i⁻ = itemids[U{nnz}]` (theo popularity, như implicit); `U[u, i⁻] = 1` → bỏ mẫu.
- `same_destination` — `i⁻` rút trong destination của `i⁺`: `dest_distribution: uniform` đều trên mọi search unit cùng destination (kể
  cả unit chưa ai tương tác — chúng nhận bias âm, khác implicit nơi chúng giữ 0; tác dụng phụ có chủ đích của "cùng destination"),
  `pop` theo tần suất nnz trong destination; trúng item đã thích → rút lại ≤ `max_resample` lần rồi bỏ mẫu; destination có ít hơn
  `min_dest_items` ứng viên → lùi về `global` (đếm `sharePositivesFallback`).

Không bit-identical với implicit (luồng RNG khác: `numpy.default_rng` vs mt19937 của implicit; thứ tự cập nhật theo bản GPU có nguồn,
bản CPU `.pyx` không có nguồn trong wheel). `explain` trả `[]`: u·v không phân rã theo event → không đạt FR-REC-03 nếu vào production.
"""
from __future__ import annotations

import math
from time import perf_counter

import numpy as np

from .base import TrainData, UserCtx

NEGATIVES = ("global", "same_destination")
DEST_DISTRIBUTIONS = ("uniform", "pop")


def init_factors(rng: np.random.Generator, n_users: int, n_items: int, factors: int, user_counts: np.ndarray,
                 item_counts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(X user, Y item) float32 (·, F+1). Mirror `implicit/gpu/bpr.py:108-123`: Y rút trước X; hàng không tương tác = 0; X[:, F] = 1."""
    Y = ((rng.random((n_items, factors + 1)) - 0.5) / factors).astype(np.float32)
    X = ((rng.random((n_users, factors + 1)) - 0.5) / factors).astype(np.float32)
    Y[np.asarray(item_counts) == 0] = 0.0
    X[np.asarray(user_counts) == 0] = 0.0
    X[:, factors] = 1.0
    return X, Y


class DestinationPools:
    """Ứng viên negative theo destination: `uniform` = mọi unit cùng destination; `pop` = itemids của các ô nnz cùng destination."""

    def __init__(self, dest_of: np.ndarray, itemids_nnz: np.ndarray, distribution: str = "uniform"):
        if distribution not in DEST_DISTRIBUTIONS:
            raise ValueError(f"dest_distribution={distribution!r}: chỉ {DEST_DISTRIBUTIONS}")
        codes, self.dest_code = np.unique(np.asarray(dest_of).astype(str), return_inverse=True)
        self.n_dest = len(codes)
        members = np.arange(len(dest_of)) if distribution == "uniform" else np.asarray(itemids_nnz)
        member_dest = self.dest_code[members]
        order = np.argsort(member_dest, kind="stable")
        self.pool = members[order].astype(np.int64)
        self.size = np.bincount(member_dest, minlength=self.n_dest).astype(np.int64)
        self.start = np.concatenate([[0], np.cumsum(self.size)[:-1]]).astype(np.int64)

    def draw(self, rng: np.random.Generator, pos_items: np.ndarray) -> np.ndarray:
        d = self.dest_code[pos_items]
        offs = np.floor(rng.random(len(pos_items)) * np.maximum(self.size[d], 1)).astype(np.int64)
        return self.pool[self.start[d] + np.minimum(offs, np.maximum(self.size[d] - 1, 0))]


def sample_negatives(rng: np.random.Generator, users: np.ndarray, pos_items: np.ndarray, liked: np.ndarray, *, kind: str,
                     itemids_nnz: np.ndarray, dest_pools: DestinationPools | None = None, min_dest_items: int = 20,
                     max_resample: int = 10) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(neg, keep, fallback): `keep` = mẫu không bỏ; `fallback` = mẫu dương có destination quá nhỏ nên rút global.
    `liked` là ma trận user × item (bool / uint8) của X_train."""
    n = len(pos_items)
    neg = np.asarray(itemids_nnz)[rng.integers(0, len(itemids_nnz), size=n)]
    if kind == "global":
        return neg, ~liked[users, neg].astype(bool), np.zeros(n, dtype=bool)
    if kind != "same_destination" or dest_pools is None:
        raise ValueError(f"negatives={kind!r}: chỉ {NEGATIVES} (same_destination cần dest_pools)")
    fallback = dest_pools.size[dest_pools.dest_code[pos_items]] < min_dest_items
    keep = np.ones(n, dtype=bool)
    keep[fallback] = ~liked[users[fallback], neg[fallback]].astype(bool)
    own = np.flatnonzero(~fallback)
    if len(own):
        neg[own] = dest_pools.draw(rng, pos_items[own])
        bad = own[liked[users[own], neg[own]].astype(bool)]
        for _ in range(max_resample):
            if not len(bad):
                break
            neg[bad] = dest_pools.draw(rng, pos_items[bad])
            bad = bad[liked[users[bad], neg[bad]].astype(bool)]
        keep[bad] = False
    return neg, keep, fallback


def sgd_step(X: np.ndarray, Y: np.ndarray, u: int, i: int, j: int, lr: float, reg: float) -> bool:
    """Một cập nhật BPR (in-place), mọi vế dùng giá trị cũ — `implicit/gpu/bpr.cu:45-63`. Trả True khi mẫu đã xếp đúng (z < 0,5)."""
    xu = X[u].copy()
    diff = Y[i] - Y[j]
    z = 1.0 / (1.0 + math.exp(float(xu @ diff)))
    Y[i] += lr * (z * xu - reg * Y[i])
    Y[j] += lr * (-z * xu - reg * Y[j])
    F = X.shape[1] - 1
    X[u, :F] += lr * (z * diff[:F] - reg * xu[:F])
    return z < 0.5


def sgd_epoch(rng: np.random.Generator, userids: np.ndarray, itemids: np.ndarray, liked: np.ndarray, X: np.ndarray, Y: np.ndarray,
              lr: float, reg: float, *, kind: str, dest_pools: DestinationPools | None, min_dest_items: int,
              max_resample: int) -> dict:
    """Một epoch: `nnz` mẫu có hoàn lại; rút negative theo vector rồi cập nhật tuần tự (SGD như implicit)."""
    nnz = len(userids)
    idx = rng.integers(0, nnz, size=nnz)
    users, pos = userids[idx], itemids[idx]
    neg, keep, fallback = sample_negatives(rng, users, pos, liked, kind=kind, itemids_nnz=itemids, dest_pools=dest_pools,
                                           min_dest_items=min_dest_items, max_resample=max_resample)
    correct = 0
    for u, i, j in zip(users[keep].tolist(), pos[keep].tolist(), neg[keep].tolist()):
        correct += sgd_step(X, Y, u, i, j, lr, reg)
    kept = int(keep.sum())
    return {"samples": nnz, "kept": kept, "skipped": nnz - kept, "correct": correct, "fallback": int(fallback.sum())}


class BprNumpy:
    name = "bpr_numpy"
    needs_vectors = False
    rows = "user"

    def __init__(self, factors: int = 64, learning_rate: float = 0.01, regularization: float = 0.01, iterations: int = 100,
                 negatives: str = "global", min_dest_items: int = 20, dest_distribution: str = "uniform", max_resample: int = 10,
                 seed: int = 42):
        if negatives not in NEGATIVES:
            raise ValueError(f"bpr_numpy negatives={negatives!r}: chỉ {NEGATIVES}")
        if dest_distribution not in DEST_DISTRIBUTIONS:
            raise ValueError(f"bpr_numpy dest_distribution={dest_distribution!r}: chỉ {DEST_DISTRIBUTIONS}")
        self.factors, self.learning_rate, self.regularization = int(factors), float(learning_rate), float(regularization)
        self.iterations, self.negatives, self.min_dest_items = int(iterations), negatives, int(min_dest_items)
        self.dest_distribution, self.max_resample, self.seed = dest_distribution, int(max_resample), int(seed)
        self.user_factors: np.ndarray | None = None
        self.item_factors: np.ndarray | None = None

    def _params(self) -> dict:
        p = {"factors": self.factors, "learningRate": self.learning_rate, "regularization": self.regularization,
             "iterations": self.iterations, "negatives": self.negatives, "seed": self.seed, "bias": "factors+1 cột"}
        if self.negatives == "same_destination":
            p.update({"minDestItems": self.min_dest_items, "destDistribution": self.dest_distribution, "maxResample": self.max_resample})
        return p

    def fit(self, data: TrainData) -> dict:
        t0 = perf_counter()
        U = np.asarray(data.U)
        liked = U.astype(bool)
        userids, itemids = (a.astype(np.int64) for a in np.nonzero(U))
        rng = np.random.default_rng(self.seed)
        X, Y = init_factors(rng, U.shape[0], U.shape[1], self.factors, U.sum(axis=1), U.sum(axis=0))
        pools = DestinationPools(data.index.destination, itemids, self.dest_distribution) if self.negatives == "same_destination" else None
        totals = {"samples": 0, "kept": 0, "skipped": 0, "correct": 0, "fallback": 0}
        last = None
        if len(userids):
            for _ in range(self.iterations):
                last = sgd_epoch(rng, userids, itemids, liked, X, Y, self.learning_rate, self.regularization, kind=self.negatives,
                                 dest_pools=pools, min_dest_items=self.min_dest_items, max_resample=self.max_resample)
                for key in totals:
                    totals[key] += last[key]
        self.user_factors, self.item_factors = X, Y
        log = {"params": self._params(), "rows": "user", "nRows": int(U.shape[0]), "nnzU": int(len(userids)),
               "itemFactorShape": list(Y.shape),
               "trainAucLastEpoch": round(last["correct"] / last["kept"], 4) if last and last["kept"] else None,
               "skippedShare": round(totals["skipped"] / totals["samples"], 4) if totals["samples"] else None,
               "because": "none — u·v không phân rã theo event", "implementation": "numpy SGD tuần tự (không bit-identical với implicit)",
               "fitSeconds": round(perf_counter() - t0, 3)}
        if pools is not None:
            pos_dest = pools.dest_code[itemids]
            log["destStats"] = {"nDestinations": int(pools.n_dest),
                                "eligibleDestinations": int((pools.size >= self.min_dest_items).sum()),
                                "sharePositivesFallback": round(float(np.mean(pools.size[pos_dest] < self.min_dest_items)), 4)
                                if len(itemids) else None,
                                "shareSamplesFallback": round(totals["fallback"] / totals["samples"], 4) if totals["samples"] else None,
                                "medianPoolSize": float(np.median(pools.size)) if pools.n_dest else None}
        return log

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
        if self.item_factors is None or ctx.user_row is None:
            return np.zeros(len(cand), dtype=np.float32)
        return (self.item_factors[cand] @ self.user_factors[ctx.user_row]).astype(np.float32)

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None:
        return None

    def explain(self, ctx: UserCtx, items: np.ndarray) -> list[list[dict]]:
        return [[] for _ in range(len(items))]
