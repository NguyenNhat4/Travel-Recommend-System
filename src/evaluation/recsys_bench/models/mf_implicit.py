"""`ials` và `bpr` — MF bằng `implicit`, rows = user (spec `recsys-algos-v1.md` §6).

- iALS: `AlternatingLeastSquares(factors 64, reg 0,01, iter 15, alpha 40)`; `implicit` nhân dữ liệu với α nên c = α·r = 40; user factor
  tính lại lúc chấm bằng `recalculate_user(row, U_csr[row])` (tất định khi cố định item factors).
- BPR: `BayesianPersonalizedRanking(factors 64, lr 0,01, reg 0,01, iter 100)`, negative toàn cục (phân bố popularity của implicit);
  `user_factors`/`item_factors` có cột bias → 65 cột, nhân đủ. `bpr_dest` (negative cùng destination) nằm ở `bpr_numpy.py` (Phase C).
- Tái lập: `random_state = seed`, `num_threads = 1`, `threadpoolctl.threadpool_limits(1)` quanh fit. Một scorer mỗi seed; `bench.aggregate`
  gộp theo family như arm random.
"""
from __future__ import annotations

from time import perf_counter

import numpy as np

from . import because
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
        self.matrix_events: tuple[str, ...] = ("purchase", "add_to_cart")

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
        self.matrix_events = tuple((getattr(data, "stats", None) or {}).get("events") or self.matrix_events)
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

    def explain(self, ctx: UserCtx, items: np.ndarray) -> list[list[dict]]:
        """Mặc định (bpr): u·v không phân rã theo event → không có because (không đạt FR-REC-03 nếu vào production)."""
        return [[] for _ in range(len(items))]


class Ials(_ImplicitMf):
    name = "ials"

    def __init__(self, factors: int = 64, regularization: float = 0.01, iterations: int = 15, alpha: float = 40.0, seed: int = 42):
        super().__init__(factors, regularization, iterations, seed)
        self.alpha = float(alpha)
        self._explain_weights: dict[int, object] = {}
        self.because_unmapped = 0

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

    def item_contributions(self, ctx: UserCtx, item: int) -> list[tuple[int, float]]:
        """[(unit j đã tương tác, đóng góp)] của `implicit` `explain` (Cholesky của W_u, đủ nnz của hàng): tổng = điểm ials."""
        if self.model is None or ctx.user_row is None:
            return []
        from threadpoolctl import threadpool_limits
        row = ctx.user_row
        nnz = int(self.U_csr[row].nnz)
        if nnz == 0:
            return []
        weights = self._explain_weights.get(row)
        with threadpool_limits(limits=1):
            _, top, weights = self.model.explain(row, self.U_csr, int(item), user_weights=weights, N=nnz)
        self._explain_weights[row] = weights
        return [(int(j), float(s)) for j, s in top]

    def explain(self, ctx: UserCtx, items: np.ndarray) -> list[list[dict]]:
        """because[] kind latent: đóng góp theo item j → event gần nhất cùng unit (mọi trip của khách); không map được → đếm."""
        bec, unmapped = because.latent(ctx.profile, items, lambda x: self.item_contributions(ctx, x), self.matrix_events)
        self.because_unmapped += unmapped
        return bec


class Bpr(_ImplicitMf):
    name = "bpr"

    def __init__(self, factors: int = 64, learning_rate: float = 0.01, regularization: float = 0.01, iterations: int = 100,
                 negatives: str = "global", seed: int = 42):
        super().__init__(factors, regularization, iterations, seed)
        if negatives != "global":
            raise ValueError(f"bpr negatives={negatives!r}: implicit chỉ có 'global' — negative cùng destination dùng scorer bpr_numpy "
                             "(entry bpr_dest)")
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
