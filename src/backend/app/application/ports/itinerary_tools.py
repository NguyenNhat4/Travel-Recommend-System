"""Read-only ports consumed by the itinerary agent.

`request`/response payloads below mirror `SearchRequest`/`SearchResponse`,
`RecommendationResponse`, `ProductDetail` and `DestinationListResponse` in
`src/shared/contracts/schemas/*.yaml` — the contract, not this file, is the source of truth for
their shape (AGENTS.md §2), so they stay `dict[str, Any]` here rather than a second, hand-kept copy.
`ToolCall`/`ToolResult`/`ToolDefinition` are internal-only (never serialized against the public API)
and are typed accordingly.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.backend.app.domain.itinerary.types import ToolCall, ToolDefinition, ToolErrorPayload, ToolResult


class SearchProductsPort(Protocol):
    async def search_products(self, request: dict[str, Any]) -> dict[str, Any]: ...


class RecommendationPort(Protocol):
    async def get_recommendations(
        self, request: dict[str, Any], authorization: str | None = None
    ) -> dict[str, Any]: ...


class SimilarProductsPort(Protocol):
    """Sản phẩm cùng taxonomy gần nhất với một sản phẩm đã đề xuất (GET /products/{productId}/similar)."""
    async def get_similar_products(self, product_id: str, limit: int) -> dict[str, Any]: ...


class CatalogPort(Protocol):
    async def get_product_detail(self, product_id: str) -> dict[str, Any]: ...
    async def list_destinations(self) -> dict[str, Any]: ...


class ToolError(Exception):
    """Safe internal error: never includes response bodies or credentials."""
    def __init__(self, code: str, *, retryable: bool = False, http_status: int | None = None,
                 reason: str | None = None):
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.http_status = http_status
        self.reason = reason  # từ cố định do backend đặt (vd. `embed:quota_exhausted`), không chứa text upstream

    def as_dict(self) -> ToolErrorPayload:
        payload: ToolErrorPayload = {"code": self.code, "retryable": self.retryable, "httpStatus": self.http_status}
        if self.reason:
            payload["reason"] = self.reason
        return payload


class ToolExecutorPort(Protocol):
    supports_catalog: bool
    def definitions(self) -> list[ToolDefinition]: ...
    async def execute(self, call: ToolCall) -> ToolResult: ...
    async def get_product_detail(self, product_id: str) -> dict[str, Any]: ...
    async def list_destinations(self) -> dict[str, Any]: ...


class ConversationStorePort(Protocol):
    """`value` is a serialized `agents.state.AgentState` checkpoint; `application` cannot depend on
    `agents` (docs/prd/architecture.md §2 quy tắc 1, 5), so it stays untyped here."""

    async def load(self, conversation_id: str | None, owner: str = "anonymous") -> dict[str, Any] | None: ...
    async def save(self, conversation_id: str, value: dict[str, Any], owner: str = "anonymous") -> None: ...
