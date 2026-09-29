"""Đọc items.parquet + vectors.npy một lần cho runner: payload chung (spec P5.1), id ↔ row, tên để in."""
from __future__ import annotations

import json
from functools import cached_property

import numpy as np
import pyarrow.parquet as pq

from .. import paths
from ..filters import Table

PAYLOAD_COLS = ["id", "name", "variant", "taxonomy", "destination", "available", "amenity_ids", "unit_price", "star_rating",
                "lat", "lon"]


class Dataset:
    def __init__(self, scale: str):
        self.scale = scale
        self.dir = paths.data_dir(scale, create=False)
        if not (self.dir / paths.ITEMS).exists():
            raise FileNotFoundError(f"thiếu {self.dir / paths.ITEMS} — chạy `vb dataset catalog` / `vb scale-data` trước")
        t = pq.read_table(self.dir / paths.ITEMS, columns=PAYLOAD_COLS)
        self.n = t.num_rows
        self.ids: list[str] = t.column("id").to_pylist()
        self.names: list[str] = t.column("name").to_pylist()
        self._variant = t.column("variant").to_pylist()
        self._taxonomy = t.column("taxonomy").to_pylist()
        self._destination = t.column("destination").to_pylist()
        self._available = t.column("available").to_numpy()
        la = t.column("amenity_ids").combine_chunks()
        self._am_off = la.offsets.to_numpy()
        self._am_val = la.flatten().to_numpy(zero_copy_only=False).astype(np.int16)
        self._price = t.column("unit_price").to_numpy(zero_copy_only=False).astype(np.float64)
        self._star = t.column("star_rating").to_numpy(zero_copy_only=False).astype(np.float64)
        self._lat = t.column("lat").to_numpy()
        self._lon = t.column("lon").to_numpy()

    @cached_property
    def vectors(self) -> np.ndarray:
        return np.load(self.dir / paths.VECTORS, mmap_mode="r")

    @property
    def dim(self) -> int:
        return int(self.vectors.shape[1])

    @cached_property
    def row_of(self) -> dict[str, int]:
        return {pid: i for i, pid in enumerate(self.ids)}

    @cached_property
    def table(self) -> Table:
        return Table.from_parquet(self.dir / paths.ITEMS, with_ids=False)

    @cached_property
    def query_vectors(self) -> np.ndarray:
        return np.load(self.dir / paths.QUERY_VECTORS)

    @cached_property
    def queries(self) -> list[dict]:
        with open(self.dir / paths.QUERIES, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    @cached_property
    def gt(self) -> dict[str, np.ndarray]:
        z = np.load(self.dir / paths.GT)
        return {k: z[k] for k in z.files}

    def payload(self, i: int) -> dict:
        a, b = self._am_off[i], self._am_off[i + 1]
        return {"variant": self._variant[i], "taxonomy": self._taxonomy[i], "destination": self._destination[i],
                "available": bool(self._available[i]), "amenity_ids": self._am_val[a:b].tolist(),
                "unit_price": None if np.isnan(self._price[i]) else float(self._price[i]),
                "star_rating": None if np.isnan(self._star[i]) else float(self._star[i]),
                "lat": float(self._lat[i]), "lon": float(self._lon[i])}

    def batch(self, rows: np.ndarray) -> tuple[list[str], np.ndarray, list[dict]]:
        rows = np.asarray(rows)
        order = np.argsort(rows)                       # đọc mmap theo thứ tự tăng rồi trả về đúng thứ tự yêu cầu
        vecs = np.empty((len(rows), self.dim), dtype=np.float16)
        vecs[order] = self.vectors[rows[order]]
        return [self.ids[i] for i in rows], vecs, [self.payload(int(i)) for i in rows]
