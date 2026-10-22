"""OpenAI 兼容的 Chat Completions 客户端。

覆盖 openai / deepseek / azure / moonshot / zhipu / ollama / 任意自定义网关，
全部走 /v1/chat/completions 协议，只换 base_url 与鉴权头。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import settings
from ..security import decrypt_secret

VENDORS: dict[str, dict[str, str]] = {
    "openai": {"label": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "deepseek": {"label": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "moonshot": {"label": "Moonshot 月之暗面", "base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "zhipu": {"label": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
    "qwen": {"label": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "ollama": {"label": "本地 Ollama", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b"},
    "custom": {"label": "自定义网关", "base_url": "", "model": ""},
}


def default_base_url(vendor: str) -> str:
    return VENDORS.get(vendor, VENDORS["custom"])["base_url"]


def default_model(vendor: str) -> str:
    return VENDORS.get(vendor, VENDORS["custom"])["model"]


@dataclass
class AiReply:
    ok: bool
    text: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def _endpoint(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        return ""
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1") or base.endswith("/v4"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def chat(
    *,
    provider: Any,
    system: str,
    user: str,
    timeout: float | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> AiReply:
    """同步调用（放线程池执行，别在 event loop 里直接跑）。"""
    started = time.monotonic()
    base = provider.base_url or default_base_url(provider.vendor)
    url = _endpoint(base)
    if not url:
        return AiReply(ok=False, error="供应商未配置 base_url")
    api_key = decrypt_secret(provider.api_key_enc)
    if not api_key and provider.vendor != "ollama":
        return AiReply(ok=False, error="供应商未配置 api_key")

    body = {
        "model": provider.model or default_model(provider.vendor),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": provider.temperature if temperature is None else temperature,
        "max_tokens": provider.max_tokens if max_tokens is None else max_tokens,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    kwargs: dict[str, Any] = {}
    if settings.http_proxy:
        kwargs["proxy"] = settings.http_proxy

    try:
        with httpx.Client(timeout=timeout or settings.ai_timeout, **kwargs) as client:
            resp = client.post(url, json=body, headers=headers)
    except httpx.HTTPError as exc:
        return AiReply(ok=False, error=f"网络错误：{exc}", latency_ms=int((time.monotonic() - started) * 1000))

    latency = int((time.monotonic() - started) * 1000)
    if resp.status_code >= 400:
        snippet = resp.text[:300].replace("\n", " ")
        return AiReply(ok=False, error=f"HTTP {resp.status_code}：{snippet}", latency_ms=latency)

    try:
        data = resp.json()
    except ValueError:
        return AiReply(ok=False, error="返回不是 JSON", latency_ms=latency)

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return AiReply(ok=False, error="返回结构不含 choices[0].message.content",
                       latency_ms=latency, raw=data)

    usage = data.get("usage") or {}
    return AiReply(
        ok=True,
        text=str(text).strip(),
        model=str(data.get("model") or body["model"]),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        latency_ms=latency,
        raw=data,
    )
