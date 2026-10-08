from src.backend.app.infrastructure.vectors import postgres_store
from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader


def _reader(fingerprints):
    """Reader giả: mã băm lần lượt theo danh sách, mỗi lần kéo đầy đủ trả một object mới và được đếm."""
    reader = PostgresCatalogReader("postgresql://unused")
    marks = iter(fingerprints)
    reader._fingerprint = lambda: next(marks)
    reader.full_loads = 0

    def load_full():
        reader.full_loads += 1
        return object()

    reader._load_full = load_full
    return reader


def test_unchanged_fingerprint_reuses_catalog_without_pulling_again():
    reader = _reader(["a:1", "a:1"])
    first = reader.load()
    assert reader.load() is first
    assert reader.full_loads == 1


def test_changed_fingerprint_pulls_full_catalog():
    reader = _reader(["a:1", "b:1", "b:1"])
    first = reader.load()
    second = reader.load()
    assert second is not first
    assert reader.load() is second
    assert reader.full_loads == 2


def test_fingerprint_failure_pulls_full_and_does_not_cache():
    reader = _reader([None, "a:1", "a:1"])
    reader.load()
    reader.load()  # lần trước không có mã băm nên không có gì để so: vẫn kéo
    reader.load()
    assert reader.full_loads == 2


def test_failed_full_load_keeps_previous_cache_untouched():
    reader = _reader(["a:1", "b:1", "a:1"])
    first = reader.load()

    def broken():
        raise RuntimeError("db down")

    reader._load_full = broken
    try:
        reader.load()
    except RuntimeError:
        pass
    assert reader.load() is first


def test_fingerprint_errors_are_swallowed(monkeypatch, caplog):
    import psycopg

    def refuse(*args, **kwargs):
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(psycopg, "connect", refuse)
    assert PostgresCatalogReader("postgresql://unused")._fingerprint() is None
    assert "recsys.catalog.fingerprint.failed" in caplog.text


def test_fingerprint_query_hashes_exactly_the_catalog_and_combo_queries():
    query = postgres_store._FINGERPRINT_QUERY
    assert postgres_store._QUERY in query
    assert postgres_store._COMBO_QUERY in query
