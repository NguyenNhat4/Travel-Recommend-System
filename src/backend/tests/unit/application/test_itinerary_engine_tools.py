"""Tool itinerary gọi engine trong tiến trình (`ITINERARY_DATA_MODE=inprocess`).

Thành công phải khớp route và adapter HTTP; lỗi phải về đúng mã, không lộ thông điệp engine hay token; token hỏng
là 401 trước khi engine chạy. Dùng fixture `services` (scope session) nên mọi test là hàm pytest chạy `asyncio.run`.
"""
import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.api.errors import install_error_handlers
from src.backend.app.api.v1.routes import catalog as catalog_routes
from src.backend.app.api.v1.routes import recommendations as recommendation_routes
from src.backend.app.api.v1.routes import search as search_routes
from src.backend.app.application.auth.principal import AuthenticatedUser
from src.backend.app.application.catalog.use_cases import GetProductDetail, GetSimilarProducts
from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.application.itinerary.engine_tools import InProcessItineraryTools
from src.backend.app.application.itinerary.tool_contracts import validate
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.core.request_context import bind_request_id, current_request_id, reset_request_id
from src.backend.app.infrastructure.auth.keys import generate_rsa_pem_pair
from src.backend.app.infrastructure.clients.itinerary_http_clients import ItineraryHttpClients
from src.backend.tests.conftest import ROWS, P
from src.backend.tests.fakes.auth import jwt_issuer
from src.backend.tests.fakes.auth_app import AuthWorld
from src.backend.tests.fakes.catalog import InMemoryProductQuery

# cdp_user_id "P1" có lịch sử trong EVENTS của conftest: token của user này ra gợi ý cá nhân hoá.
USER = AuthenticatedUser("u-1", "p1@example.com", "x", "P1", "P1")
SEARCH = {"query": "nghỉ dưỡng biển", "destination": "Nha Trang", "limit": 20, "offset": 0}


def run(coro):
    return asyncio.run(coro)


def token_for(issuer) -> str:
    return issuer.issue_access_token(USER, session_id="s_abc", amr=("pwd",))[0]


def tools_with(*, search=None, recommend=None, index=None, product_detail=None, similar=None, verifier=None,
               revoked=None, executor=None) -> InProcessItineraryTools:
    return InProcessItineraryTools(
        search=lambda: search, recommend=lambda: recommend, index=lambda: index,
        product_detail=lambda: product_detail, similar_products=lambda: similar,
        token_verifier=lambda: verifier, revoked_tokens=lambda: revoked, executor=executor,
    )


def tool_error(coro) -> ToolError:
    with pytest.raises(ToolError) as caught:
        run(coro)
    return caught.value


@pytest.fixture
def world():
    return AuthWorld([USER])


@pytest.fixture
def detail():
    return GetProductDetail(InMemoryProductQuery(ROWS))


def backend(services, world, detail) -> FastAPI:
    """Đúng các route mà adapter HTTP gọi, trên cùng engine với adapter trong tiến trình."""
    app = FastAPI()
    install_error_handlers(app)  # lỗi catalog ra đúng Error Envelope như app thật
    for module in (search_routes, recommendation_routes, catalog_routes):
        app.include_router(module.router, prefix="/api/v1")
    app.state.search = services["search"]
    app.state.recommend = services["recommend"]
    app.state.index = services["index"]
    app.state.get_product_detail = detail
    app.state.token_verifier = world.issuer
    app.state.revoked_tokens = world
    return app


def stable(body: dict) -> dict:
    """Bỏ phần phụ thuộc đồng hồ: generatedAt, latencyMs và score/contribution (decay theo thời điểm gọi)."""
    body = deepcopy(body)
    body.pop("generatedAt", None)
    body.get("diagnostics", {}).pop("latencyMs", None)
    for item in body.get("recommendations", []):
        item.pop("score", None)
        item["because"] = [(b["productId"], b["event"]) for b in item["because"]]
    return body


class Spy:
    """Engine đồng bộ giả: ghi lại lời gọi, trả `result` hoặc ném `error`."""

    def __init__(self, result=None, error=None):
        self.result, self.error = result, error
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return deepcopy(self.result)


# ------------------------------------------------------------------ thành công khớp route


