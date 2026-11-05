import time, uuid, logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("http.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start    = time.perf_counter()
        response = await call_next(request)
        ms       = (time.perf_counter() - start) * 1000

        logger.info(
            "method=%s path=%s status=%d ms=%.1f id=%s",
            request.method, request.url.path,
            response.status_code, ms, request_id,
        )
        response.headers["X-Request-ID"]     = request_id
        response.headers["X-Response-Time"]  = f"{ms:.1f}ms"
        return response
