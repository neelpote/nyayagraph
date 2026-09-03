from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse


logger = logging.getLogger("nyayagraph.requests")


class RequestGuard:
    """Process-local MVP limiter; replace with Redis for multi-replica deployment."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, request: Request) -> bool:
        client = request.client.host if request.client else "unknown"
        ai_path = request.url.path.startswith("/api/v1/ai") or request.url.path.startswith("/api/v1/search")
        login_path = request.url.path in {"/api/v1/auth/login", "/api/v1/auth/dev-login"}
        limit = 15 if login_path else (30 if ai_path else 240)
        window = 60.0
        key = f"{'login' if login_path else ('ai' if ai_path else 'api')}:{client}"
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True

    async def middleware(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        started = time.perf_counter()
        if not self.allow(request):
            response = JSONResponse(status_code=429, content={"detail": "Request rate limit exceeded"})
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        event = {
            "timestamp": time.time(), "request_id": request_id,
            "action": f"{request.method} {request.url.path}", "status": response.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        logger.info(json.dumps(event, separators=(",", ":")))
        return response


request_guard = RequestGuard()