def test_success_matches_the_route_and_the_http_adapter(services, world, detail):
    tools = tools_with(search=services["search"], recommend=services["recommend"], index=services["index"],
                       product_detail=detail, verifier=world.issuer, revoked=world)
    bearer = f"Bearer {token_for(world.issuer)}"

    async def scenario():
        transport = httpx.ASGITransport(app=backend(services, world, detail))
        async with httpx.AsyncClient(base_url="http://backend.test/api/v1/", transport=transport) as http:
            over_http = ItineraryHttpClients(http)
            route = (await http.get("search", params={"q": SEARCH["query"], "destination": "Nha Trang",
                                                         "limit": 20, "offset": 0})).json()
            assert {key: value for key, value in route.items() if key not in {"cutoff", "diagnostics"}} \
                == await over_http.search_products(SEARCH) == await tools.search_products(SEARCH)

            for authorization in (None, bearer):
                request = {"k": 5, "destination": "Nha Trang"}
                route = (await http.get("recommendations", params=request,
                                        headers={"Authorization": authorization} if authorization else {})).json()
                in_process = await tools.get_recommendations(request, authorization)
                assert stable(route) == stable(await over_http.get_recommendations(request, authorization)) \
                    == stable(in_process)
                validate("get_recommendations", in_process, "response")
                assert in_process["cdpUserId"] == (USER.cdp_user_id if authorization else None)

            assert (await http.get("destinations")).json() == await over_http.list_destinations() \
                == await tools.list_destinations()
            assert (await http.get("products/H1")).json() == await over_http.get_product_detail("H1") \
                == await tools.get_product_detail("H1")
            for adapter in (over_http, tools):
                with pytest.raises(ToolError) as caught:
                    await adapter.get_product_detail("khong-co")
                error = caught.value
                assert (error.code, error.retryable, error.http_status) == ("PRODUCT_NOT_FOUND", False, 404)

    run(scenario())
    payload = run(tools.search_products(SEARCH))
    assert payload["results"] and "cutoff" not in payload and "diagnostics" not in payload
    validate("search_products", payload, "response")
    assert valid("DestinationListResponse", run(tools.list_destinations()))
    assert valid("ProductDetail", run(tools.get_product_detail("H1")))


def test_personalised_recommendations_differ_from_the_anonymous_ones(services, world):
    """Chứng minh token thật sự được dùng: user P1 có lịch sử nên không rơi về popular của khách."""
    tools = tools_with(recommend=services["recommend"], verifier=world.issuer, revoked=world)
    anonymous = run(tools.get_recommendations({"k": 5}))
    personal = run(tools.get_recommendations({"k": 5}, f"Bearer {token_for(world.issuer)}"))
    assert anonymous["strategy"] == "popular" and anonymous["cdpUserId"] is None
    assert personal["strategy"] != "popular" and personal["cdpUserId"] == "P1"


# ------------------------------------------------------------------ engine lấy lại mỗi lời gọi


def test_engine_is_resolved_on_every_call():
    engines = {"search": Spy({"results": [], "total": 1})}
    tools = InProcessItineraryTools(search=lambda: engines["search"], recommend=lambda: None, index=lambda: None,
                                    product_detail=lambda: None, similar_products=lambda: None,
                                    token_verifier=lambda: None, revoked_tokens=lambda: None)
    assert run(tools.search_products({"query": "biển"}))["total"] == 1
    engines["search"] = Spy({"results": [], "total": 2})
    assert run(tools.search_products({"query": "biển"}))["total"] == 2
    engines["search"] = None
    error = tool_error(tools.search_products({"query": "biển"}))
    assert (error.code, error.retryable, error.http_status) == ("SEARCH_UNAVAILABLE", True, 503)


def test_every_tool_is_unavailable_until_recsys_is_ready():
    tools = tools_with()
    for call in (tools.search_products({"query": "biển"}), tools.get_recommendations({"k": 5}),
                 tools.get_product_detail("H1"), tools.list_destinations(), tools.get_similar_products("H1", 8)):
        error = tool_error(call)
        assert (error.code, error.retryable, error.http_status) == ("SEARCH_UNAVAILABLE", True, 503)
    assert tools.product_count is None
    assert tools_with(index=SimpleNamespace(units=[1, 2, 3])).product_count == 3


# ------------------------------------------------------------------ map lỗi


def test_unexpected_engine_error_is_retryable_and_never_leaks(caplog):
    tools = tools_with(search=Spy(error=RuntimeError("secret upstream detail")))
    gateway = ItineraryToolGateway(tools, tools, tools)
    with caplog.at_level(logging.DEBUG, logger="uvicorn.error"):
        result = run(gateway.execute({"id": "a", "name": "search_products", "args": {"query": "biển"}}))
    assert result["error"] == {"code": "SEARCH_UNAVAILABLE", "retryable": True, "httpStatus": 503}
    assert "secret" not in str(result)
    assert "secret" not in caplog.text
    assert "reason=RuntimeError" in caplog.text
    # Frame traceback có mặt để lần ra bug, dù thông điệp lỗi bị giữ lại.
    assert "raise self.error" in caplog.text


