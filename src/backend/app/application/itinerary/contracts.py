"""Runtime validation against the authoritative, bundled OpenAPI schemas."""
from copy import deepcopy
from functools import lru_cache
from typing import Any
import json

from jsonschema import Draft202012Validator, FormatChecker
from src.shared.contracts.scripts.bundle_openapi import bundle


@lru_cache(maxsize=None)
def schema(name: str) -> dict[str, Any]:
    document = bundle()
    value = deepcopy(document["components"]["schemas"][name])
    value["components"] = document["components"]
    return value


def valid(name: str, value: Any) -> bool:
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError):
        return False
    return not any(Draft202012Validator(schema(name), format_checker=FormatChecker()).iter_errors(value))


def error_response(code: str, message: str, request_id: str, retryable: bool = False) -> dict:
    return {"error": {"code": code, "message": message,
                      "retryable": retryable, "requestId": request_id}}
