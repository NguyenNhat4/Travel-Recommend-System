"""Read tool schemas directly from the checked-in OpenAPI entrypoint."""
from copy import deepcopy
from functools import lru_cache
from typing import Any
import json

from jsonschema import Draft202012Validator, FormatChecker
from src.shared.contracts.scripts.bundle_openapi import bundle
from src.backend.app.application.ports.itinerary_tools import ToolError

OPERATIONS = {
    "search_products": ("/search", "get"),
    "get_recommendations": ("/recommendations", "get"),
}


@lru_cache(maxsize=1)
def contracts() -> dict[str, dict[str, Any]]:
    document = bundle()

    def resolve(value):
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            target = document
            for part in value["$ref"][2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
            return resolve(target)
        return {key: resolve(item) for key, item in value.items()}

    result = {}
    for name, (path, method) in OPERATIONS.items():
        operation = resolve(document["paths"][path][method])
        if name == "search_products":
            # Planner giữ schema giàu của SearchRequest. HTTP compatibility adapter sẽ
            # đổi `query` thành `q` và Agent hậu kiểm các filter mà GET legacy chưa hỗ trợ.
            arguments = resolve(document["components"]["schemas"]["SearchRequest"])
        elif method == "post":
            arguments = operation["requestBody"]["content"]["application/json"]["schema"]
        else:
            parameters = [p for p in operation["parameters"] if p["in"] == "query"]
            arguments = {"type": "object", "additionalProperties": False,
                         "properties": {p["name"]: p["schema"] for p in parameters},
                         "required": [p["name"] for p in parameters if p.get("required")]}
        result[name] = {"arguments": arguments,
                        "response": operation["responses"]["200"]["content"]["application/json"]["schema"],
                        "description": operation["summary"]}
    return result


def definitions() -> list[dict[str, Any]]:
    return [{"name": name, "description": contract["description"],
             "parameters": deepcopy(contract["arguments"])} for name, contract in contracts().items()]


def validate(name: str, value: Any, kind: str) -> None:
    if name not in contracts():
        raise ToolError("TOOL_NOT_ALLOWED")
    schema = contracts()[name][kind]
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ToolError("INVALID_ARGUMENTS" if kind == "arguments" else "INVALID_TOOL_RESPONSE") from exc
    if next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), None):
        # Do not echo untrusted values, tokens or upstream messages into checkpoints.
        raise ToolError("INVALID_ARGUMENTS" if kind == "arguments" else "INVALID_TOOL_RESPONSE")
    if kind == "response" and name == "get_recommendations" and value["strategy"] == "popular":
        if any(item["because"] for item in value["recommendations"]):
            raise ToolError("INVALID_TOOL_RESPONSE")


def argument_names(name: str) -> frozenset[str]:
    """Tên tham số hợp đồng khai báo cho tool; rỗng khi tool không có trong hợp đồng."""
    contract = contracts().get(name)
    return frozenset(contract["arguments"].get("properties", {})) if contract else frozenset()


def normalize_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    validate(name, arguments, "arguments")
    result = {key: deepcopy(value) for key, value in arguments.items() if value is not None}
    for key, schema in contracts()[name]["arguments"]["properties"].items():
        candidates = [schema, *schema.get("oneOf", [])]
        for candidate in candidates:
            if key not in result and "default" in candidate:
                result[key] = deepcopy(candidate["default"])
    if name == "search_products" and "priceMin" in result and "priceMax" in result:
        if result["priceMin"] > result["priceMax"]:
            raise ToolError("INVALID_ARGUMENTS")
    return result


@lru_cache(maxsize=1)
def error_schema() -> dict[str, Any]:
    document = bundle()
    schema = deepcopy(document["components"]["schemas"]["ErrorResponse"])
    schema["components"] = document["components"]
    return schema


def upstream_error_code(value: Any) -> str | None:
    if next(Draft202012Validator(error_schema()).iter_errors(value), None):
        return None
    return value["error"]["code"]
