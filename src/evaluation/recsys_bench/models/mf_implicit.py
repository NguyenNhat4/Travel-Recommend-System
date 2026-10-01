"""`ials` và `bpr` — MF bằng `implicit`, rows = user (spec `recsys-algos-v1.md` §6).

- iALS: `AlternatingLeastSquares(factors 64, reg 0,01, iter 15, alpha 40)`; `implicit` nhân dữ liệu với α nên c = α·r = 40; user factor
  tính lại lúc chấm bằng `recalculate_user(row, U_csr[row])` (tất định khi cố định item factors).
- BPR: `BayesianPersonalizedRanking(factors 64, lr 0,01, reg 0,01, iter 100)`, negative toàn cục (phân bố popularity của implicit);
  `user_factors`/`item_factors` có cột bias → 65 cột, nhân đủ. `bpr_dest` (negative cùng destination) chưa có cài đặt → `status: not_run`.
- Tái lập: `random_state = seed`, `num_threads = 1`, `threadpoolctl.threadpool_limits(1)` quanh fit. Một scorer mỗi seed; `bench.aggregate`
  gộp theo family như arm random.
"""
from __future__ import annotations

from time import perf_counter

import numpy as np

from .base import TrainData, UserCtx
from .knn_implicit import require_implicit


class _ImplicitMf:
    needs_vectors = False
    rows = "user"
    name = "mf"

    def __init__(self, factors: int = 64, regularization: float = 0.01, iterations: int = 15, seed: int = 42):
        self.factors, self.regularization, self.iterations, self.seed = int(factors), float(regularization), int(iterations), int(seed)
        self.model = None
        self.U_csr = None
        self.item_factors: np.ndarray | None = None
        self._user_cache: dict[int, np.ndarray] = {}

    def _make(self):  # pragma: no cover - lớp con
        raise NotImplementedError

    def _user_vector(self, row: int) -> np.ndarray:  # pragma: no cover - lớp con
        raise NotImplementedError

    def _params(self) -> dict:
        return {"factors": self.factors, "regularization": self.regularization, "iterations": self.iterations, "seed": self.seed}

    def fit(self, data: TrainData) -> dict:
        implicit = require_implicit()
        from threadpoolctl import threadpool_limits
        t0 = perf_counter()
        self.U_csr = data.csr_U()
        with threadpool_limits(limits=1):
            model = self._make()
            model.fit(self.U_csr, show_progress=False)
        self.model = model
        self.item_factors = np.asarray(model.item_factors, dtype=np.float32)
        self._user_cache.clear()
        return {"params": self._params(), "rows": "user", "nRows": int(data.U.shape[0]), "nnzU": int(data.U.sum()),
                "itemFactorShape": list(self.item_factors.shape), "implicitVersion": implicit.__version__,
                "fitSeconds": round(perf_counter() - t0, 3)}

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
        if self.model is None or ctx.user_row is None:
            return np.zeros(len(cand), dtype=np.float32)
        u = self._user_cache.get(ctx.user_row)
        if u is None:
            u = np.asarray(self._user_vector(ctx.user_row), dtype=np.float32)
            self._user_cache[ctx.user_row] = u
        return (self.item_factors[cand] @ u).astype(np.float32)

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None:
        return None


class Ials(_ImplicitMf):
    name = "ials"

    def __init__(self, factors: int = 64, regularization: float = 0.01, iterations: int = 15, alpha: float = 40.0, seed: int = 42):
        super().__init__(factors, regularization, iterations, seed)
        self.alpha = float(alpha)

    def _params(self) -> dict:
        return {**super()._params(), "alpha": self.alpha, "confidence": f"c = alpha*r = {self.alpha:g}", "userVector": "recalculate_user"}

    def _make(self):
        from implicit.als import AlternatingLeastSquares
        return AlternatingLeastSquares(factors=self.factors, regularization=self.regularization, iterations=self.iterations,
                                       alpha=self.alpha, use_gpu=False, calculate_training_loss=False, num_threads=1,
                                       random_state=self.seed)

    def _user_vector(self, row: int) -> np.ndarray:
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=1):
            return np.asarray(self.model.recalculate_user(row, self.U_csr[row]), dtype=np.float32).ravel()


class Bpr(_ImplicitMf):
    name = "bpr"

    def __init__(self, factors: int = 64, learning_rate: float = 0.01, regularization: float = 0.01, iterations: int = 100,
                 negatives: str = "global", seed: int = 42):
        super().__init__(factors, regularization, iterations, seed)
        if negatives != "global":
            raise ValueError(f"bpr negatives={negatives!r}: tuần này chỉ 'global' (bpr_dest: status not_run)")
        self.learning_rate, self.negatives = float(learning_rate), negatives

    def _params(self) -> dict:
        return {**super()._params(), "learningRate": self.learning_rate, "negatives": self.negatives, "bias": "factors+1 cột"}

    def _make(self):
        from implicit.bpr import BayesianPersonalizedRanking
        return BayesianPersonalizedRanking(factors=self.factors, learning_rate=self.learning_rate, regularization=self.regularization,
                                           iterations=self.iterations, use_gpu=False, num_threads=1, verify_negative_samples=True,
                                           random_state=self.seed)

    def _user_vector(self, row: int) -> np.ndarray:
        return np.asarray(self.model.user_factors[row], dtype=np.float32)
