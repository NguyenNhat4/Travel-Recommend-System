#!/usr/bin/env python3
"""Compatibility CLI for the canonical combo parser in ``data_collection.seed``."""
from __future__ import annotations

import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from data_collection.seed.parse_combos import main


if __name__ == "__main__":
    raise SystemExit(main())
