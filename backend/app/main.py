"""FastAPI 入口：API + 单页应用托管，一个端口跑完全站。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .bootstrapping import bootstrap_all
from .config import settings
from .db import init_db, session_scope
from .jobs.scheduler import next_jobs, start_scheduler, stop_scheduler
from .providers.registry import registry
from .ratelimit import rate_limit_middleware, security_headers_middleware
from .routers import (
    admin,
    ai,
    analytics,
    auth,
    backtest,
    draws,
    games,
    health,
    predict,
    providers,
    sync,
    tickets,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("caipiao")

STATIC_DIR = Path(settings.static_dir)

DEFAULT_ADMIN_PASSWORD = "TANGlidong24ban@"


def _security_selfcheck() -> None:
    """启动时体检，把不安全配置明确喊出来（不改行为，只提示）。"""
    if settings.admin_password == DEFAULT_ADMIN_PASSWORD:
        logger.warning("安全提示：仍在用默认管理员密码，请登录后台「修改我的密码」或改 deploy/.env 的 ADMIN_PASSWORD")
    if not settings.cookie_secure:
        logger.warning("安全提示：COOKIE_SECURE=false，生产走 HTTPS 时应置 true（Cookie Secure + HSTS）")
    if settings.enable_docs:
        logger.warning("安全提示：ENABLE_DOCS=true，/api/docs 对外暴露，生产建议设为 false")
    if settings.admin_token:
        logger.warning("安全提示：ADMIN_TOKEN 已启用，静态令牌不受 CSRF 与会话吊销保护，脚本用完建议清空")
    if not settings.secret_key:
        logger.info("AI Key 与会话使用本地密钥文件（data/data-secret.key，chmod 600）")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_providers()
    with session_scope() as session:
        info = bootstrap_all(session)
    if info.get("admin_created"):
        logger.info("默认管理员已就绪：%s", settings.admin_username)
    _security_selfcheck()
    if settings.sync_enabled:
        start_scheduler()
    logger.info("caipiao-lab %s up on %s:%s", __version__, settings.app_host, settings.app_port)
    yield
    stop_scheduler()


def _seed_providers() -> None:
    from sqlalchemy import select

    from .models import Provider

    with session_scope() as session:
        existing = {row.code for row in session.execute(select(Provider)).scalars().all()}
        for provider in registry.all():
            if provider.code in existing:
                continue
            session.add(
                Provider(
                    code=provider.code,
                    name=provider.name,
                    enabled=True,
                    priority=provider.priority,
                    rate_limit=provider.rate_limit,
                    config={"supported_games": sorted(provider.supported_games)},
                )
            )


app = FastAPI(
    title="福彩数据与预测平台",
    version=__version__,
    description="福利彩票全彩种历史数据、统计分析、概率预测与回测。",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.enable_docs else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.enable_docs else None,
)


@app.middleware("http")
async def read_only_guard(request: Request, call_next):
    """只读模式：拦掉所有写操作（登录除外，否则管理员进不去）。"""
    path = request.url.path
    if (
        settings.read_only
        and request.method in ("POST", "PATCH", "PUT", "DELETE")
        and path.startswith("/api/")
        and not path.startswith("/api/auth/")
    ):
        return JSONResponse({"detail": "当前为只读模式"}, status_code=403)
    return await call_next(request)


app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

_origins = [settings.dev_origin, "http://localhost:5173", "http://127.0.0.1:5173"]
for extra in (settings.cors_origins or "").split(","):
    item = extra.strip()
    if item:
        _origins.append(item)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Token", "X-Device-Id", "X-CSRF"],
)

api_prefix = "/api"
for module in (health, games, draws, analytics, predict, backtest, sync, providers, tickets, auth, ai, admin):
    app.include_router(module.router, prefix=api_prefix)

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        # /api 前缀下的未知路径要回 404 JSON，不能被 SPA 兜底成 index.html
        # （否则前端 fetch 拿到 200 + HTML，解析失败难排查）
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
else:  # 开发期前端独立跑

    @app.get("/", include_in_schema=False)
    async def dev_root():
        return {"service": "caipiao-lab", "version": __version__,
                "hint": "前端未构建；开发用 5173，生产请 npm run build 后拷到 backend/app/static"}


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)


if __name__ == "__main__":
    run()
