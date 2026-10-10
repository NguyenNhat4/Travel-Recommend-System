import sys
sys.stdout.reconfigure(encoding="utf-8")
import types
import importlib.machinery
import os
import time
import pickle

REPO_ROOT = os.path.abspath(".")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

if 'sklearn' not in sys.modules:
    _m_sk = types.ModuleType('sklearn')
    _m_sk.__spec__ = importlib.machinery.ModuleSpec('sklearn', None)
    sys.modules['sklearn'] = _m_sk
if 'sklearn.metrics' not in sys.modules:
    _m_met = types.ModuleType('sklearn.metrics')
    _m_met.__spec__ = importlib.machinery.ModuleSpec('sklearn.metrics', None)
    _m_met.roc_curve = lambda *args, **kwargs: (None, None, None)
    sys.modules['sklearn.metrics'] = _m_met

from src.backend.app.core.config import get_settings
from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
from src.backend.app.domain.search import (
    QueryNormalizer, build_query_plan, PlanParams, PlanFlags, HybridConfig,
    tokens, query_tokens, coverage, revalidate, hybrid_filter_score
)
from src.backend.app.application.search.use_cases import _plan_gazetteers, canonical_query
from src.backend.app.infrastructure.embeddings.factory import build_embedder
from src.backend.app.infrastructure.vectors.weaviate_store import connect_weaviate, WeaviateVectorSearch

settings = get_settings()
print('Loading catalog cache...', flush=True)
with open(r'.embcache\debug_catalog_units.pkl', 'rb') as f:
    catalog = pickle.load(f)
index = catalog.to_index(f'{settings.embed_model}:{TEXT_BUILDER_VERSION}')
print(f'Index ready with {len(index.units)} units!', flush=True)

print('Connecting Weaviate...', flush=True)
client = connect_weaviate(settings.weaviate_url, api_key=settings.weaviate_api_key, grpc_port=settings.weaviate_grpc_port)
vs = WeaviateVectorSearch(client, collection=settings.vector_collection, dimension=settings.embed_dimension)

print('Loading embedder...', flush=True)
embedder = build_embedder(settings)

q = 'resort Nha Trang cho gia đình'
print(f'Testing query: {q}', flush=True)
normalizer = QueryNormalizer(destinations=set(index.destination.tolist()), names=(p.name for p in index.units))
nq = normalizer(q)
gazetteers = _plan_gazetteers(index.units)
plan = build_query_plan(nq, q, PlanParams(), PlanFlags(), gazetteers)
print(f'Query Plan diagnostics: {plan.as_diagnostics()}', flush=True)

mask = index.mask(**plan.mask_kwargs(destination=plan.destination.value))
allowed = index.allowed_ids(mask)
print(f'Universe F count: {len(allowed)}', flush=True)

qvec = embedder.embed_query(canonical_query(nq.text))
dense_hits = [h for h in vs.near_vector(qvec, allowed, 50) if h.product_id in index.idx]
print(f'Dense hits count: {len(dense_hits)}', flush=True)
if dense_hits:
    print(f'Dense Top 1: {dense_hits[0].product_id} score={dense_hits[0].score:.4f} name={index.units[index.idx[dense_hits[0].product_id]].name}', flush=True)
    print(f'Dense Bottom: {dense_hits[-1].product_id} score={dense_hits[-1].score:.4f} name={index.units[index.idx[dense_hits[-1].product_id]].name}', flush=True)

lex_hits = [h for h in vs.bm25(canonical_query(plan.lexical_text), allowed, 20, with_vectors=True) if h.product_id in index.idx]
print(f'BM25 hits count: {len(lex_hits)}', flush=True)
if lex_hits:
    print(f'BM25 Top 1: {lex_hits[0].product_id} score={lex_hits[0].score:.4f} name={index.units[index.idx[lex_hits[0].product_id]].name}', flush=True)
    print(f'BM25 Bottom: {lex_hits[-1].product_id} score={lex_hits[-1].score:.4f} name={index.units[index.idx[lex_hits[-1].product_id]].name}', flush=True)

print('ALL PIPELINE STAGES RAN SUCCESSFULLY!', flush=True)
client.close()
