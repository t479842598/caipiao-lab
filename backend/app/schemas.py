"""API 契约 —— 前后端锁死在这里，先定契约再并行开发。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------- 彩种 / 开奖 ----------
class BallSpecOut(BaseModel):
    key: str
    label: str
    count: int
    min: int
    max: int
    pad: int
    ordered: bool = False
    domain: list[int] = Field(default_factory=list)


class GameOut(BaseModel):
    code: str
    name: str
    short: str
    first_issue: str
    draw_weekdays: list[int] = Field(default_factory=list)
    draw_time: str = ""
    balls: list[BallSpecOut] = Field(default_factory=list)
    latest_issue: str | None = None
    latest_date: date | None = None
    latest_numbers: dict[str, list[str]] | None = None
    next_issue: str | None = None
    draw_count: int = 0


class PrizeOut(BaseModel):
    type: str
    type_num: int | None = None
    type_money: float | None = None


class DrawOut(BaseModel):
    id: int
    game_code: str
    issue: str
    draw_date: date
    week: str = ""
    numbers: dict[str, list[str]]
    ordered: list[str] | None = None
    sales: float | None = None
    pool_money: float | None = None
    content: str = ""
    source: str = ""
    prizes: list[PrizeOut] = Field(default_factory=list)


class DrawPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[DrawOut]


# ---------- 统计 ----------
class FrequencyItem(BaseModel):
    n: int
    count: int
    rate: float
    expected: float
    deviation: float
    recent: list[int] = Field(default_factory=list)


class FrequencyOut(BaseModel):
    game: str
    ball: str
    window: int
    total_draws: int
    items: list[FrequencyItem] = Field(default_factory=list)


class OmissionItem(BaseModel):
    n: int
    current: int
    max: int = 0
    avg: float = 0.0
    last_issue: str | None = None


class OmissionOut(BaseModel):
    game: str
    ball: str
    items: list[OmissionItem] = Field(default_factory=list)


class TrendOut(BaseModel):
    game: str
    ball: str
    issues: list[str] = Field(default_factory=list)
    domain: list[int] = Field(default_factory=list)
    matrix: list[list[int]] = Field(default_factory=list)  # 1=开出 0=未开
    omission: list[list[int]] = Field(default_factory=list)  # 逐期遗漏值


class DistributionOut(BaseModel):
    game: str
    window: int
    sum_hist: list[dict[str, Any]] = Field(default_factory=list)
    span_hist: list[dict[str, Any]] = Field(default_factory=list)
    odd_even_hist: list[dict[str, Any]] = Field(default_factory=list)
    big_small_hist: list[dict[str, Any]] = Field(default_factory=list)
    zone_hist: list[dict[str, Any]] = Field(default_factory=list)
    consecutive_hist: list[dict[str, Any]] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


# ---------- 预测 ----------
class PredictRequest(BaseModel):
    game: str = "ssq"
    count: int = Field(default=5, ge=1, le=100)
    engine: Literal["uniform", "frequency", "omission", "markov", "bayes", "gbdt", "ensemble"] = "ensemble"
    strategy: Literal["balanced", "hot", "cold", "mixed", "random"] = "balanced"
    window: int = Field(default=100, ge=10, le=2000)
    seed: int | None = None
    pick: int | None = Field(default=None, description="快乐8 选几，默认 10")


class TicketNumbers(BaseModel):
    red: list[str] = Field(default_factory=list)
    blue: list[str] = Field(default_factory=list)
    ordered: list[str] | None = None


class StructureOut(BaseModel):
    odd_even: str = ""
    big_small: str = ""
    sum: int = 0
    span: int = 0
    zones: str = ""
    consecutive: int = 0


class PredictTicketOut(BaseModel):
    index: int
    numbers: dict[str, Any]
    score: float = 0.0
    structure: StructureOut = Field(default_factory=StructureOut)
    rationale: dict[str, Any] = Field(default_factory=dict)


class MarginalOut(BaseModel):
    ball: str
    items: list[dict[str, Any]] = Field(default_factory=list)


class PredictResponse(BaseModel):
    game: str
    game_name: str
    target_issue: str
    based_on: str
    engine: str
    strategy: str
    seed: int
    count: int
    tickets: list[PredictTicketOut] = Field(default_factory=list)
    marginals: list[MarginalOut] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    elapsed_ms: int = 0
    note: str = "概率模型输出，不构成中奖保证。"


class PredictHistoryItem(BaseModel):
    id: int
    game_code: str
    target_issue: str
    based_on: str
    engine: str
    strategy: str
    count: int
    seed: int
    created_at: datetime
    checked: bool = False
    hit_summary: dict[str, Any] | None = None
    tickets: list[dict[str, Any]] = Field(default_factory=list)


# ---------- 回测 ----------
class BacktestRequest(BaseModel):
    game: str = "ssq"
    periods: int = Field(default=200, ge=50, le=2000)
    engine: Literal["uniform", "frequency", "omission", "markov", "bayes", "gbdt", "ensemble"] = "ensemble"
    window: int = Field(default=100, ge=20, le=1000)
    topk: int = Field(default=6, ge=1, le=20)
    stride: int = Field(default=5, ge=1, le=20, description="树模型每隔多少期重训一次，1=每期重训")


class BacktestSide(BaseModel):
    label: str
    avg_hits: float = 0.0
    hit_rate_at_topk: float = 0.0
    log_loss: float = 0.0
    brier: float = 0.0
    avg_ticket_hits: float = 0.0


class BacktestResponse(BaseModel):
    game: str
    engine: str
    periods: int
    window: int
    topk: int
    stride: int = 1
    model: BacktestSide
    baseline: BacktestSide
    lift_avg_hits: float = 1.0
    lift_log_loss: float = 1.0
    verdict: str = ""
    hit_histogram: dict[str, int] = Field(default_factory=dict)
    per_issue: list[dict[str, Any]] = Field(default_factory=list)


# ---------- 随机性检验 ----------
class RandomnessOut(BaseModel):
    game: str
    draws: int
    chi_square: dict[str, Any] = Field(default_factory=dict)
    runs_test: dict[str, Any] = Field(default_factory=dict)
    autocorrelation: list[dict[str, Any]] = Field(default_factory=list)
    verdict: str = ""


# ---------- 同步 / 供应商 ----------
class SyncStatusOut(BaseModel):
    enabled: bool
    running: dict[str, bool] = Field(default_factory=dict)
    last_runs: list[dict[str, Any]] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    next_jobs: list[dict[str, Any]] = Field(default_factory=list)


class SyncRunOut(BaseModel):
    id: int
    game_code: str
    provider: str
    mode: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    status: str = ""
    error: str = ""


class ProviderOut(BaseModel):
    code: str
    name: str
    enabled: bool
    priority: int
    rate_limit: float
    last_ok_at: datetime | None = None
    last_error: str = ""
    supported_games: list[str] = Field(default_factory=list)
    healthy: bool = True


class ProviderPatch(BaseModel):
    enabled: bool | None = None
    priority: int | None = None


# ---------- 票夹 ----------
class TicketCreate(BaseModel):
    game_code: str
    issue: str = ""
    numbers: dict[str, Any]
    cost: float = 2.0
    note: str = ""


class TicketOut(BaseModel):
    id: int
    game_code: str
    issue: str
    numbers: dict[str, Any]
    cost: float
    note: str
    source: str
    created_at: datetime
    settled: bool
    prize: float
    hit_detail: dict[str, Any] | None = None


class TicketStatsOut(BaseModel):
    total_tickets: int = 0
    total_cost: float = 0.0
    total_prize: float = 0.0
    roi: float = 0.0
    settled: int = 0
    pending: int = 0
    by_game: list[dict[str, Any]] = Field(default_factory=list)

# ---------- 账号 / 会话 ----------
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str = ""
    role: str = "admin"
    enabled: bool = True
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None


class LoginOut(BaseModel):
    ok: bool = True
    user: UserOut | None = None
    csrf: str = "1"


class MeOut(BaseModel):
    authenticated: bool = False
    user: UserOut | None = None
    csrf: str = ""
    ai_enabled: bool = True


class SessionOut(BaseModel):
    id: int
    created_at: datetime | None = None
    expires_at: datetime | None = None
    last_seen_at: datetime | None = None
    ip: str = ""
    user_agent: str = ""
    current: bool = False


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


# ---------- 审计 ----------
class AuditOut(BaseModel):
    id: int
    at: datetime | None = None
    actor: str = ""
    action: str = ""
    target: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    ip: str = ""
    status: str = "ok"


# ---------- AI 供应商 ----------
class AiProviderSubmit(BaseModel):
    """用户自助提交：把自己的 AI 凭据交上来。"""

    name: str = Field(min_length=1, max_length=64)
    vendor: str = "openai"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    submitter_name: str = Field(default="", max_length=64)
    submitter_contact: str = Field(default="", max_length=128)
    note: str = Field(default="", max_length=500)


class AiProviderAdmin(BaseModel):
    """后台维护：可以改状态、改模型、换 key。"""

    name: str | None = None
    vendor: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    enabled: bool | None = None
    status: str | None = None
    review_note: str | None = None
    submitter_name: str | None = None
    submitter_contact: str | None = None
    note: str | None = None


class AiProviderOut(BaseModel):
    id: int
    name: str
    vendor: str = "openai"
    base_url: str = ""
    model: str = ""
    api_key_set: bool = False
    api_key_hint: str = ""
    temperature: float = 0.4
    max_tokens: int = 1200
    enabled: bool = True
    status: str = "pending"
    submitter_name: str = ""
    submitter_contact: str = ""
    note: str = ""
    review_note: str = ""
    created_at: datetime | None = None
    reviewed_at: datetime | None = None
    last_ok_at: datetime | None = None
    last_error: str = ""
    calls: int = 0
    healthy: bool = True


class AiAnalyzeIn(BaseModel):
    game: str = "ssq"
    count: int = Field(default=5, ge=1, le=20)
    engine: str = "ensemble"
    strategy: str = "balanced"
    window: int = Field(default=100, ge=10, le=2000)
    provider_id: int | None = None
    question: str = ""


class AiAnalysisOut(BaseModel):
    id: int
    game_code: str
    target_issue: str = ""
    provider_name: str = ""
    model: str = ""
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    answer: str = ""
    error: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class InsightOut(BaseModel):
    game: str
    target_issue: str = ""
    based_on: str = ""
    draws: int = 0
    summary: str = ""
    hot: list[dict[str, Any]] = Field(default_factory=list)
    cold: list[dict[str, Any]] = Field(default_factory=list)
    omission_top: list[dict[str, Any]] = Field(default_factory=list)
    structure: dict[str, Any] = Field(default_factory=dict)
    randomness: str = ""
    caveat: str = "概率模型输出，不构成中奖保证。"


# ---------- 管理后台 ----------
class AdminOverviewOut(BaseModel):
    draws: int = 0
    tickets: int = 0
    predictions: int = 0
    sync_runs: int = 0
    ai_providers: int = 0
    ai_pending: int = 0
    ai_analyses: int = 0
    users: int = 0
    sessions: int = 0
    audit_logs: int = 0
    read_only: bool = False
    sync_enabled: bool = True
    ai_enabled: bool = True
    docs_enabled: bool = True
    cookie_secure: bool = False
    admin_token_set: bool = False


class UserAdminCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(default="", max_length=64)
    role: str = "admin"


class UserAdminPatch(BaseModel):
    display_name: str | None = None
    role: str | None = None
    enabled: bool | None = None
    password: str | None = None

