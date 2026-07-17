import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.metrics import http_request_duration_seconds, http_requests_total
from app.request_context import set_request_id

logger = logging.getLogger("app.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns (or echoes) a request ID, times the request, logs one
    structured JSON line per request (replacing uvicorn's plaintext access
    log), and records Prometheus metrics -- one pass since all three need
    the same start/end timestamps and method/path/status, not three
    middlewares each re-timing the same request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        start = time.perf_counter()
        response = await call_next(request)
        duration_s = time.perf_counter() - start

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            extra={
                "extra_method": request.method,
                "extra_path": request.url.path,
                "extra_status_code": response.status_code,
                "extra_duration_ms": round(duration_s * 1000, 2),
            },
        )

        # The matched route *template* (e.g. "/v1/calls/{call_id}"), not the
        # interpolated path -- using the raw path would give every distinct
        # call ID its own Prometheus label, an unbounded-cardinality time
        # bomb. Falls back to the raw path for genuine 404s, which have no
        # matched route at all.
        route = request.scope.get("route")
        path_label = route.path if route is not None else request.url.path

        http_requests_total.labels(
            method=request.method, path=path_label, status_code=response.status_code
        ).inc()
        http_request_duration_seconds.labels(method=request.method, path=path_label).observe(
            duration_s
        )

        return response
