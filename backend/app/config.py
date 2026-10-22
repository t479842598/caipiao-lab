"""全局配置：全部来自环境变量 / .env，便于服务器部署时零代码改动。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(ROOT_DIR / "deploy" / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "127.0.0.1"
    app_port: int = 8787
    db_path: str = str(ROOT_DIR / "data" / "lottery.db")

    # ---------- 账号体系 ----------
    secret_key: str = ""              # 为空则首启随机生成并写 data/.secret
    session_ttl_hours: int = 72       # 登录会话有效期
    cookie_secure: bool = False       # 生产走 HTTPS 时置 true
    admin_username: str = "admin"
    admin_password: str = "TANGlidong24ban@"
    admin_token: str = ""             # 兼容旧部署的静态令牌（可选，留空即仅账号登录）
    login_max_fails: int = 5          # 连续失败次数
    login_lock_minutes: int = 15      # 触发后锁定时长
    min_password_length: int = 10

    # ---------- 运行开关 ----------
    read_only: bool = False
    enable_docs: bool = True

    sync_enabled: bool = True
    sync_tz: str = "Asia/Shanghai"
    provider_primary: str = "cwl_official"
    provider_fallback: str = "c500"

    rate_limit_per_min: int = 120     # 出站请求速率（对官方站点保持克制）
    inbound_rate_per_min: int = 240   # 入站每 IP 每分钟上限
    inbound_burst: int = 60
    heavy_rate_per_min: int = 12      # predict / backtest 这类 CPU 接口
    request_timeout: float = 20.0
    page_size: int = 300
    http_proxy: str = ""

    dev_origin: str = "http://127.0.0.1:5173"
    cors_origins: str = ""            # 逗号分隔，留空则仅 dev_origin
    static_dir: str = str(BACKEND_DIR / "app" / "static")

    # ---------- 预测默认值 ----------
    predict_default_count: int = 5
    predict_max_count: int = 100

    # ---------- AI 供应商 ----------
    ai_enabled: bool = True
    ai_timeout: float = 60.0
    ai_max_calls_per_hour: int = 30   # 每 IP 每小时 AI 调用上限
    ai_allow_public_submit: bool = True
    # 是否允许供应商 base_url 指向内网 / 本机（默认禁，防 SSRF；用 Ollama 时开）
    ai_allow_private_endpoint: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
