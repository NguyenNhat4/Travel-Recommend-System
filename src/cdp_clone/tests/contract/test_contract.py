"""Responses from the running app must match src/shared/contracts/cdp-clone.openapi.yaml."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

CONTRACTS = Path(__file__).resolve().parents[3] / "shared/contracts"
sys.path.insert(0, str(CONTRACTS / "scripts"))
from bundle_openapi import bundle  # noqa: E402

DOC = bundle(CONTRACTS / "cdp-clone.openapi.yaml")
EVENTS = "/cdp/v1/events"
USER_EVENTS = "/cdp/v1/users/{cdpUserId}/events"
CANCEL = "/cdp/v1/users/{cdpUserId}/events/{eventId}/cancellation"
PROFILE = "/cdp/v1/profiles/{cdpUserId}"


def assert_matches(response, path, method):
    operation = DOC["paths"][path][method]
    spec = operation["responses"].get(str(response.status_code))
    assert spec is not None, f"{method.upper()} {path} does not declare {response.status_code}"
    if "$ref" in spec:
        spec = DOC["components"]["responses"][spec["$ref"].split("/")[-1]]
    schema = dict(spec["content"]["application/json"]["schema"], components=DOC["components"])
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(response.json())


@pytest.fixture
def seeded(client):
    client.post(EVENTS, json={"events": [
        {"cdpUserId": "VP1", "eventName": "purchase", "eventId": "purchase:bi-1", "productId": "p1",
         "taxonomy": "hotel", "eventGroupId": "OFF1", "quantity": 1, "unitPrice": 3400000.5,
         "usingDate": "2026-10-02"},
        {"cdpUserId": "VP1", "eventName": "search", "searchQuery": "Nha Trang"},
    ]})
    client.put("/cdp/v1/profiles/VP1", json={"purchasedVerticals": ["hotel"]})
    return client


def test_success_responses_match_contract(seeded):
    body = {"events": [{"cdpUserId": "VP1", "eventName": "product_view", "productId": "p1", "taxonomy": "hotel"}]}
    assert_matches(seeded.post(EVENTS, json=body), EVENTS, "post")
    assert_matches(seeded.get("/cdp/v1/users/VP1/events"), USER_EVENTS, "get")
    assert_matches(seeded.put("/cdp/v1/users/VP1/events/purchase:bi-1/cancellation"), CANCEL, "put")
    assert_matches(seeded.get("/cdp/v1/users/VP1/events?includeCancelled=true"), USER_EVENTS, "get")
    assert_matches(seeded.get("/cdp/v1/profiles/VP1"), PROFILE, "get")
    assert_matches(seeded.put("/cdp/v1/profiles/VP1", json={}), PROFILE, "put")


def test_error_responses_match_contract(client):
    anonymous = TestClient(client.app, raise_server_exceptions=False)
    cases = [
        (client.post(EVENTS, json={"events": []}), EVENTS, "post"),
        (anonymous.post(EVENTS, json={"events": []}), EVENTS, "post"),
        (anonymous.get("/cdp/v1/users/VP1/events"), USER_EVENTS, "get"),
        (client.get("/cdp/v1/users/VP1/events?limit=0"), USER_EVENTS, "get"),
        (client.put("/cdp/v1/users/VP1/events/none/cancellation"), CANCEL, "put"),
        (client.get("/cdp/v1/profiles/VP404"), PROFILE, "get"),
        (client.put("/cdp/v1/profiles/VP1", json={"lifecycleStage": "sleeping"}), PROFILE, "put"),
    ]
    for response, path, method in cases:
        assert response.status_code >= 400
        assert_matches(response, path, method)