def test_catalog_errors_keep_their_code_and_status(detail):
    error = tool_error(tools_with(product_detail=detail).get_product_detail("khong-co"))
    assert (error.code, error.retryable, error.http_status) == ("PRODUCT_NOT_FOUND", False, 404)


def test_non_json_result_is_an_invalid_tool_response():
    tools = tools_with(search=Spy({"results": [], "total": 0, "topScore": float("nan")}))
    error = tool_error(tools.search_products({"query": "biển"}))
    assert (error.code, error.retryable) == ("INVALID_TOOL_RESPONSE", False)


def test_cancellation_propagates_instead_of_becoming_a_tool_error():
    release = threading.Event()

    def slow(*_args, **_kwargs):
        release.wait(5)
        return {"results": [], "total": 0}

    async def scenario():
        try:
            await asyncio.wait_for(tools_with(search=slow).search_products({"query": "biển"}), 0.05)
        finally:
            release.set()

    with pytest.raises(TimeoutError):
        run(scenario())


# ------------------------------------------------------------------ xác thực


def forged_token() -> str:
    """JWT đúng dạng nhưng ký bằng khoá lạ: bị từ chối ở bước kiểm chữ ký, không phải ở bước đọc header."""
    return token_for(jwt_issuer(private_key=generate_rsa_pem_pair()[0]))


@pytest.mark.parametrize("case", ["forged", "malformed", "expired", "revoked", "basic"])
def test_bad_token_is_401_before_the_engine_runs(case, world, caplog):
    if case == "forged":
        token = forged_token()
    else:
        token = token_for(jwt_issuer(access_ttl_seconds=-120) if case == "expired" else world.issuer)
    if case == "revoked":
        world.revoked_jti.add(world.issuer.verify(token).token_id)
    header = {"malformed": "Bearer not.a.jwt", "basic": "Basic x"}.get(case, f"Bearer {token}")
    engine = Spy()
    tools = tools_with(recommend=engine, verifier=world.issuer, revoked=world)
    with caplog.at_level(logging.DEBUG, logger="uvicorn.error"):
        error = tool_error(tools.get_recommendations({"k": 5}, header))
    assert error.http_status == 401 and not error.retryable
    assert error.code == ("TOKEN_EXPIRED" if case == "expired" else "INVALID_TOKEN")
    assert engine.calls == []
    assert token not in caplog.text and "not.a.jwt" not in caplog.text


def test_bad_token_is_401_even_when_recsys_is_not_ready(world):
    # 401 thắng 503: token được kiểm trước khi adapter hỏi tới engine.
    tools = tools_with(recommend=None, verifier=world.issuer, revoked=world)
    error = tool_error(tools.get_recommendations({"k": 5}, f"Bearer {forged_token()}"))
    assert (error.code, error.retryable, error.http_status) == ("INVALID_TOKEN", False, 401)


def test_revocation_store_outage_is_retryable_not_anonymous(world, caplog):
    class DownRevocations:
        async def is_revoked(self, token_id):
            raise ConnectionError("redis down")

    token = token_for(world.issuer)
    engine = Spy()
    tools = tools_with(recommend=engine, verifier=world.issuer, revoked=DownRevocations())
    with caplog.at_level(logging.DEBUG, logger="uvicorn.error"):
        error = tool_error(tools.get_recommendations({"k": 5}, f"Bearer {token}"))
    assert (error.code, error.retryable, error.http_status) == ("SEARCH_UNAVAILABLE", True, 503)
    assert engine.calls == []
    assert token not in caplog.text


@pytest.mark.parametrize("header", [None, ""])
def test_missing_or_empty_header_is_a_guest_like_http_mode(header, services):
    # Không cần verifier: header rỗng không có token nào để kiểm.
    result = run(tools_with(recommend=services["recommend"]).get_recommendations({"k": 5}, header))
    assert result["cdpUserId"] is None
    assert result["strategy"] == "popular"


# ------------------------------------------------------------------ luồng thread


def test_pool_job_keeps_the_request_id_and_runs_on_the_itinerary_pool():
    seen = {}

    def engine(q, **kwargs):
        seen.update(request_id=current_request_id(), thread=threading.current_thread().name)
        return {"results": [], "total": 0}

    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="itinerary-tool")

    async def scenario():
        token = bind_request_id("req-inprocess")
        try:
            return await tools_with(search=engine, executor=pool).search_products({"query": "biển"})
        finally:
            reset_request_id(token)

    try:
        run(scenario())
    finally:
        pool.shutdown(wait=True)
    assert seen["request_id"] == "req-inprocess"
    assert seen["thread"].startswith("itinerary-tool")


# ------------------------------------------------------------------ dữ liệu trả về


def test_result_is_a_copy_not_the_engine_index(services):
    index = services["index"]
    payload = run(tools_with(search=services["search"]).search_products(SEARCH))
    item = payload["results"][0]
    item["attributes"]["injected"] = True
    assert "injected" not in index.units[index.idx[item["productId"]]].attributes


def test_search_forwards_only_the_engine_filters_and_never_identity():
    engine = Spy({"results": [], "total": 0})
    request = {"query": "  khách sạn gia đình ", "destination": "Nha Trang", "taxonomy": None, "limit": 5,
               "offset": 0, "priceMax": 2_000_000, "starRatingMin": 4, "availableOnly": True,
               "sort": "relevance", "includeVariants": False}
    run(tools_with(search=engine).search_products(request))
    run(tools_with(search=engine).search_products({"query": "golf", "taxonomy": "golf"}))
    assert engine.calls == [
        (("khách sạn gia đình",), {"destination": "Nha Trang", "limit": 5, "offset": 0}),
        (("golf",), {"taxonomy": "golf"}),
    ]


# ------------------------------------------------------------------ similar (lượt đổi món)

# X1 có trong catalog nhưng không phải search unit và không có cha: engine không có vector cho nó → 409.
SIMILAR_ROWS = ROWS + [P("X1", "Phòng chưa gắn cha", "hotel", "Nha Trang", {"level": "room"}, price=1_000_000)]


@pytest.fixture
def similar(services):
    return GetSimilarProducts(InMemoryProductQuery(SIMILAR_ROWS), services["similar"])


def test_similar_matches_the_route_and_the_http_adapter(services, world, detail, similar):
    tools = tools_with(similar=similar)
    app = backend(services, world, detail)
    app.state.get_similar_products = similar

    async def scenario():
        token = bind_request_id("req-similar")
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(base_url="http://backend.test/api/v1/", transport=transport) as http:
                route = (await http.get("products/R1/similar", params={"limit": 4})).json()
                over_http = await ItineraryHttpClients(http).get_similar_products("R1", 4)
            return route, over_http, await tools.get_similar_products("R1", 4)
        finally:
            reset_request_id(token)

    route, over_http, in_process = run(scenario())
    assert route == over_http == in_process
    # Hạng phòng R1 được resolve về khách sạn cha H1; requestId như route thêm vào.
    assert (in_process["productId"], in_process["resolvedFrom"], in_process["requestId"]) == ("H1", "R1", "req-similar")
    assert in_process["results"] and {r["taxonomy"] for r in in_process["results"]} == {"hotel"}
    validate("get_similar_products", in_process, "response")


def test_similar_errors_keep_their_catalog_code(similar):
    tools = tools_with(similar=similar)
    for product_id, expected in (("khong-co", ("PRODUCT_NOT_FOUND", False, 404)),
                                 ("X1", ("PRODUCT_NOT_INDEXED", False, 409))):
        error = tool_error(tools.get_similar_products(product_id, 8))
        assert (error.code, error.retryable, error.http_status) == expected


def test_similar_is_retryable_503_until_recsys_is_ready():
    # Provider None: catalog chưa dựng. Use case có nhưng engine None: RecSys chưa nạp (CatalogUnavailable).
    not_ready = GetSimilarProducts(InMemoryProductQuery(SIMILAR_ROWS), None)
    for tools in (tools_with(similar=None), tools_with(similar=not_ready)):
        error = tool_error(tools.get_similar_products("H1", 8))
        assert (error.code, error.retryable, error.http_status) == ("SEARCH_UNAVAILABLE", True, 503)


def test_similar_through_the_gateway_never_logs_the_anchor(similar, caplog):
    tools = tools_with(similar=similar)
    gateway = ItineraryToolGateway(tools, tools, tools, similar=tools)
    with caplog.at_level(logging.DEBUG, logger="uvicorn.error"):
        found = run(gateway.execute({"id": "a", "name": "get_similar_products", "args": {"productId": "R1"}}))
        missing = run(gateway.execute({"id": "b", "name": "get_similar_products",
                                       "args": {"productId": "khong-co"}}))
    assert found["data"]["results"] and found["arguments"] == {"productId": "R1", "limit": 8}
    assert missing["error"] == {"code": "PRODUCT_NOT_FOUND", "retryable": False, "httpStatus": 404}
    assert "name=get_similar_products outcome=ok" in caplog.text
    assert "R1" not in caplog.text and "khong-co" not in caplog.text
