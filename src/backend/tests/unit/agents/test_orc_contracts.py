"""Function schema, provider strict conversion, bounds and local validation."""

import json
from copy import deepcopy

from jsonschema import Draft202012Validator

from src.backend.app.application.itinerary.orc_contracts import (
    CONTROL_TOOLS,
    TOOLS,
    function_tools,
    tool_errors,
)
from src.backend.app.infrastructure.llm.client import strict_parameters


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def test_function_definitions_are_bounded_and_not_free_form():
    definitions = function_tools(list(TOOLS))
    assert len(definitions) == 7
    assert len(json.dumps(definitions)) < 40_000
    for tool in definitions:
        schema = tool["function"]["parameters"]
        Draft202012Validator.check_schema(schema)
        for node in walk(schema):
            if "properties" in node:
                assert node["additionalProperties"] is False
        assert "userId" not in json.dumps(schema)
    assert [t["function"]["name"] for t in function_tools(list(TOOLS), False)] == [
        "respond"
    ]


def test_optional_fields_can_be_omitted_but_unknown_fields_rejected():
    assert (
        tool_errors("find_products", {"why": "Tra dữ liệu.", "taxonomy": "attraction"})
        == []
    )
    assert tool_errors(
        "find_products",
        {"why": "Tra dữ liệu.", "taxonomy": "attraction", "userId": "other"},
    )
    assert tool_errors(
        "find_products", {"why": "Tra dữ liệu.", "taxonomy": "attraction", "limit": 21}
    )
    assert tool_errors("get_products", {"why": "Tra dữ liệu.", "refs": ["p1"] * 11})
    assert tool_errors("update_trip", {"adults": 1})
    assert (
        tool_errors("update_trip", {"evidence": "một mình", "adults": 1, "children": 0})
        == []
    )
    assert tool_errors("respond", {"action": "respond"})


def test_strict_conversion_preserves_original_and_requires_nullable_fields_recursively():
    for schema in [*TOOLS.values(), *CONTROL_TOOLS.values()]:
        original = deepcopy(schema)
        converted = strict_parameters(schema)
        assert original == schema
        for node in walk(converted):
            if "properties" in node:
                assert node["required"] == list(node["properties"])
                assert node["additionalProperties"] is False
    query = strict_parameters(TOOLS["find_products"])["properties"]["query"]
    assert "null" in query["type"]


def test_schedule_three_slots_and_no_manual_room_dates():
    schema = TOOLS["plan_itinerary"]
    day = schema["properties"]["schedule"]["items"]
    assert set(day["properties"]) == {"day", "morning", "afternoon", "evening"}
    assert schema["properties"]["stays"]["items"]["properties"]["rooms"]["maximum"] == 9
    assert "check_out" not in schema["properties"]["stays"]["items"]["properties"]
