import numpy as np

from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.catalog import Product
from src.evaluation.recommender_prototypes import build_recommenders


def make_index():
    units = [
        Product("a", "Resort biển gia đình", "hotel", "Nha Trang", "bãi biển hồ bơi", {"familyFriendly": True}),
        Product("b", "Vé công viên nước", "attraction", "Nha Trang", "trò chơi nước gia đình", {"waterPark": True}),
        Product("c", "Vé tham quan phố cổ", "attraction", "Hội An", "văn hóa phố cổ", {"outdoor": True}),
        Product("d", "Chuyến bay Đà Nẵng", "flight", "Đà Nẵng", "đường bay nội địa", {"directFlight": True}),
        Product("e", "Golf Nha Trang", "golf", "Nha Trang", "sân golf biển", {"outdoor": True}),
    ]
    vectors = np.asarray(
        [[1, 0, 0], [0.9, 0.1, 0], [0, 0, 1], [0, 1, 0], [0.8, 0.2, 0]], dtype=np.float32
    )
    return UnitIndex(
        units=units,
        E=vectors,
        taxonomy=np.array([p.taxonomy for p in units]),
        destination=np.array([p.destination for p in units]),
        available=np.ones(len(units), dtype=bool),
        recommendable=np.array([True, True, True, True, False]),
        parent_of={},
        model_version="test",
    )


def test_registry_contains_the_ten_approved_prototypes():
    recommenders = build_recommenders(make_index(), [])

    assert [model.key for model in recommenders] == [
        "random",
        "global_popularity",
        "destination_season_popularity",
        "structured_content",
        "multilingual_embedding",
        "item_item_cf",
        "implicit_als",
        "personalized_pagerank",
        "markov_sequence",
        "hybrid_contextual",
    ]


def test_all_models_are_deterministic_on_cold_start_and_only_recommend_recommendable_units():
    index = make_index()
    recommenders = build_recommenders(index, [])

    for model in recommenders:
        first = model.recommend("new-user", [], k=5, seed=7)
        second = model.recommend("new-user", [], k=5, seed=7)
        assert [item.product_id for item in first] == [item.product_id for item in second]
        assert first
        assert all(index.recommendable[index.idx[item.product_id]] for item in first)


def test_model_returns_no_seen_recommendations_when_user_consumed_catalog():
    index = make_index()
    events = [
        {"cdpUserId": "u1", "eventName": "product_view", "productId": product.product_id}
        for product in index.units if index.recommendable[index.idx[product.product_id]]
    ]
    model = build_recommenders(index, events)[0]

    assert model.recommend("u1", events, k=5) == []


def test_all_models_are_deterministic_with_trained_history():
    index = make_index()
    events = [
        {"cdpUserId": "u1", "eventName": "product_view", "productId": "a", "timestamp": "2026-01-01T00:00:00Z"},
        {"cdpUserId": "u1", "eventName": "purchase", "productId": "b", "timestamp": "2026-01-02T00:00:00Z"},
        {"cdpUserId": "u2", "eventName": "purchase", "productId": "a", "timestamp": "2026-01-02T00:00:00Z"},
        {"cdpUserId": "u2", "eventName": "product_view", "productId": "c", "timestamp": "2026-01-03T00:00:00Z"},
    ]

    for model in build_recommenders(index, events):
        first = model.recommend("u1", events, k=3, seed=19)
        second = model.recommend("u1", events, k=3, seed=19)
        assert [(item.product_id, item.score) for item in first] == [(item.product_id, item.score) for item in second]


def test_personalized_content_methods_use_user_history_and_hide_seen_items():
    index = make_index()
    events = [
        {"cdpUserId": "u1", "eventName": "purchase", "productId": "a", "timestamp": "2026-01-01T00:00:00Z"},
    ]
    recommenders = {model.key: model for model in build_recommenders(index, events)}

    for key in ("structured_content", "multilingual_embedding", "item_item_cf", "implicit_als", "personalized_pagerank", "markov_sequence", "hybrid_contextual"):
        result = recommenders[key].recommend("u1", events, k=5, seed=7)
        assert result
        assert all(item.product_id != "a" for item in result)
