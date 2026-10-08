"""Tên cấu hình bench OPH-L → cài vào engine production trong tiến trình đo (plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md`
§4, §5.1). Engine không sửa: mọi thứ là monkeypatch trên `use_cases` / `Popularity` + bọc `VectorSearchPort` và hậu xử lý ô B.

Tên cấu hình = các token nối bằng `+` (bí danh mở rộng đệ quy):

    P0 | P2          profile nền: production | P2 của PR-A (confidence + CAP_EXEMPT_EVENTS)
    F0 | F14c        công thức nhánh không chuyến mở: production | F14c (cal(cos) 0,65 + pop 0,35, Q ghim)
    destCap<N>       tối đa N món / điểm đến khi không có chuyến mở (`dest_diversity`)
    slotB            ô khám phá B của PR-A: lấp ô trống bằng món ở điểm đến khác theo cos(u_long), 1 món / điểm đến
    book | sess      ưu tiên chuyến đã đặt (I-3, O3) | + chuyến ảo T_S từ các chuyến chỉ-xem (O4); `sessH:<ngày>`
    orig:pen:<w>     phạt route sai điểm xuất phát ở nhánh mở (O1); nhánh không chuyến luôn mask
    orig:mask        mask ở mọi nhánh (O2)
    cart:<w>         + w·cart ở nhánh mở và đưa món trong giỏ vào pool (O5); `cartPool` = chỉ pool
    popH:<H>:<α>     pop_h ở nhánh không chuyến (N1); `popBox:<W>:<α>` hộp W ngày (parity với α = 0, W = 90);
                     `popScope:global` áp mọi nhánh (D-popGlobal)
    dormHL:<m>       khách P3_dormant dựng u_long với H_LONG × m (N2) · `dormPop:<w>` w_pop của P3 (N3)
    p2Pop:<w>        w_pop của P2_first_time ở nhánh không chuyến (N4) · `dormDays:<d>` ngưỡng dormant (mặc định 365)
    oph              ép chạy qua đường code OPH kể cả khi mọi công tắc tắt (cổng parity V0p/V1p/V2p)

Trần (rò có chủ đích, chỉ để đo khoảng trống — plan §4.2, không bao giờ là ứng viên):
    origTgt          Z-orig: `ô` = điểm xuất phát của route đích khi đích là chuyến bay (còn lại suy từ event)
    cartTgt          Z-cart: món đích coi như nằm trong giỏ (vào pool nếu qua mask + cộng W_CART)
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

import src.backend.app.application.recommendation.use_cases as UC
from src.backend.app.domain.recommendation import build_profile as prod_build
from src.backend.app.domain.recommendation import mmr_select as prod_mmr
from src.backend.app.domain.recommendation import score_candidates as prod_score
from src.evaluation.recsys_bench.theme_study import dest_diversity, pop_smooth
from src.evaluation.recsys_bench.theme_study.layered_profile import DORMANT_DAYS, make_layered_build_profile
from src.evaluation.recsys_bench.theme_study.oph_scorer import Q_HIGH, Q_LOW, make_scorer
from src.evaluation.recsys_bench.theme_study.pool import CartPool
from src.evaluation.recsys_bench.theme_study.profile_variants import make_build_profile

ALIASES = {
    "B0": "P0+F0",
    "B1p": "P2+F0+slotB",
    "B2": "P2+F14c+destCap2+slotB",
    "V0p": "B0+oph",
    "V1p": "B1p+oph",
    "V2p": "B2+oph",
    # bậc mặc định (tham số khởi tạo của plan §3.3); grid truyền tên tường minh
    "O1": "B1p+orig:pen:0.3",
    "O2": "B1p+orig:mask",
    "O3": "O1+book",
    "O4": "O3+sess",
    "O5": "O4+cart:0.05",
    "N1": "B2+popH:90:1",
    "N2": "N1+dormHL:3",
    "N3": "N2+dormPop:0.5",
    "N4": "N3+p2Pop:0.45",
}
EXPLORE_TAX = ("hotel", "attraction", "combo")


@dataclass(frozen=True)
class Config:
    name: str
    confidence: bool = False
    cap_exempt: bool = False
    none_scorer: str = "F0"
    dest_cap: int = 0
    slot_b: bool = False
    booked_first: bool = False
    session_agg: bool = False
    h_session: float = 7.0
    origin_mode: str | None = None
    w_origin: float = 0.30
    w_cart: float = 0.0
    cart_pool: bool = False
    pop_h: float | None = None
    pop_box: float | None = None
    pop_alpha: float = 0.0
    pop_scope: str = "none"
    dormant_hl_mult: float = 1.0
    dormant_days: float = DORMANT_DAYS
    w_pop_by_segment: dict = field(default_factory=dict)
    force_oph: bool = False
    origin_target: bool = False
    cart_target: bool = False

    @property
    def needs_scorer(self) -> bool:
        return (self.force_oph or self.none_scorer != "F0" or self.origin_mode is not None or bool(self.w_cart)
                or bool(self.w_pop_by_segment) or self.cart_target)


def expand(name: str, _depth: int = 0) -> list[str]:
    if _depth > 10:
        raise ValueError(f"bí danh lặp vô hạn: {name}")
    out: list[str] = []
    for tok in name.split("+"):
        out += expand(ALIASES[tok], _depth + 1) if tok in ALIASES else [tok]
    return out


def parse(name: str) -> Config:
    c = Config(name=name)
    for tok in expand(name):
        head, *rest = tok.split(":")
        if tok == "P0":
            pass
        elif tok == "P2":
            c = replace(c, confidence=True, cap_exempt=True)
        elif tok in ("F0", "F14c"):
            c = replace(c, none_scorer=tok)
        elif tok.startswith("destCap"):
            c = replace(c, dest_cap=int(tok[len("destCap"):]))
        elif tok == "slotB":
            c = replace(c, slot_b=True)
        elif tok == "book":
            c = replace(c, booked_first=True)
        elif tok == "sess":
            c = replace(c, booked_first=True, session_agg=True)
        elif head == "sessH":
            c = replace(c, h_session=float(rest[0]))
        elif head == "orig":
            mode = rest[0]
            if mode not in ("pen", "mask"):
                raise ValueError(f"{tok}: orig:pen:<w> | orig:mask")
            c = replace(c, origin_mode=mode, w_origin=float(rest[1]) if mode == "pen" else c.w_origin)
        elif head == "cart":
            c = replace(c, w_cart=float(rest[0]), cart_pool=True)
        elif tok == "cartPool":
            c = replace(c, cart_pool=True)
        elif head == "popH":
            c = replace(c, pop_h=float(rest[0]), pop_box=None, pop_alpha=float(rest[1]))
        elif head == "popBox":
            c = replace(c, pop_box=float(rest[0]), pop_h=None, pop_alpha=float(rest[1]))
        elif head == "popScope":
            c = replace(c, pop_scope=rest[0])
        elif head == "dormHL":
            c = replace(c, dormant_hl_mult=float(rest[0]))
        elif head == "dormDays":
            c = replace(c, dormant_days=float(rest[0]))
        elif head == "dormPop":
            c = replace(c, w_pop_by_segment={**c.w_pop_by_segment, "P3_dormant": float(rest[0])})
        elif head == "p2Pop":
            c = replace(c, w_pop_by_segment={**c.w_pop_by_segment, "P2_first_time": float(rest[0])})
        elif tok == "oph":
            c = replace(c, force_oph=True)
        elif tok == "origTgt":
            c = replace(c, origin_target=True)
        elif tok == "cartTgt":
            c = replace(c, cart_target=True, cart_pool=True)
        else:
            raise ValueError(f"token cấu hình lạ {tok!r} trong {name!r}")
    if c.w_pop_by_segment and c.none_scorer == "F0":
        raise ValueError(f"{name}: dormPop / p2Pop chỉ áp cho F14c (nhánh không chuyến của F0 là công thức production)")
    return c


class Installed:
    """Cài một cấu hình; `state` là ô dùng chung của request đang chạy (engine xử lý tuần tự)."""

    def __init__(self, cfg: Config, index, engines: list, q: tuple[float, float] = (Q_LOW, Q_HIGH)):
        self.cfg, self.index, self.engines = cfg, index, engines
        self.state: dict = {}
        #: Thông tin của người đo (đích bị giấu) — chỉ cấu hình trần đọc; `eval_oph` đặt trước mỗi khách.
        self.hint: dict = {}
        self._restore = []
        base = make_build_profile(confidence=cfg.confidence, cap_exempt=cfg.cap_exempt)
        # Lớp luôn cài: mọi công tắc tắt thì trả đúng đối tượng của bản nền (không đổi kết quả), nhưng ghi `segment` / `ctx0`
        # cho mọi cấu hình kể cả B0 — để phân tầng ghép cặp có cùng nhãn ở hai phía.
        bp = make_layered_build_profile(base, self.state, booked_first=cfg.booked_first, session_agg=cfg.session_agg,
                                        h_session=cfg.h_session, dormant_hl_mult=cfg.dormant_hl_mult,
                                        dormant_days=cfg.dormant_days, confidence=cfg.confidence)
        mmr, space_cls = prod_mmr, UC._LocalSpace
        if cfg.dest_cap:
            bp, mmr, space_cls = dest_diversity.install(bp, cfg.dest_cap)
        state = self.state

        class Space(space_cls):                                   # noqa: D401 - giữ request hiện tại cho scorer / pool
            def __init__(self, index_, dimension):
                state.clear()
                super().__init__(index_, dimension)
                state["space"] = self

        scorer = make_scorer(state, index, none_scorer=cfg.none_scorer, w_pop_by_segment=cfg.w_pop_by_segment,
                             origin_mode=cfg.origin_mode, w_origin=cfg.w_origin, w_cart=cfg.w_cart, q=q,
                             hint=self.hint if (cfg.origin_target or cfg.cart_target) else None,
                             origin_target=cfg.origin_target, cart_target=cfg.cart_target) \
            if cfg.needs_scorer else prod_score
        UC.build_profile, UC.score_candidates, UC.mmr_select, UC._LocalSpace = bp, scorer, mmr, Space
        if cfg.pop_h is not None or cfg.pop_box is not None:
            self._restore.append(pop_smooth.install(index, state, cfg.pop_h, cfg.pop_alpha, box=cfg.pop_box,
                                                    scope=cfg.pop_scope))
        if cfg.cart_pool:
            for eng in engines:
                inner = eng.vectors
                eng.vectors = CartPool(inner, index, state, hint=self.hint if cfg.cart_target else None)
                self._restore.append(lambda e=eng, v=inner: setattr(e, "vectors", v))

    def recommend(self, eng, uid, as_of, k, events) -> dict:
        resp = eng.recommend(uid, as_of, k, events)
        if self.cfg.slot_b:
            resp = explore_fill(resp, k, self.state, self.index, eng.vectors, events)
        return resp

    def restore(self):
        for f in reversed(self._restore):
            f()
        UC.build_profile, UC.score_candidates = prod_build, prod_score
        UC.mmr_select, UC._LocalSpace = prod_mmr, _PROD_SPACE


_PROD_SPACE = UC._LocalSpace


def explore_fill(resp: dict, k: int, state: dict, index, vectors, events) -> dict:
    """Gương ô B của PR-A (`_explore_fill` sau `mmr_select`): chỉ khi có chuyến mở và list < k; một `near_vector(u_long)` trên
    điểm đến ≠ X, recommendable, taxonomy hotel/attraction/combo, chưa mua; mỗi điểm đến tối đa 1 món, xếp **sau** list."""
    recs = resp.get("recommendations") or []
    prof = state.get("profile")
    if len(recs) >= k or prof is None or prof.active_trip is None or not recs:
        return resp
    x = resp.get("destination")
    m = index.mask(only_recommendable=True) & np.isin(index.taxonomy, EXPLORE_TAX)
    if x:
        m &= index.destination != x
    for e in events:
        if e.get("eventName") == "purchase":
            g = index.resolve(str(e.get("productId") or ""))
            if g is not None:
                m[g] = False
    have = {r["productId"] for r in recs}
    used = {r.get("destination") for r in recs}
    extra = []
    for h in vectors.near_vector(prof.u_long, index.allowed_ids(m), 50):
        g = index.idx.get(h.product_id)
        if g is None or h.product_id in have:
            continue
        d = str(index.destination[g])
        if d in used:
            continue
        used.add(d)
        extra.append({"productId": h.product_id, "destination": d, "taxonomy": str(index.taxonomy[g]), "explore": True,
                      "because": []})
        if len(recs) + len(extra) >= k:
            break
    return {**resp, "recommendations": recs + extra}
