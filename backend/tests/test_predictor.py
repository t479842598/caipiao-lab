from __future__ import annotations

from app.engine.predictor import predict, serialize_run
from app.models import PredictionRun


def test_predict_returns_requested_count(session) -> None:
    out = predict(session, "ssq", count=7, engine="frequency", window=50, seed=1)
    assert len(out["tickets"]) == 7
    assert out["game"] == "ssq"
    assert out["count"] == 7


def test_predict_target_issue_follows_latest(session) -> None:
    out = predict(session, "ssq", count=1, engine="frequency", window=50, seed=1)
    assert out["target_issue"] != out["based_on"]
    assert out["target_issue"] > out["based_on"]


def test_predict_is_deterministic_with_seed(session) -> None:
    a = predict(session, "qlc", count=3, engine="frequency", window=50, seed=999, persist=False)
    b = predict(session, "qlc", count=3, engine="frequency", window=50, seed=999, persist=False)
    assert [t["numbers"] for t in a["tickets"]] == [t["numbers"] for t in b["tickets"]]


def test_predict_persists_run_and_tickets(session) -> None:
    out = predict(session, "ssq", count=2, engine="bayes", window=50, seed=11)
    assert out["run_id"] is not None
    run = session.get(PredictionRun, out["run_id"])
    assert run is not None
    reloaded = serialize_run(run)
    assert len(reloaded["tickets"]) == 2
    assert reloaded["engine"] == "bayes"


def test_predict_3d_ticket_ordered(session) -> None:
    out = predict(session, "3d", count=2, engine="frequency", window=50, seed=4)
    for t in out["tickets"]:
        assert len(t["numbers"]["ordered"]) == 3


def test_predict_marginals_sum_to_one(session) -> None:
    out = predict(session, "ssq", count=1, engine="frequency", window=50, seed=1)
    for block in out["marginals"]:
        total = sum(i["p"] for i in block["items"])
        assert abs(total - 1.0) < 1e-3


def test_predict_no_future_leak(session) -> None:
    """预测只能基于最新一期之前的数据：based_on 必须等于库里最新期号。"""
    out = predict(session, "ssq", count=1, engine="frequency", window=50, seed=2, persist=False)
    from app.models import Draw
    from sqlalchemy import select

    latest = session.execute(
        select(Draw.issue).where(Draw.game_code == "ssq").order_by(Draw.draw_date.desc(), Draw.issue.desc()).limit(1)
    ).scalar_one()
    assert out["based_on"] == latest
