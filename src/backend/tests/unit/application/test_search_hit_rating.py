"""`hit()` (dùng chung /search, /similar, /recommendations) trả `rating`/`reviewCount` như ProductSummary
(contract `ScoredProduct` = ProductSummary + score); thiếu thì card Web rơi về chip hạng sao."""
from src.backend.app.application.search.use_cases import hit


def test_hit_exposes_rating_and_review_count_like_product_summary(services, monkeypatch):
    index = services["index"]
    attrs = index.units[0].attributes
    monkeypatch.setitem(attrs, "reviewScore", 8.2)
    monkeypatch.setitem(attrs, "reviewScoreScale", 10.0)
    monkeypatch.setitem(attrs, "reviewCount", 128)
    row = hit(index, 0, 0.5)
    assert row["rating"] == 4.1 and row["reviewCount"] == 128


def test_hit_rating_is_null_without_review_score(services, monkeypatch):
    index = services["index"]
    attrs = index.units[0].attributes
    for key in ("reviewScore", "reviewScoreScale", "reviewCount"):
        monkeypatch.delitem(attrs, key, raising=False)
    row = hit(index, 0, 0.5)
    assert row["rating"] is None and row["reviewCount"] is None
