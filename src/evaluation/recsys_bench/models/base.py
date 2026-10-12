"""Hợp đồng chung của registry thuật toán (Day 4–5 R3; `docs/spec/bench/recsys-algos-v1.md` §0).

Một scorer chỉ làm hai việc: `fit(data)` trên X_train toàn cục của split và `score(ctx, cand)` trả điểm float32 cho một tập ứng viên
(chỉ số unit toàn cục). Mọi thứ còn lại — mask, pool, phá hoà, MMR, metric — nằm ở `funnel.py` và dùng chung cho mọi scorer, để bảng
so sánh đo *scorer* chứ không đo cách lấy lịch sử hay cách lọc.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Protocol

import numpy as np

from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.recommendation.profile import Profile


@dataclass
class TrainData:
    """X_train của một split (spec §0.2) và các ma trận nhị phân dựng từ nó. Dựng **một lần** mỗi run (`data.build`)."""

    index: UnitIndex
    x_train: list[dict]                              # ⊆ kept, đã cắt theo khách (LLBO: < as_of_u của khách test; temporal: < T)
    B: np.ndarray                                    # uint8 (T, I): hàng = (cdpUserId, eventGroupId), ô = purchase ∨ add_to_cart
    trip_rows: dict[tuple[str, str], int]
    U: np.ndarray                                    # uint8 (U, I): hàng = user (gồm cả event thiếu gid)
    user_rows: dict[str, int]
    E: np.ndarray                                    # float32 (I, d) theo thứ tự index.units; hàng 0 khi unit chưa có vector
    has_vec: np.ndarray                              # bool (I,)
    product_ids: np.ndarray                          # str (I,) — khoá phá hoà cuối (item_id tăng dần)
    stats: dict = field(default_factory=dict)

    @property
    def n_items(self) -> int:
        return len(self.index.units)

    def csr_B(self):
        """CSR của B (scipy import lười — chỉ scorer `implicit` cần)."""
        from scipy.sparse import csr_matrix
        return csr_matrix(self.B.astype(np.float32))

    def csr_U(self):
        from scipy.sparse import csr_matrix
        return csr_matrix(self.U.astype(np.float32))


@dataclass
class Seeds:
    """Tập seed S và trọng số w_e của một khách (spec §0.3), lấy từ `build_profile` của engine — không tự tính lại."""

    units: np.ndarray                                # int64 (n,) chỉ số unit toàn cục (có thể lặp: nhiều event cùng unit)
    weights: np.ndarray                              # float32 (n,)
    branch: str                                      # "short" (có trip mở) | "long" (không) | "none" (không trip nào)

    @property
    def total(self) -> float:
        return float(self.weights.sum()) if self.weights.size else 0.0


@dataclass
class UserCtx:
    """Ngữ cảnh một khách tại `as_of`, dùng chung cho mọi scorer trong run (`funnel.CtxCache`)."""

    user: str
    as_of: datetime
    profile: Profile                                 # build_profile(...) với E_full chỉ số toàn cục; profile.trips rỗng = engine đi popular
    seeds: Seeds
    pop: np.ndarray                                  # float32 (I,) = popularity_at(as_of).unit_scores(destination) (None → toàn cục)
    pop_dict: dict[int, float]                       # dict gốc của unit_scores — giữ thứ tự chèn để pool engine hoà đúng như engine
    destination: str | None                          # điểm đến của trip mở, None nếu không có
    excluded: set[str]                               # taxonomy đã mua trong trip mở
    bought: set[int]                                 # unit đã mua (mọi trip) — luôn bị loại
    user_row: int | None                             # hàng trong TrainData.U, None nếu khách không có event trong X_train
    origin: str | None = None                        # điểm xuất phát chuyến bay của khách (`profile.infer_origin`, FR-REC-04 09/10)
    next_trip_scoring: bool = False                  # engine chấm F14c ở nhánh không chuyến mở (bật + đúng tag model, PR-B 09/10)

    @property
    def strategy(self) -> str:
        return self.profile.strategy if self.profile.trips else "popular"


class Scorer(Protocol):
    """Giao thức scorer. `fit` trả fit-log (dict JSON-được) ghi vào `summary.fitLog`; `score` trả float32 cùng chiều `cand`;
    `collab_part` trả phần điểm cộng tác (để tính `collab_coverage`) hoặc None khi scorer không có vế đó."""

    name: ClassVar[str]
    needs_vectors: ClassVar[bool]
    rows: ClassVar[str]                              # "trip" | "user" | "none"

    def fit(self, data: TrainData) -> dict: ...

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray: ...

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None: ...
