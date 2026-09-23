"""Log bằng structlog (spec §1.5), level qua --verbose. Không log secret: httpx bị hạ xuống WARNING."""
from __future__ import annotations

import logging
import sys
import warnings

import structlog


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    for noisy in ("httpx", "httpcore", "grpc"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # authlib (phụ thuộc của weaviate-client) tự đặt simplefilter("always") cho cảnh báo httpx của nó lúc import —
    # import trước rồi mới chèn filter ignore lên đầu, không thì filter của authlib thắng.
    try:
        import authlib.deprecate  # noqa: F401
    except ImportError:
        pass
    warnings.filterwarnings("ignore", message="The httpx module is deprecated")
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        processors=[structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="%H:%M:%S"),
                    structlog.dev.ConsoleRenderer(colors=False)],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )
