"""Small, comparable recommender prototypes for offline architecture evaluation.

All recommenders share one interface and one eligibility rule. They rank catalog
search units that the catalog marks recommendable; availability is measured as a
metric instead of filtered so its value remains informative.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import numpy as np

from src.backend.app.application.ports import UnitIndex

EVENT_WEIGHTS = {"purchase": 5.0, "add_to_cart": 3.0, "product_view": 1.0, "search": 0.1}
_TOKEN_RE = re.compile(r"[\w]+", flags=re.UNICODE)


@dataclass(frozen=True)
class RankedProduct:
    product_id: str
    score: float
    reason: str


class Recommender(Protocol):
    key: str
    label: str
    description: str
    limitation: str

    def fit(self, index: UnitIndex, events: list[dict]) -> "Recommender": ...
    def recommend(self, user_id: str, events: list[dict], k: int = 20, seed: int = 42) -> list[RankedProduct]: ...


def _event_product(event: dict, index: UnitIndex) -> int | None:
    product_id = event.get("productId")
    return index.resolve(str(product_id)) if product_id else None


def _timestamp(event: dict) -> float:
    value = event.get("timestamp")
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return 0.0


def _normalize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    maximum = float(np.max(values)) if values.size else 0.0
    minimum = float(np.min(values)) if values.size else 0.0
    if maximum <= minimum:
        return np.zeros_like(values)
    return (values - minimum) / (maximum - minimum)


def _token_features(index: UnitIndex) -> list[Counter[str]]:
    output = []
    for product in index.units:
        features: Counter[str] = Counter()
        features[f"taxonomy:{product.taxonomy}"] += 2.0
        features[f"destination:{product.destination.casefold()}"] += 1.0
        for key, value in sorted(product.attributes.items()):
            if value is True:
                features[f"attribute:{key}"] += 2.0
            elif value not in (None, False, "") and isinstance(value, (str, int, float)):
                features[f"{key}:{str(value).casefold()}"] += 1.0
        output.append(features)
    return output


class BaseRecommender:
    key = "base"
    label = "Base"
    description = "Shared evaluation interface."
    limitation = "Prototype result; inspect the report conditions."

    def __init__(self):
        self.index: UnitIndex | None = None
        self.events: list[dict] = []

    def fit(self, index: UnitIndex, events: list[dict]) -> "BaseRecommender":
        self.index, self.events = index, list(events)
        self._fit()
        return self

    def _fit(self) -> None:
        pass

    def _score(self, user_id: str, events: list[dict], seed: int) -> tuple[np.ndarray, str]:
        assert self.index is not None
        return np.zeros(len(self.index.units), dtype=np.float64), self.description

    def recommend(self, user_id: str, events: list[dict], k: int = 20, seed: int = 42) -> list[RankedProduct]:
        assert self.index is not None, "Call fit(index, events) before recommend()."
        if k <= 0:
            return []
        scores, reason = self._score(user_id, events, seed)
        eligible = np.asarray(self.index.recommendable, dtype=bool).copy()
        seen = {i for event in events if (i := _event_product(event, self.index)) is not None}
        if seen:
            eligible[list(seen)] = False
        if not eligible.any():
            return []
        candidates = np.flatnonzero(eligible)
        if candidates.size > k:
            candidate_scores = scores[candidates]
            threshold = float(np.partition(candidate_scores, -k)[-k])
            above = candidates[candidate_scores > threshold]
            tied = candidates[candidate_scores == threshold]
            tie_slots = k - above.size
            tied = sorted(tied, key=lambda i: self.index.units[i].product_id)[:tie_slots]
            candidates = np.concatenate((above, np.asarray(tied, dtype=int)))
        top = sorted(candidates.tolist(), key=lambda i: (-float(scores[i]), self.index.units[i].product_id))
        return [RankedProduct(self.index.units[i].product_id, float(scores[i]), reason) for i in top]


class RandomRecommender(BaseRecommender):
    key, label = "random", "Random baseline"
    description = "Deterministic seeded random ordering."
    limitation = "Only a sanity-check baseline; no personalization signal."

    def _score(self, user_id, events, seed):
        assert self.index is not None
        digest = hashlib.sha256(f"{seed}:{user_id}".encode()).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
        return rng.random(len(self.index.units)), self.description


class GlobalPopularityRecommender(BaseRecommender):
    key, label = "global_popularity", "Global popularity"
    description = "Products ordered by purchase count in the training split."
    limitation = "Favors globally popular products and has no personal signal."

    def _fit(self):
        assert self.index is not None
        counts = np.zeros(len(self.index.units), dtype=np.float64)
        for event in self.events:
            if event.get("eventName") == "purchase":
                item = _event_product(event, self.index)
                if item is not None:
                    counts[item] += 1
        if not counts.any():
            counts = np.asarray([float(p.attributes.get("reviewCount") or 0) for p in self.index.units])
        self.popularity = counts

    def _score(self, user_id, events, seed):
        return self.popularity.copy(), self.description


class DestinationSeasonPopularityRecommender(GlobalPopularityRecommender):
    key, label = "destination_season_popularity", "Destination and season popularity"
    description = "Purchase popularity conditioned on the user's recent destination and travel month."
    limitation = "Uses destination/month context inferred from training events; seed history may be synthetic."

    def _fit(self):
        super()._fit()
        assert self.index is not None
        self.by_destination: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(len(self.index.units), dtype=np.float64))
        self.by_destination_month: dict[tuple[str, int], np.ndarray] = defaultdict(lambda: np.zeros(len(self.index.units), dtype=np.float64))
        for event in self.events:
            if event.get("eventName") != "purchase":
                continue
            item = _event_product(event, self.index)
            if item is None:
                continue
            destination = str(self.index.destination[item])
            self.by_destination[destination][item] += 1
            month_value = event.get("usingDate") or event.get("timestamp")
            try:
                month = datetime.fromisoformat(str(month_value).replace("Z", "+00:00")).month
            except (TypeError, ValueError):
                month = 0
            if month:
                self.by_destination_month[(destination, month)][item] += 1

    def _score(self, user_id, events, seed):
        assert self.index is not None
        valid = [(event, _event_product(event, self.index)) for event in events]
        valid = [(event, item) for event, item in valid if item is not None]
        if not valid:
            return self.popularity.copy(), self.description + " (global cold-start fallback)"
        event, item = max(valid, key=lambda pair: _timestamp(pair[0]))
        destination = str(self.index.destination[item])
        month_value = event.get("usingDate") or event.get("timestamp")
        try:
            month = datetime.fromisoformat(str(month_value).replace("Z", "+00:00")).month
        except (TypeError, ValueError):
            month = 0
        conditioned = self.by_destination_month.get((destination, month)) if month else None
        if conditioned is None or not conditioned.any():
            conditioned = self.by_destination.get(destination)
        if conditioned is None or not conditioned.any():
            conditioned = self.popularity
        return conditioned.copy(), self.description


class StructuredContentRecommender(BaseRecommender):
    key, label = "structured_content", "Structured content-based"
    description = "Cosine similarity over taxonomy, destination, and structured product attributes."
    limitation = "Does not use long-form descriptions or learned semantic relationships."

    def _fit(self):
        assert self.index is not None
        self.features = _token_features(self.index)
        document_frequency: Counter[str] = Counter()
        for features in self.features:
            document_frequency.update(features.keys())
        n = max(len(self.features), 1)
        self.idf = {term: math.log(1 + n / (1 + count)) for term, count in document_frequency.items()}
        self.vectors = []
        for features in self.features:
            vector = {term: count * self.idf[term] for term, count in features.items()}
            norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
            self.vectors.append({term: value / norm for term, value in vector.items()})

    def _score(self, user_id, events, seed):
        assert self.index is not None
        profile: Counter[str] = Counter()
        for event in events:
            item = _event_product(event, self.index)
            if item is not None:
                weight = EVENT_WEIGHTS.get(str(event.get("eventName")), 0.2)
                for term, value in self.features[item].items():
                    profile[term] += weight * value
        norm = math.sqrt(sum(value * value for value in profile.values())) or 1.0
        profile = Counter({term: value / norm for term, value in profile.items()})
        scores = np.asarray([sum(value * vector.get(term, 0.0) for term, value in profile.items()) for vector in self.vectors])
        return scores, self.description if profile else self.description + " (cold-start; ties by product ID)"


class EmbeddingContentRecommender(BaseRecommender):
    key, label = "multilingual_embedding", "Multilingual embedding content-based"
    description = "Cosine similarity to a recency-weighted profile built from catalog multilingual embeddings."
    limitation = "Uses the configured catalog embedding model; quality depends on catalog text and synthetic history."

    def _score(self, user_id, events, seed):
        assert self.index is not None
        profile = np.zeros(self.index.E.shape[1], dtype=np.float64)
        now = max((_timestamp(event) for event in events), default=0.0)
        for event in events:
            item = _event_product(event, self.index)
            if item is None:
                continue
            days = max(0.0, (now - _timestamp(event)) / 86400) if now else 0.0
            weight = EVENT_WEIGHTS.get(str(event.get("eventName")), 0.2) * 2 ** (-days / 180)
            profile += weight * self.index.E[item]
        norm = np.linalg.norm(profile)
        if norm:
            profile /= norm
        return self.index.E @ profile, self.description if norm else self.description + " (cold-start)"


class ItemItemCFRecommender(BaseRecommender):
    key, label = "item_item_cf", "Item-item collaborative filtering"
    description = "Ranks items by co-interaction similarity across users in the training split."
    limitation = "Co-occurrence estimates are weak on sparse or synthetic interaction data."

    def _fit(self):
        assert self.index is not None
        histories: dict[str, dict[int, float]] = defaultdict(dict)
        for event in self.events:
            user = event.get("cdpUserId")
            item = _event_product(event, self.index)
            if user and item is not None:
                histories[str(user)][item] = histories[str(user)].get(item, 0.0) + EVENT_WEIGHTS.get(str(event.get("eventName")), 0.2)
        co: dict[int, Counter[int]] = defaultdict(Counter)
        for history in histories.values():
            for left, left_weight in history.items():
                for right, right_weight in history.items():
                    if left != right:
                        co[left][right] += min(left_weight, right_weight)
        self.similar: dict[int, dict[int, float]] = {}
        for source, values in co.items():
            source_norm = math.sqrt(sum(value * value for value in values.values())) or 1.0
            self.similar[source] = {target: value / source_norm for target, value in values.items()}

    def _score(self, user_id, events, seed):
        assert self.index is not None
        scores = np.zeros(len(self.index.units), dtype=np.float64)
        for event in events:
            item = _event_product(event, self.index)
            if item is None:
                continue
            weight = EVENT_WEIGHTS.get(str(event.get("eventName")), 0.2)
            for neighbor, similarity in self.similar.get(item, {}).items():
                scores[neighbor] += weight * similarity
        return scores, self.description if scores.any() else self.description + " (cold-start fallback by product ID)"


class ImplicitALSRecommender(BaseRecommender):
    key, label = "implicit_als", "Implicit-feedback matrix factorization (ALS)"
    description = "NumPy implicit ALS prototype trained on weighted user-item events."
    limitation = "Low-rank factors can overfit small, sparse, generated interaction histories."

    def __init__(self, factors: int = 16, iterations: int = 6, regularization: float = 0.1, alpha: float = 15.0):
        super().__init__()
        self.factors, self.iterations = factors, iterations
        self.regularization, self.alpha = regularization, alpha

    def _fit(self):
        assert self.index is not None
        interactions: dict[str, dict[int, float]] = defaultdict(dict)
        for event in self.events:
            user = event.get("cdpUserId")
            item = _event_product(event, self.index)
            if user and item is not None and event.get("eventName") != "search":
                interactions[str(user)][item] = interactions[str(user)].get(item, 0.0) + EVENT_WEIGHTS.get(str(event.get("eventName")), 0.2)
        users = sorted(interactions)
        self.user_factors: dict[str, np.ndarray] = {}
        self.item_factors = np.zeros((len(self.index.units), self.factors), dtype=np.float64)
        if not users:
            return
        rng = np.random.default_rng(1729)
        self.user_factors = {user: rng.normal(0, 0.05, self.factors) for user in users}
        self.item_factors = np.zeros((len(self.index.units), self.factors), dtype=np.float64)
        item_users: dict[int, list[tuple[str, float]]] = defaultdict(list)
        for user, values in interactions.items():
            for item, value in values.items():
                item_users[item].append((user, value))
        for item in item_users:
            self.item_factors[item] = rng.normal(0, 0.05, self.factors)
        identity = np.eye(self.factors) * self.regularization
        for _ in range(self.iterations):
            Y = self.item_factors
            gram = Y.T @ Y
            for user in users:
                values = interactions[user]
                ids = np.fromiter(values.keys(), dtype=int)
                confidence = np.asarray([1 + self.alpha * values[item] for item in ids])
                rows = Y[ids]
                matrix = gram + rows.T @ ((confidence - 1)[:, None] * rows) + identity
                target = rows.T @ confidence
                self.user_factors[user] = np.linalg.solve(matrix, target)
            X = np.asarray([self.user_factors[user] for user in users])
            gram_users = X.T @ X
            for item, user_values in item_users.items():
                rows = np.asarray([self.user_factors[user] for user, _ in user_values])
                confidence = np.asarray([1 + self.alpha * value for _, value in user_values])
                matrix = gram_users + rows.T @ ((confidence - 1)[:, None] * rows) + identity
                target = rows.T @ confidence
                self.item_factors[item] = np.linalg.solve(matrix, target)

    def _score(self, user_id, events, seed):
        assert self.index is not None
        user = self.user_factors.get(user_id)
        if user is None:
            return np.zeros(len(self.index.units), dtype=np.float64), self.description + " (cold-start fallback)"
        return self.item_factors @ user, self.description


class PersonalizedPageRankRecommender(BaseRecommender):
    key, label = "personalized_pagerank", "Personalized PageRank on user-item graph"
    description = "Personalized PageRank over the weighted bipartite user-item interaction graph."
    limitation = "Graph walks can amplify popular hubs; event graph is small and generated."

    def _fit(self):
        assert self.index is not None
        self.graph: dict[tuple[str, str], Counter[tuple[str, str]]] = defaultdict(Counter)
        for event in self.events:
            user = str(event.get("cdpUserId") or "")
            item = _event_product(event, self.index)
            if not user or item is None:
                continue
            user_node, item_node = ("user", user), ("item", str(item))
            weight = EVENT_WEIGHTS.get(str(event.get("eventName")), 0.2)
            self.graph[user_node][item_node] += weight
            self.graph[item_node][user_node] += weight

    def _score(self, user_id, events, seed):
        assert self.index is not None
        start = ("user", user_id)
        if start not in self.graph:
            return np.zeros(len(self.index.units), dtype=np.float64), self.description + " (cold-start fallback)"
        scores: dict[tuple[str, str], float] = {start: 1.0}
        for _ in range(16):
            next_scores: dict[tuple[str, str], float] = defaultdict(float)
            next_scores[start] += 0.15
            for node, mass in scores.items():
                neighbors = self.graph.get(node)
                if not neighbors:
                    next_scores[start] += 0.85 * mass
                    continue
                total = sum(neighbors.values()) or 1.0
                for neighbor, weight in neighbors.items():
                    next_scores[neighbor] += 0.85 * mass * weight / total
            scores = next_scores
        output = np.zeros(len(self.index.units), dtype=np.float64)
        for node, score in scores.items():
            if node[0] == "item":
                output[int(node[1])] = score
        return output, self.description


class MarkovSequenceRecommender(BaseRecommender):
    key, label = "markov_sequence", "Markov next-item sequence"
    description = "Ranks next products from first-order transitions between purchased products."
    limitation = "First-order transitions have little support when each user has few trips."

    def _fit(self):
        assert self.index is not None
        by_user: dict[str, list[tuple[float, int]]] = defaultdict(list)
        self.popularity = np.zeros(len(self.index.units), dtype=np.float64)
        for event in self.events:
            if event.get("eventName") != "purchase":
                continue
            user = str(event.get("cdpUserId") or "")
            item = _event_product(event, self.index)
            if user and item is not None:
                by_user[user].append((_timestamp(event), item))
                self.popularity[item] += 1
        self.transitions: dict[int, Counter[int]] = defaultdict(Counter)
        for sequence in by_user.values():
            sequence.sort(key=lambda pair: (pair[0], pair[1]))
            for (_, previous), (_, following) in zip(sequence, sequence[1:]):
                if previous != following:
                    self.transitions[previous][following] += 1

    def _score(self, user_id, events, seed):
        assert self.index is not None
        purchased = [(event, _event_product(event, self.index)) for event in events if event.get("eventName") == "purchase"]
        purchased = [(event, item) for event, item in purchased if item is not None]
        if not purchased:
            return self.popularity.copy(), self.description + " (cold-start popularity fallback)"
        last_event, last_item = max(purchased, key=lambda pair: (_timestamp(pair[0]), str(pair[0].get("productId"))))
        next_scores = np.zeros(len(self.index.units), dtype=np.float64)
        for item, count in self.transitions.get(last_item, {}).items():
            next_scores[item] = count
        if next_scores.any():
            return next_scores, self.description
        return self.popularity.copy(), self.description + " (unseen transition; popularity fallback)"


class HybridContextualRecommender(BaseRecommender):
    key, label = "hybrid_contextual", "Hybrid contextual"
    description = "Weighted blend of multilingual content, popularity, and purchase transitions."
    limitation = "Hand-set blend weights are demonstrative and are not tuned on real customer outcomes."

    def _fit(self):
        self.content = EmbeddingContentRecommender().fit(self.index, self.events)
        self.popularity = GlobalPopularityRecommender().fit(self.index, self.events)
        self.sequence = MarkovSequenceRecommender().fit(self.index, self.events)
        self.contextual = DestinationSeasonPopularityRecommender().fit(self.index, self.events)

    def _score(self, user_id, events, seed):
        content, _ = self.content._score(user_id, events, seed)
        popular, _ = self.popularity._score(user_id, events, seed)
        sequential, _ = self.sequence._score(user_id, events, seed)
        contextual, _ = self.contextual._score(user_id, events, seed)
        scores = 0.40 * _normalize(content) + 0.20 * _normalize(popular) + 0.20 * _normalize(sequential) + 0.20 * _normalize(contextual)
        return scores, self.description


def build_recommenders(index: UnitIndex, events: list[dict]) -> list[Recommender]:
    """Fit the ten approved prototypes using only the supplied training events."""
    models: list[Recommender] = [
        RandomRecommender(),
        GlobalPopularityRecommender(),
        DestinationSeasonPopularityRecommender(),
        StructuredContentRecommender(),
        EmbeddingContentRecommender(),
        ItemItemCFRecommender(),
        ImplicitALSRecommender(),
        PersonalizedPageRankRecommender(),
        MarkovSequenceRecommender(),
        HybridContextualRecommender(),
    ]
    return [model.fit(index, events) for model in models]
