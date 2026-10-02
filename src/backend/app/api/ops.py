"""Endpoint vận hành ngoài `/api/v1`, cùng nhóm với `/health` (docs/prd/deployment-plan.md §5).

`GET /metrics`: chỉ số Prometheus (số lần gọi, lỗi, p50 / p95 theo nguồn web / agent, catalog trong bộ nhớ).
`GET /internal/calls?after=&limit=`: các lần gọi gần nhất cho monitor realtime. Không có dữ liệu cá nhân hay bí mật.
"""
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

ops_router = APIRouter(include_in_schema=False)


def _telemetry(request: Request):
    return getattr(request.app.state, "call_telemetry", None)


@ops_router.get("/metrics")
async def metrics(request: Request):
    telemetry = _telemetry(request)
    if telemetry is None:
        return PlainTextResponse("# telemetry chưa bật\n", status_code=503)
    return PlainTextResponse(telemetry.prometheus(), media_type="text/plain; version=0.0.4; charset=utf-8")


@ops_router.get("/internal/calls")
async def calls(request: Request, after: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)):
    telemetry = _telemetry(request)
    if telemetry is None:
        return JSONResponse({"error": "telemetry chưa bật"}, status_code=503)
    return JSONResponse(telemetry.snapshot(after, limit), headers={"Cache-Control": "no-store"})
