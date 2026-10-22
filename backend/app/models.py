"""ORM 模型。号码统一用 JSON 存字符串数组，展开表供统计查询走索引。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    ball_spec: Mapped[dict] = mapped_column(JSON, default=dict)
    first_issue: Mapped[str] = mapped_column(String(16), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Draw(Base):
    __tablename__ = "draws"
    __table_args__ = (
        UniqueConstraint("game_code", "issue", name="uq_draws_game_issue"),
        Index("idx_draws_game_date", "game_code", "draw_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_code: Mapped[str] = mapped_column(String(16), index=True)
    issue: Mapped[str] = mapped_column(String(16), index=True)
    draw_date: Mapped[date] = mapped_column(Date, index=True)
    week: Mapped[str] = mapped_column(String(8), default="")
    numbers: Mapped[dict] = mapped_column(JSON, default=dict)  # {"red": [...], "blue": [...]}
    ordered: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 3D 位序
    sales: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    pool_money: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(32), default="")
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    numbers_rel: Mapped[list["DrawNumber"]] = relationship(
        back_populates="draw", cascade="all, delete-orphan", lazy="selectin"
    )
    prizes: Mapped[list["PrizeGrade"]] = relationship(
        back_populates="draw", cascade="all, delete-orphan", lazy="selectin"
    )


class DrawNumber(Base):
    __tablename__ = "draw_numbers"
    __table_args__ = (
        Index("idx_dn_lookup", "game_code", "ball", "value", "draw_id"),
        Index("idx_dn_draw", "draw_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draw_id: Mapped[int] = mapped_column(ForeignKey("draws.id", ondelete="CASCADE"))
    game_code: Mapped[str] = mapped_column(String(16), index=True)
    ball: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(Integer, default=0)
    value: Mapped[int] = mapped_column(Integer)
    is_blue: Mapped[bool] = mapped_column(Boolean, default=False)

    draw: Mapped[Draw] = relationship(back_populates="numbers_rel")


class PrizeGrade(Base):
    __tablename__ = "prize_grades"
    __table_args__ = (Index("idx_pg_draw", "draw_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draw_id: Mapped[int] = mapped_column(ForeignKey("draws.id", ondelete="CASCADE"))
    # 快乐8 的奖级是 "x10z10" 这类字符串，因此统一用文本保存
    type: Mapped[str] = mapped_column(String(24), default="")
    type_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type_money: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)

    draw: Mapped[Draw] = relationship(back_populates="prizes")


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_code: Mapped[str] = mapped_column(String(16), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="")
    mode: Mapped[str] = mapped_column(String(16), default="incremental")  # full / incremental
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="running")
    error: Mapped[str] = mapped_column(Text, default="")


class Provider(Base):
    __tablename__ = "providers"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    rate_limit: Mapped[float] = mapped_column(Float, default=1.0)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_code: Mapped[str] = mapped_column(String(16), index=True)
    target_issue: Mapped[str] = mapped_column(String(16))
    based_on: Mapped[str] = mapped_column(String(16), default="")
    engine: Mapped[str] = mapped_column(String(32), default="ensemble")
    strategy: Mapped[str] = mapped_column(String(32), default="balanced")
    count: Mapped[int] = mapped_column(Integer, default=5)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    hit_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    tickets_rel: Mapped[list["PredictionTicket"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )
    metrics: Mapped[list["ModelMetric"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class PredictionTicket(Base):
    __tablename__ = "prediction_tickets"
    __table_args__ = (Index("idx_pt_run", "run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("prediction_runs.id", ondelete="CASCADE"))
    idx: Mapped[int] = mapped_column(Integer, default=1)
    numbers: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[dict] = mapped_column(JSON, default=dict)
    hit_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    run: Mapped[PredictionRun] = relationship(back_populates="tickets_rel")


class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("prediction_runs.id", ondelete="CASCADE"))
    metric: Mapped[str] = mapped_column(String(48))
    value: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_value: Mapped[float] = mapped_column(Float, default=0.0)
    lift: Mapped[float] = mapped_column(Float, default=1.0)

    run: Mapped[PredictionRun] = relationship(back_populates="metrics")


class Ticket(Base):
    """票夹：用户自选号码记账，开奖后自动兑奖。"""

    __tablename__ = "tickets"
    __table_args__ = (Index("idx_tickets_game_issue", "game_code", "issue"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_code: Mapped[str] = mapped_column(String(16))
    issue: Mapped[str] = mapped_column(String(16), default="")
    numbers: Mapped[dict] = mapped_column(JSON, default=dict)
    cost: Mapped[float] = mapped_column(Numeric(10, 2), default=2.0)
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(16), default="manual")
    # 归属：登录用户 "u:<id>"，游客设备 "d:<device_id>"。空串 = 无主（老数据）
    owner_key: Mapped[str] = mapped_column(String(48), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    settled: Mapped[bool] = mapped_column(Boolean, default=False)
    prize: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    hit_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)

# --------------------------------------------------------------------------- #
# 账号 / 会话 / 审计
# --------------------------------------------------------------------------- #
class User(Base):
    """管理员账号。前台游客无需登录，只有后台写操作需要管理员身份。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(16), default="admin")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[str] = mapped_column(String(64), default="")
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserSession(Base):
    """登录会话。库里只存 token 的 sha256，泄露库也拿不到可用 cookie。"""

    __tablename__ = "user_sessions"
    __table_args__ = (Index("idx_sessions_user", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(200), default="")
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    """后台操作审计：谁在什么时候改了什么。"""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("idx_audit_at", "at"), Index("idx_audit_action", "action"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    actor: Mapped[str] = mapped_column(String(64), default="anonymous")
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
    ua: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(16), default="ok")


# --------------------------------------------------------------------------- #
# AI 供应商（用户自助登记 → 管理员审核 → 用来做 AI 分析）
# --------------------------------------------------------------------------- #
class AiProvider(Base):
    """AI 供应商配置。api_key 用 Fernet 加密后落库，接口只回掩码。"""

    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    vendor: Mapped[str] = mapped_column(String(32), default="openai")  # openai/azure/deepseek/ollama/custom
    base_url: Mapped[str] = mapped_column(String(255), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    api_key_enc: Mapped[str] = mapped_column(Text, default="")
    api_key_hint: Mapped[str] = mapped_column(String(32), default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.4)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1200)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # pending 待审核 / approved 已启用 / rejected 已驳回
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # 提交者信息（用户自己填的，后台留档）
    submitter_name: Mapped[str] = mapped_column(String(64), default="")
    submitter_contact: Mapped[str] = mapped_column(String(128), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    review_note: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    calls: Mapped[int] = mapped_column(Integer, default=0)


class AiAnalysis(Base):
    """一次 AI 分析记录：喂进去的预测凭据 + 模型返回的文本。"""

    __tablename__ = "ai_analyses"
    __table_args__ = (Index("idx_ai_analysis_game", "game_code", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_code: Mapped[str] = mapped_column(String(16))
    target_issue: Mapped[str] = mapped_column(String(16), default="")
    provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_name: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    answer: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(64), default="anonymous")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
