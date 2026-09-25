"""Mọi response của endpoint assistant phải khớp OpenAPI, kiểm ở biên HTTP thật.

Khác với test runtime (kiểm state của graph), test này đi qua FastAPI và kiểm hai điều cho
từng đường ra:

1. Body hợp lệ với schema mà contract gán cho status đó (`ItineraryResponse` cho 200,
   `ErrorResponse` cho phần còn lại).
2. HTTP status **được khai báo** trong `paths/itinerary-agent.yaml`. Một mã lỗi đúng schema
   nhưng chưa khai báo vẫn là contract drift: client sinh từ OpenAPI sẽ không xử lý nó.

Graph tự validate response ở `finalize_node`, nhưng các lỗi phát sinh tại route (request sai
schema, tool chưa cấu hình, timeout, exception) **không đi qua** node đó. Chính những nhánh ấy
là lý do test này tồn tại.
"""
from __future__ import annotations

import json
import os
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from src.backend.app.agents.models import ConversationalAnswer, DestinationChoice, Extraction
from src.backend.app.application.itinerary.contracts import schema
from src.backend.app.core.config import get_settings
from src.backend.app.main import app
from src.shared.contracts.scripts.bundle_openapi import bundle

DOC = bundle()
ITINERARIES = "/assistant/itineraries"
STREAM = "/assistant/itineraries/stream"

PRODUCT = {
    "productId": "a", "name": "Catalog a", "taxonomy": "attraction", "destination": "Nha Trang",
    "description": "Điểm tham quan cho gia đình.", "attributes": {}, "unitPrice": 100000,
    "currency": "VND", "priceUnit": "PER_PERSON", "available": True,
    "availableFrom": None, "availableTo": None, "imageUrl": None,
}


def extraction(**patch) -> Extraction:
    return Extraction(domain="travel", patch=patch)


class ScriptedLlm:
    """Kịch bản hoá quyết định của model; raise nếu luồng gọi model bằng schema ngoài dự kiến."""

    def __init__(self, result=None, fail=False):
        self.result = result or extraction(destination="Nha Trang", days=2,
                                           party={"type": "SOLO", "adults": 1, "children": 0})
        self.fail = fail

    def with_structured_output(self, target):
        async def invoke(_prompt):
            if self.fail:
                raise RuntimeError("provider error")
            if target is Extraction:
                return self.result
            if target is DestinationChoice:
                return DestinationChoice(destination=None)
            if target is ConversationalAnswer:
                return ConversationalAnswer(message="Bạn muốn đi đâu và mấy ngày?")
            raise AssertionError(f"luồng lịch trình không được gọi model cho {target.__name__}")
        return SimpleNamespace(ainvoke=invoke)

    def bind_tools(self, _definitions):
        async def invoke(_prompt):
            return SimpleNamespace(tool_calls=[{"name": "search_products", "args": {"query": "tham quan"}}])
        return SimpleNamespace(ainvoke=invoke)


class Clients:
    # Giống FixtureItineraryClients: có list_destinations nên composition root nối làm catalog.
    supports_catalog = True

    def __init__(self, products=None, destinations=None, fail=False):
        self.products = [deepcopy(PRODUCT)] if products is None else products
        self.destinations = destinations or ["Nha Trang"]
        self.fail = fail

    async def search_products(self, _args):
        if self.fail:
            raise RuntimeError("upstream down")
        return {"results": [{**p, "score": 0.9} for p in self.products], "total": len(self.products)}

    async def get_recommendations(self, _args, authorization=None):
        return {"strategy": "popular", "recommendations": []}

    async def get_product_detail(self, product_id):
        return deepcopy(next(p for p in self.products if p["productId"] == product_id))

    async def list_destinations(self):
        return {"destinations": [{"destination": name, "productCount": len(self.products)}
                                 for name in self.destinations]}


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(schema(name), format_checker=FormatChecker())


