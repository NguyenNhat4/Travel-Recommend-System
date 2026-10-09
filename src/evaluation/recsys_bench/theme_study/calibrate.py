"""Calibrate lại ngưỡng F14c (`SEMANTIC_Q_LOW` / `SEMANTIC_Q_HIGH`) — chạy khi đổi model embedding hoặc text builder
(đề xuất `docs/prd/update-archive/2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md`, PR-B 09/10).

Lấy phân vị p10 / p99 của `cos(u_long, v)` trên đúng không gian ứng viên engine chấm cho khách giả lập `between` (seed riêng,
mặc định 99 — khác mọi seed đo), với profile engine hiện tại. In bản đề nghị cùng hằng đang ship để so; **không** sửa code.

    python -m src.evaluation.recsys_bench.theme_study.calibrate --vec npy:<prefix> --as-of 2026-10-08T00:00:00+00:00 \
        --seeds 99,7,2026 --out calib.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

from src.backend.app.domain.recommendation import build_profile
from src.backend.app.domain.recommendation import profile as P
from src.evaluation.recsys_bench.theme_study import theme_exp as TE
from src.evaluation.recsys_bench.theme_study.step2_scorers import calibrate_quantile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vec", required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--seeds", default="99", help="seed tập calibration (khác seed đo); nhiều seed để xem độ bền")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    TE.AS_OF = datetime.fromisoformat(a.as_of)
    idx, vec = TE.load_index(a.vec)
    purchases = [e for e in TE.load_events() if e["eventName"] == "purchase"]
    # engine không F14c khi đo ngưỡng (công thức chấm không ảnh hưởng cos(u_long, v) nhưng giữ đúng cách đo 08/10)
    eng = TE.OfflineEngine(idx, vec, purchases, mode="prod", next_trip_scoring=False, max_per_destination=0)
    w = TE.World(idx, vec, [e for e in purchases if TE.parse_ts(e["timestamp"]) < TE.AS_OF])
    runs = [calibrate_quantile(eng, w, build_profile, TE.AS_OF, seed=int(s)) for s in a.seeds.split(",") if s]
    out = {"modelVersion": idx.model_version, "shipped": {"q_low": P.SEMANTIC_Q_LOW, "q_high": P.SEMANTIC_Q_HIGH,
                                                           "modelVersion": P.SEMANTIC_CALIBRATION_MODEL_VERSION},
           "tagMatches": P.calibration_applies(idx.model_version), "runs": runs}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
