from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..engine.dataset import load_ball_data
from ..engine.stats import (
    distribution_stats,
    frequency_table,
    omission_table,
    randomness_report,
    trend_matrix,
)
from ..games import GAMES
from ..schemas import DistributionOut, FrequencyOut, OmissionOut, RandomnessOut, TrendOut

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _check(game: str, ball: str) -> None:
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    if ball not in ("red", "blue"):
        raise HTTPException(400, "ball 只能是 red 或 blue")


@router.get("/{game}/frequency", response_model=FrequencyOut)
def frequency(
    game: str,
    ball: str = Query("red"),
    window: int = Query(100, ge=0, le=5000),
    db: Session = Depends(get_db),
) -> FrequencyOut:
    _check(game, ball)
    data = load_ball_data(db, game, ball)
    return FrequencyOut(game=game, ball=ball, window=window, total_draws=data.n,
                        items=frequency_table(data, window))


@router.get("/{game}/omission", response_model=OmissionOut)
def omission(
    game: str,
    ball: str = Query("red"),
    limit: int = Query(0, ge=0, le=200),
    db: Session = Depends(get_db),
) -> OmissionOut:
    _check(game, ball)
    data = load_ball_data(db, game, ball)
    return OmissionOut(game=game, ball=ball, items=omission_table(data, limit or None))


@router.get("/{game}/trend", response_model=TrendOut)
def trend(
    game: str,
    ball: str = Query("red"),
    periods: int = Query(30, ge=5, le=200),
    db: Session = Depends(get_db),
) -> TrendOut:
    _check(game, ball)
    data = load_ball_data(db, game, ball)
    return TrendOut(**trend_matrix(data, periods))


@router.get("/{game}/distribution", response_model=DistributionOut)
def distribution(
    game: str,
    window: int = Query(200, ge=10, le=5000),
    db: Session = Depends(get_db),
) -> DistributionOut:
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    data = load_ball_data(db, game, "red")
    return DistributionOut(**distribution_stats(data, window))


@router.get("/{game}/randomness", response_model=RandomnessOut)
def randomness(game: str, db: Session = Depends(get_db)) -> RandomnessOut:
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    data = load_ball_data(db, game, "red")
    return RandomnessOut(**randomness_report(data))
