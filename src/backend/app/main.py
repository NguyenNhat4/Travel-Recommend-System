"""Composition root — nơi duy nhất nối infrastructure vào use case (ARCHITECTURE.md §5)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routes import recommendations, search
from app.application.recommendation import BuildPopularity, RecommendForUser
from app.application.search import SearchProducts, SimilarProducts
from app.core.settings import settings
from app.infrastructure.cdp.local_cdp_client import LocalCdpClient
from app.infrastructure.embeddings.sentence_transformers_embedder import SentenceTransformersEmbedder
from app.infrastructure.vectors.in_memory_store import InMemoryVectorStore


def build_services(embedder=None, cdp=None):
    embedder = embedder or SentenceTransformersEmbedder(settings.embed_model)
    index = InMemoryVectorStore(settings.products_path, embedder, settings.embed_cache_dir).load()
    cdp = cdp or LocalCdpClient(settings.events_path)
    popularity = BuildPopularity(index, cdp)()
    return {
        "index": index,
        "search": SearchProducts(index, embedder, cutoff=settings.search_cutoff, max_limit=settings.search_max_limit),
        "similar": SimilarProducts(index),
        "recommend": RecommendForUser(index, cdp, popularity, candidate_k=settings.recommend_candidate_k),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    for k, v in build_services().items():
        setattr(app.state, k, v)
    yield


app = FastAPI(title="V-OTA backend", lifespan=lifespan)
app.include_router(search.router)
app.include_router(recommendations.router)
