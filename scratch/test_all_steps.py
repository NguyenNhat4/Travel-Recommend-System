import sys
sys.stdout.reconfigure(encoding="utf-8")
import types
import importlib.machinery
import os
import time
import pickle
import numpy as np

if 'sklearn' not in sys.modules:
    _m_sk = types.ModuleType('sklearn')
    _m_sk.__spec__ = importlib.machinery.ModuleSpec('sklearn', None)
    sys.modules['sklearn'] = _m_sk
if 'sklearn.metrics' not in sys.modules:
    _m_met = types.ModuleType('sklearn.metrics')
    _m_met.__spec__ = importlib.machinery.ModuleSpec('sklearn.metrics', None)
    _m_met.roc_curve = lambda *args, **kwargs: (None, None, None)
    sys.modules['sklearn.metrics'] = _m_met

REPO_ROOT = os.path.abspath(".")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.backend.app.core.config import get_settings
from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
from src.backend.app.domain.search import (
    QueryNormalizer, build_query_plan, PlanParams, PlanFlags, HybridConfig,
    is_unaccented, tokens, query_tokens, coverage, revalidate, soft_star_order,
    hybrid_filter_score, candidate_filter_score
)
from src.backend.app.domain.search.fuzzy import FuzzyIndex
from src.backend.app.domain.search.tone import detect_style, normalize_tone
from src.backend.app.application.search.use_cases import (
    canonical_query, _plan_gazetteers, _child_filter, PROFILE_NO_DIACRITICS
)

settings = get_settings()
print("1. Loading catalog units...")
with open(r".embcache\debug_catalog_units.pkl", "rb") as f:
    cat = pickle.load(f)
index = cat.to_index(f"{settings.embed_model}:{TEXT_BUILDER_VERSION}")

q = "resort Nha Trang cho gia đình có hồ bơi"

print("2. Testing Step 1: Normalization...")
normalizer = QueryNormalizer(
    destinations=set(index.destination.tolist()),
    names=(p.name for p in index.units),
    tone=False,
)
nq = normalizer(q)
canonical_text = canonical_query(nq.text if nq else q)
unacc = is_unaccented(nq.text if nq else q)
t_style = detect_style([q]) or "N/A"
print("Step 1 OK:", canonical_text, unacc, t_style)

print("3. Testing Step 2: Query Plan...")
gazetteers = _plan_gazetteers(index.units)
plan_flags = PlanFlags()
plan_params = PlanParams()
plan = build_query_plan(nq, q, plan_params, plan_flags, gazetteers)
decision = plan.destination
plan_diag = plan.as_diagnostics(extended=True)
plan_dict = {
    "confidence": plan.confidence,
    "fallback_reasons": list(plan.fallback_reasons),
    "destination_decision": {
        "value": decision.value,
        "source": decision.source,
        "skipped": decision.skipped,
        "candidates": list(decision.candidates),
    },
    "taxonomy": plan.taxonomy,
    "taxonomy_strength": plan.taxonomy_strength,
    "must_not_taxonomies": list(plan.must_not_taxonomies),
    "must_not_flags": list(plan.must_not_flags),
    "price_range": f"{plan.price_min} -> {plan.price_max}" if plan.price_source else None,
    "star_min": plan.star_min,
    "party_total": plan.party_total if plan.party_source else None,
    "lexical_text_for_bm25": plan.lexical_text,
    "diagnostics": plan_diag,
}
print("Step 2 OK:", plan_dict["taxonomy"], plan_dict["destination_decision"])

print("4. Testing Step 3: Filter First Mask...")
mask_kwargs = plan.mask_kwargs(destination=decision.value)
mask = index.mask(**mask_kwargs)
allowed = index.allowed_ids(mask)
f_count = int(mask.sum())
print(f"Step 3 OK: |F| = {f_count}")

print("5. Testing Step 4 & 5 Mock Scoring & Fusion...")
# Test with dummy dense hits and lex hits to test the scoring and gate logic
from src.backend.app.application.ports import VectorHit, LexicalHit
dummy_dense = [VectorHit(product_id=allowed[i], score=0.9 - i*0.01) for i in range(min(10, len(allowed)))]
dummy_lex = [LexicalHit(product_id=allowed[i], score=15.0 - i) for i in range(min(5, len(allowed)))]

cosines = {index.idx[h.product_id]: float(h.score) for h in dummy_dense}
dense_rank = {index.idx[h.product_id]: r for r, h in enumerate(dummy_dense, 1)}
lexical_rank = {index.idx[h.product_id]: r for r, h in enumerate(dummy_lex, 1)}

fusion_cfg = dict(
    fuzzy_k=0,
    fuzzy_candidate_k=200,
    fuzzy_min_sim=0.6,
    dense_weight=1.0,
    lexical_weight=1.0,
    fuzzy_weight=1.0,
)
hybrid_config = HybridConfig(
    rrf_k=30,
    lexical_k=50,
    lexical_cutoff=0.5,
    min_coverage=0.1,
    **fusion_cfg,
)
facet_fields = {"taxonomy": index.taxonomy, "destination": index.destination}
name_tokens = [set(tokens(p.name)) for p in index.units]
q_tokens = query_tokens(canonical_query(plan.lexical_text))

outcome = hybrid_filter_score(
    cosines,
    dense_rank,
    lexical_rank,
    lambda u: coverage(q_tokens, name_tokens[u]) >= hybrid_config.min_coverage,
    0.84,
    hybrid_config,
    f_count,
    facet_fields,
)

order, drops = revalidate(outcome.order, mask)
child_filter = _child_filter(plan)
if plan.price_active and plan.party_active:
    children_attrs = index.attrs.children
    kept = [u for u in order if not children_attrs[u] or index.matched_children(u, limit=1, **child_filter)]
    drops += (len(order) - len(kept))
    order = kept

if plan.star_active:
    order = soft_star_order(order, index.star_known_ok(plan.star_min))

outcome.order = order
print("Step 5 OK! Top 1 index:", order[0] if order else None, "Total:", outcome.total)
print("ALL 5 STEPS VALIDATED CLEANLY!")
