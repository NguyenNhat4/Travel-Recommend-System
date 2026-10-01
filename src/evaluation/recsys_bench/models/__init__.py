"""Registry thuật toán cho bảng so sánh recsys (Day 4–5 R3–R5; `docs/spec/bench/recsys-algos-v1.md`).

Scorer được nạp **lười** theo tên để `--help` và các arm numpy không cần `scipy` / `implicit`.
"""
from __future__ import annotations

import importlib

#: tên scorer trong `algos_v1.yaml` → (module, class)
SCORER_MODULES: dict[str, tuple[str, str]] = {
    "content": ("content", "ContentProfile"),
    "cooc_trip": ("cooc", "CoocTrip"),
    "star_blend": ("star", "StarBlend"),
    "ease": ("ease", "Ease"),
    "rp3beta": ("rp3beta", "Rp3Beta"),
    "itemknn": ("knn_implicit", "ItemKnn"),
    "ials": ("mf_implicit", "Ials"),
    "bpr": ("mf_implicit", "Bpr"),
}


def get_scorer_class(name: str):
    if name not in SCORER_MODULES:
        raise KeyError(f"scorer không có trong registry: {name!r} (có: {sorted(SCORER_MODULES)})")
    module, cls = SCORER_MODULES[name]
    return getattr(importlib.import_module(f"{__name__}.{module}"), cls)
