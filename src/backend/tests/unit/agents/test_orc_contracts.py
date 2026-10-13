"""Schema quyết định của orc (assistant v2): đúng dạng OpenAI strict nhận, bounds khớp API nguồn, lỗi chỉ đúng chỗ."""
import json

from jsonschema import Draft202012Validator

from src.backend.app.application.itinerary.orc_contracts import (CONTEXT_PATCH, TOOLS, decision_errors,
                                                                  decision_schema)
from src.backend.tests.fakes.orc_tools import arguments, call, execute, respond
from src.shared.contracts.scripts.bundle_openapi import bundle


def _walk(node, visit):
    if isinstance(node, dict):
        visit(node)
        for child in node.values():
            _walk(child, visit)
    elif isinstance(node, list):
        for child in node:
            _walk(child, visit)


def test_schema_is_strict_mode_compatible_and_small():
    schema = decision_schema(list(TOOLS))
    Draft202012Validator.check_schema(schema)

    def visit(node):
        # OpenAI strict mode từ chối uniqueItems (lỗi 400 đo được 2026-10-13) và không nhận field tuỳ chọn.
        assert not {"uniqueItems", "default", "oneOf", "examples"} & set(node)
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert node["required"] == list(node["properties"])
            assert node.get("description")

    _walk(schema, visit)
    # Schema đi kèm mọi lần gọi model; bản cũ 193 KB.
    assert len(json.dumps(schema, ensure_ascii=False)) < 30_000
    assert "userId" not in json.dumps(schema)


def test_respond_only_schema_has_no_execute_branch():
    schema = decision_schema(list(TOOLS), can_execute=False)
    assert decision_errors({"decision": execute(call("list_destinations"))}, schema)
    assert decision_errors({"decision": respond()}, schema) == []


def test_bounds_match_source_api_contract():
    api = bundle()

    def resolve(node):
        while "$ref" in node:
            target = api
            for part in node["$ref"][2:].split("/"):
                target = target[part]
            node = target
        return node

    def param(path, name):
        rows = [resolve(row) for row in api["paths"][path]["get"]["parameters"]]
        return resolve(next(row for row in rows if row["name"] == name)["schema"])

    assert TOOLS["get_recommendations"]["properties"]["k"]["maximum"] == param("/recommendations", "k")["maximum"]
    assert TOOLS["get_similar_products"]["properties"]["limit"]["maximum"] == \
        param("/products/{productId}/similar", "limit")["maximum"]
    assert TOOLS["list_products"]["properties"]["limit"]["maximum"] == param("/products", "limit")["maximum"]
    assert TOOLS["list_products"]["properties"]["sort"]["enum"][:-1] == param("/products", "sort")["enum"]
    search = resolve(api["components"]["schemas"]["SearchRequest"])["properties"]
    assert TOOLS["search_products"]["properties"]["limit"]["maximum"] == resolve(search["limit"])["maximum"]


def test_errors_point_at_the_wrong_argument_of_the_intended_tool():
    schema = decision_schema(list(TOOLS))
    bad = execute(call("search_products", query="khách sạn Huế", limit=99))
    assert decision_errors({"decision": bad}, schema) == [
        "decision/calls/0/arguments/limit: 99 is greater than the maximum of 50"]
    unknown = execute({"name": "drop_database", "arguments": {}})
    assert decision_errors({"decision": unknown}, schema)


def test_unadvertised_tool_and_extra_argument_are_rejected():
    schema = decision_schema(["search_products"])
    assert decision_errors({"decision": execute(call("list_destinations"))}, schema)
    extra = execute({"name": "search_products",
                     "arguments": {**arguments("search_products", query="x"), "userId": "another"}})
    assert decision_errors({"decision": extra}, schema)


def test_context_patch_needs_evidence_and_typed_values():
    schema = decision_schema(list(TOOLS))
    patch = {key: None for key in CONTEXT_PATCH["properties"]}
    good = respond(context_patch={**patch, "free_only": True, "evidence": "chỉ chỗ miễn phí"})
    assert decision_errors({"decision": good}, schema) == []
    assert decision_errors({"decision": respond(context_patch={**patch, "free_only": "true", "evidence": "x"})},
                           schema)
    assert decision_errors({"decision": respond(context_patch={**patch, "free_only": True, "evidence": ""})},
                           schema)
