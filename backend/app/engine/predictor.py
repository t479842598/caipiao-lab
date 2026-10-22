"""预测编排：加载数据 → 脱敏截断 → 算概率 → 出票 → 落库。"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..games import get_game, next_issue_guess
from ..models import Draw, ModelMetric, PredictionRun, PredictionTicket
from .dataset import load_ball_data
from .generator import build_tickets
from .models import compute_marginals


def _target_issue(session: Session, game: str) -> tuple[str, str]:
    spec = get_game(game)
    row = session.execute(
        select(Draw.issue, Draw.draw_date).where(Draw.game_code == game).order_by(Draw.draw_date.desc()).limit(1)
    ).first()
    if row is None:
        return spec.first_issue, ""
    last_issue, last_date = row
    return next_issue_guess(last_issue, last_date.year if last_date else None, datetime.now().year), last_issue


def predict(
    session: Session,
    game: str,
    count: int = 5,
    engine: str = "ensemble",
    strategy: str = "balanced",
    window: int = 100,
    seed: int | None = None,
    pick: int | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    started = time.monotonic()
    spec = get_game(game)
    target_issue, based_on = _target_issue(session, game)
    actual_seed = seed if seed is not None else int(time.time() * 1000) % 2_147_483_647

    red_data = load_ball_data(session, game, "red")
    if red_data.n == 0:
        raise ValueError(f"{spec.name} 还没有任何开奖数据，请先同步")
    red_probs, weights = compute_marginals(red_data, engine=engine, window=window)
    tickets = build_tickets(red_data, red_probs, spec, count=count, strategy=strategy,
                            seed=actual_seed, pick=pick)

    marginals = [
        {
            "ball": "red",
            "items": [
                {"n": n, "p": round(float(red_probs[i]), 5)}
                for i, n in enumerate(red_data.domain)
            ],
        }
    ]
    if spec.blue is not None and engine in ("ensemble", "frequency", "bayes", "gbdt"):
        blue_data = load_ball_data(session, game, "blue")
        if blue_data.n:
            blue_probs, _ = compute_marginals(blue_data, engine="frequency", window=window)
            marginals.append(
                {
                    "ball": "blue",
                    "items": [{"n": n, "p": round(float(blue_probs[i]), 5)} for i, n in enumerate(blue_data.domain)],
                }
            )

    elapsed = int((time.monotonic() - started) * 1000)
    payload = {
        "game": game,
        "game_name": spec.name,
        "target_issue": target_issue,
        "based_on": based_on,
        "engine": engine,
        "strategy": strategy,
        "seed": actual_seed,
        "count": len(tickets),
        "tickets": tickets,
        "marginals": marginals,
        "weights": weights,
        "elapsed_ms": elapsed,
        "note": "概率模型输出，不构成中奖保证。",
    }

    if persist:
        run = PredictionRun(
            game_code=game,
            target_issue=target_issue,
            based_on=based_on,
            engine=engine,
            strategy=strategy,
            count=len(tickets),
            params={"window": window, "pick": pick},
            seed=actual_seed,
        )
        session.add(run)
        session.flush()
        for ticket in tickets:
            session.add(
                PredictionTicket(
                    run_id=run.id,
                    idx=ticket["index"],
                    numbers=ticket["numbers"],
                    score=float(ticket["score"]),
                    rationale={**ticket["rationale"], "structure": ticket["structure"]},
                )
            )
        safe = red_probs + 1e-12
        entropy = float(-(red_probs * np.log(safe)).sum())
        baseline = float(np.log(len(red_probs)))
        session.add(
            ModelMetric(
                run_id=run.id,
                metric="marginal_entropy",
                value=entropy,
                baseline_value=baseline,
                lift=round(entropy / baseline, 6) if baseline else 1.0,
            )
        )
        session.commit()
        payload["run_id"] = run.id

    return payload


def serialize_run(run: PredictionRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "game_code": run.game_code,
        "target_issue": run.target_issue,
        "based_on": run.based_on,
        "engine": run.engine,
        "strategy": run.strategy,
        "count": run.count,
        "seed": run.seed,
        "created_at": run.created_at,
        "checked": run.checked,
        "hit_summary": run.hit_summary,
        "tickets": [
            {"index": t.idx, "numbers": t.numbers, "score": t.score, "rationale": t.rationale,
             "hit_detail": t.hit_detail}
            for t in sorted(run.tickets_rel, key=lambda x: x.idx)
        ],
    }


save_run = serialize_run
