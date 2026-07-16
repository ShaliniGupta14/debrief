import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.request_context import set_request_id

logger = logging.getLogger("app.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns (or echoes) a request ID, times the request, and logs one
    structured JSON line per request -- our replacement for uvicorn's
    plaintext access log."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            extra={
                "extra_method": request.method,
                "extra_path": request.url.path,
                "extra_status_code": response.status_code,
                "extra_duration_ms": round(duration_ms, 2),
            },
        )
        return response