class AssistantContractTests(unittest.TestCase):
    def assert_conforms(self, path: str, status: int, body: dict, label: str) -> None:
        declared = DOC["paths"][path]["post"]["responses"]
        self.assertIn(str(status), declared,
                      f"{label}: HTTP {status} chưa khai báo trong paths{path}")
        name = "ItineraryResponse" if status == 200 else "ErrorResponse"
        errors = [f"{list(e.absolute_path)}: {e.message}" for e in validator(name).iter_errors(body)]
        self.assertEqual(errors, [], f"{label}: body không khớp {name}")

    def post(self, payload: dict, *, llm=..., clients=..., path: str = ITINERARIES):
        with TestClient(app) as client:
            app.state.itinerary_llm = ScriptedLlm() if llm is ... else llm
            app.state.itinerary_http_clients = Clients() if clients is ... else clients
            return client.post(f"/api/v1{path}", json=payload)

    # ---------------------------------------------------------------- 200

    def test_every_itinerary_status_matches_the_contract(self):
        message = {"message": "lên lịch giúp mình"}
        cases = {
            "COMPLETED": (ScriptedLlm(), Clients()),
            # Thiếu destination: agent phải hỏi lại chứ không gọi retrieval.
            "NEEDS_CLARIFICATION": (ScriptedLlm(extraction(days=2)), Clients()),
            "NO_RESULTS": (ScriptedLlm(), Clients(products=[])),
            # Chỉ có combo, không xếp được slot nào -> còn sản phẩm thật để hiển thị.
            "FALLBACK": (ScriptedLlm(), Clients(products=[dict(PRODUCT, productId="c1",
                                                               name="Combo X", taxonomy="combo")])),
        }
        for expected, (llm, clients) in cases.items():
            with self.subTest(status=expected):
                response = self.post(message, llm=llm, clients=clients)
                body = response.json()
                self.assertEqual(response.status_code, 200, body)
                self.assertEqual(body["status"], expected, body)
                self.assert_conforms(ITINERARIES, 200, body, expected)

    # ---------------------------------------------------------------- lỗi

    def test_every_error_path_matches_the_contract(self):
        message = {"message": "lên lịch giúp mình"}
        refusal = ScriptedLlm(extraction(destination="Nha Trang", days=2)
                              .model_copy(update={"domain": "side_effect"}))
        cases = [
            # Chặn ở route/pydantic, không đi qua finalize_node.
            ("body rỗng", 422, "VALIDATION_ERROR", {}, ScriptedLlm(), Clients()),
            ("intentOverride thiếu conversationId", 422, "VALIDATION_ERROR",
             {"intentOverride": {"days": 2}}, ScriptedLlm(), Clients()),
            ("message quá 1000 ký tự", 422, "VALIDATION_ERROR",
             {"message": "a" * 1001}, ScriptedLlm(), Clients()),
            ("tool chưa cấu hình", 503, "SEARCH_UNAVAILABLE", message, ScriptedLlm(), None),
            # Sinh trong graph.
            ("yêu cầu ngoài phạm vi", 400, "VALIDATION_ERROR", message, refusal, Clients()),
            ("số ngày ngoài 1–7", 400, "INVALID_TRIP_DURATION", message,
             ScriptedLlm(extraction(destination="Nha Trang", days=20)), Clients()),
            ("hội thoại không tồn tại", 404, "CONVERSATION_NOT_FOUND",
             {"conversationId": "conv-khong-co", **message}, ScriptedLlm(), Clients()),
            ("điểm đến chưa hỗ trợ", 422, "UNSUPPORTED_DESTINATION", message,
             ScriptedLlm(extraction(destination="Sao Hỏa", days=2)), Clients()),
            ("model lỗi", 503, "LLM_UNAVAILABLE", message, ScriptedLlm(fail=True), Clients()),
            ("search lỗi", 503, "SEARCH_UNAVAILABLE", message, ScriptedLlm(), Clients(fail=True)),
        ]
        for label, status, code, payload, llm, clients in cases:
            with self.subTest(case=label):
                response = self.post(payload, llm=llm, clients=clients)
                body = response.json()
                self.assertEqual(response.status_code, status, body)
                self.assertEqual(body["error"]["code"], code, body)
                self.assert_conforms(ITINERARIES, status, body, label)

    def test_error_codes_come_from_the_shared_enum(self):
        """Mã lỗi tự đặt sẽ lọt qua ErrorResponse nếu enum không được kiểm riêng."""
        allowed = set(schema("ErrorCode")["enum"])
        response = self.post({"message": "lên lịch"}, clients=None)
        self.assertIn(response.json()["error"]["code"], allowed)

    def test_unsupported_destination_carries_the_details_web_needs(self):
        """§9.4 hợp đồng Frontend: Web dựng lại chip điểm đến và tiếp tục hội thoại từ details."""
        response = self.post({"message": "lên lịch"},
                             llm=ScriptedLlm(extraction(destination="Sao Hỏa", days=2)))
        details = response.json()["error"]["details"]
        self.assertEqual(response.status_code, 422)
        self.assertEqual(set(details), {"destination", "supportedDestinations", "conversationId"})
        self.assertEqual(details["supportedDestinations"], ["Nha Trang"])

    # ---------------------------------------------------------------- SSE

    def test_stream_only_emits_declared_events_and_a_valid_final_response(self):
        with TestClient(app) as client:
            app.state.itinerary_llm = ScriptedLlm()
            app.state.itinerary_http_clients = Clients()
            response = client.post(f"/api/v1{STREAM}", json={"message": "lên lịch giúp mình"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("200", DOC["paths"][STREAM]["post"]["responses"])

        names, payloads = [], []
        for line in response.text.splitlines():
            if line.startswith("event: "):
                names.append(line.removeprefix("event: "))
            elif line.startswith("data: "):
                payloads.append(json.loads(line.removeprefix("data: ")))

        allowed = set(schema("AssistantStreamEvent")["properties"]["event"]["enum"])
        self.assertEqual(set(names) - allowed, set(), "SSE phát event ngoài enum contract")
        self.assertEqual(names[0], "run.started")
        self.assertEqual(names[1], "graph.topology")
        self.assertEqual(names[-1], "run.completed")

        final = payloads[-1]
        self.assert_conforms(ITINERARIES, final["httpStatus"], final["response"], "run.completed")

    def test_stream_reports_a_graph_error_as_run_failed(self):
        """Lỗi sinh trong graph (hội thoại hết hạn) là run.failed mang Error Envelope, không phải run.completed."""
        with TestClient(app) as client:
            app.state.itinerary_llm = ScriptedLlm()
            app.state.itinerary_http_clients = Clients()
            response = client.post(f"/api/v1{STREAM}",
                                   json={"conversationId": "conv-khong-co", "message": "đổi sang Hà Nội"})
        events = []
        for block in response.text.strip().split("\n\n"):
            name, data = block.split("\n", 1)
            events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
        self.assertEqual(events[-1][0], "run.failed")
        self.assertNotIn("run.completed", [name for name, _ in events])
        final = events[-1][1]
        self.assertEqual(final["httpStatus"], 404)
        self.assertEqual(final["error"]["error"]["code"], "CONVERSATION_NOT_FOUND")
        self.assert_conforms(ITINERARIES, 404, final["error"], "run.failed")

    def test_stream_never_leaks_prompt_state_or_credentials(self):
        """Hợp đồng Agent §4.1: event chỉ mang ID node, thứ tự, trạng thái, thời lượng, response."""
        with TestClient(app) as client:
            app.state.itinerary_llm = ScriptedLlm()
            app.state.itinerary_http_clients = Clients()
            response = client.post(f"/api/v1{STREAM}", json={"message": "lên lịch giúp mình"},
                                   headers={"Authorization": "Bearer secret-token"})
        allowed = {"sequence", "nodeId", "outcome", "message", "durationMs"}
        for line in response.text.splitlines():
            if not line.startswith("data: "):
                continue
            payload = json.loads(line.removeprefix("data: "))
            if "nodeId" in payload:
                self.assertEqual(set(payload) - allowed, set())
        self.assertNotIn("secret-token", response.text)

    def test_stream_rejects_a_bad_request_before_opening_the_stream(self):
        """Request sai schema phải là HTTP 422, không phải run.failed trong một stream đã mở."""
        response = self.post({}, path=STREAM)
        self.assertEqual(response.status_code, 422)
        self.assert_conforms(STREAM, 422, response.json(), "stream body rỗng")

    # ---------------------------------------------------------------- status

    def test_status_endpoint_matches_the_contract(self):
        with TestClient(app) as client:
            app.state.itinerary_http_clients = Clients()
            response = client.get("/api/v1/assistant/status")
        self.assertEqual(response.status_code, 200)
        errors = [e.message for e in validator("AssistantStatus").iter_errors(response.json())]
        self.assertEqual(errors, [])

    def test_status_reports_the_llm_mode(self):
        """llmMode là field additive: mọi giá trị enum phải hợp lệ với AssistantStatus."""
        for mode in ("live", "disabled", "unavailable"):
            with self.subTest(mode=mode):
                with TestClient(app) as client:
                    app.state.itinerary_http_clients = Clients()
                    app.state.itinerary_llm_mode = mode
                    response = client.get("/api/v1/assistant/status")
                body = response.json()
                self.assertEqual(body["llmMode"], mode)
                errors = [e.message for e in validator("AssistantStatus").iter_errors(body)]
                self.assertEqual(errors, [])

    # ------------------------------------------------------------ LLM tắt

    def test_request_without_an_llm_fails_with_a_declared_503(self):
        """ITINERARY_USE_LLM=false: không có client, cũng không được có nhánh dự phòng gọi mạng.

        Xoá hết API key trong môi trường, nếu không `get_llm()` trong node sẽ dựng client thật
        và bài test này lặng lẽ gọi ra ngoài internet.
        """
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "GEMINI_API_KEY": "",
                                     "ANTHROPIC_API_KEY": "", "ITINERARY_USE_LLM": "false"}):
            get_settings.cache_clear()
            try:
                response = self.post({"message": "3 ngày Nha Trang"}, llm=None)
            finally:
                get_settings.cache_clear()
        body = response.json()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(body["error"]["code"], "LLM_UNAVAILABLE")
        self.assert_conforms(ITINERARIES, 503, body, "llm disabled")

    # ---------------------------------------------------------------- bề mặt

    def test_assistant_exposes_no_route_outside_the_contract(self):
        """Một route không có trong OpenAPI là bề mặt không ai sinh được client, không ai test được.

        Đọc bề mặt qua `app.openapi()` chứ không duyệt `app.routes`: FastAPI gộp router con
        thành `_IncludedRouter` không mang `path`, nên duyệt routes cho ra tập rỗng và phép so
        sánh luôn đúng một cách vô nghĩa.
        """
        declared = {f"/api/v1{path}" for path in DOC["paths"]}
        served = {
            path
            for path, operations in app.openapi()["paths"].items()
            for operation in operations.values()
            if "assistant" in (operation.get("tags") or [])
        }
        self.assertEqual(served, served & declared,
                         f"route ngoài contract: {sorted(served - declared)}")


if __name__ == "__main__":
    unittest.main()
