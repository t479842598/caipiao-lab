"""入站限流 + 安全响应头。纯内存滑窗，单实例部署足够。"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import settings

HEAVY_PREFIXES = ("/api/predict", "/api/backtest", "/api/ai/")
HEAVY_EXACT = ("/api/sync",)

# ip -> deque[timestamp]
_hits: dict[str, deque[float]] = defaultdict(deque)
_heavy: dict[str, deque[float]] = defaultdict(deque)

CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _hit(bucket: dict[str, deque[float]], key: str, limit: int, window: float = 60.0) -> bool:
    now = time.monotonic()
    dq = bucket[key]
    while dq and now - dq[0] > window:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    if len(bucket) > 20000:  # 防内存膨胀
        bucket.clear()
    return True


def is_heavy(path: str) -> bool:
    return path.startswith(HEAVY_PREFIXES) or path in HEAVY_EXACT


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/"):
        return await call_next(request)
    ip = _client_ip(request)

    if not _hit(_hits, ip, settings.inbound_rate_per_min):
        return JSONResponse({"detail": "请求过于频繁，请稍后重试"}, status_code=429,
                            headers={"Retry-After": "60"})

    if request.method in ("POST", "PATCH", "PUT", "DELETE") and is_heavy(path):
        if not _hit(_heavy, ip, settings.heavy_rate_per_min):
            return JSONResponse({"detail": "该操作消耗较大，请降低频率"}, status_code=429,
                                headers={"Retry-After": "60"})

    return await call_next(request)


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if not request.url.path.startswith("/api/"):
        headers.setdefault("Content-Security-Policy", CSP)
    if settings.cookie_secure:
        headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains")
    return response


def reset() -> None:
    _hits.clear()
    _heavy.clear()
