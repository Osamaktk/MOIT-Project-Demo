from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict, deque
from threading import Lock
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("pc_command_center.requests")
if not logger.handlers:
    output = logging.StreamHandler()
    output.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(output)
logger.setLevel(logging.INFO)
logger.propagate = False
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class SlidingWindowLimiter:
    """Single-process sliding-window limits for the local demo server."""

    def __init__(self, window_seconds: int = 60) -> None:
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        with self._lock:
            events = self._requests[key]
            while events and current - events[0] >= self.window_seconds:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(current)
            return True


class RequestSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, auth_limit: int = 60, ai_limit: int = 30) -> None:
        super().__init__(app)
        self.auth_limit = auth_limit
        self.ai_limit = ai_limit
        self.limiter = SlidingWindowLimiter()

    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        supplied_id = request.headers.get("X-Request-ID", "")
        request_id = supplied_id if REQUEST_ID_PATTERN.fullmatch(supplied_id) else uuid4().hex
        request.state.request_id = request_id
        client_ip = request.client.host if request.client else "unknown"
        bucket: str | None = None
        limit = 0
        path = request.url.path
        if request.method == "POST" and path == "/api/v1/auth/login":
            bucket, limit = "auth", self.auth_limit
        elif request.method == "POST" and (path in {"/api/v1/records/search", "/api/v1/jarvis/chat", "/api/v1/jarvis/stt"} or (path.startswith("/api/v1/meetings/") and path.endswith("/process"))):
            bucket, limit = "ai", self.ai_limit

        if bucket and not self.limiter.allow(f"{bucket}:{client_ip}", limit):
            response = JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "Too many requests. Wait briefly and try again.", "details": {}}})
        else:
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        logger.info(json.dumps({"event": "request_complete", "request_id": request_id, "method": request.method, "path": path, "status_code": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 2)}, separators=(",", ":")))
        return response
