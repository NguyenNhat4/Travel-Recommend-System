"""Lỗi nghiệp vụ của catalog. Tầng API dịch `code`, `http_status` và `details` sang Error Envelope."""
from __future__ import annotations


class CatalogError(Exception):
    code = "INTERNAL_ERROR"
    http_status = 500
    retryable = False

    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(message or self.code)
        self.details = details


class InvalidCatalogRequest(CatalogError):
    code, http_status = "VALIDATION_ERROR", 400


class ProductNotFound(CatalogError):
    code, http_status = "PRODUCT_NOT_FOUND", 404


class ProductNotIndexed(CatalogError):
    """Có trong catalog nhưng chưa có vector: cần reindex, khác sai id (search-recommendation §3.6)."""
    code, http_status = "PRODUCT_NOT_INDEXED", 409


class CatalogUnavailable(CatalogError):
    """RecSys (vector index) chưa sẵn sàng."""
    code, http_status, retryable = "SEARCH_UNAVAILABLE", 503, True
