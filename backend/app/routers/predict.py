from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..engine.predictor import predict, serialize_run
from ..games import GAMES
from ..models import PredictionRun
from ..schemas import PredictHistoryItem, PredictRequest, PredictResponse

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("", response_model=PredictResponse)
def create_prediction(req: PredictRequest, db: Session = Depends(get_db)) -> PredictResponse:
    if req.game not in GAMES:
        raise HTTPException(404, f"未知彩种 {req.game}")
    if req.count > settings.predict_max_count:
        raise HTTPException(400, f"最多一次生成 {settings.predict_max_count} 注")
    try:
        payload = predict(
            db,
            game=req.game,
            count=req.count,
            engine=req.engine,
            strategy=req.strategy,
            window=req.window,
            seed=req.seed,
            pick=req.pick,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return PredictResponse(**payload)


@router.get("/{game}/next", response_model=PredictResponse)
def quick_predict(
    game: str,
    count: int = Query(5, ge=1, le=100),
    engine: str = Query("ensemble"),
    strategy: str = Query("balanced"),
    window: int = Query(100, ge=10, le=2000),
    db: Session = Depends(get_db),
) -> PredictResponse:
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    payload = predict(db, game=game, count=count, engine=engine, strategy=strategy, window=window)
    return PredictResponse(**payload)


@router.get("/history/{game}", response_model=list[PredictHistoryItem])
def history(
    game: str,
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[PredictHistoryItem]:
    if game not in GAMES:
        raise HTTPException(404, f"未知彩种 {game}")
    runs = db.execute(
        select(PredictionRun).where(PredictionRun.game_code == game)
        .order_by(PredictionRun.id.desc()).limit(limit)
    ).scalars().all()
    out = []
    for run in runs:
        item = serialize_run(run)
        out.append(PredictHistoryItem(**item))
    return out


@router.get("/run/{run_id}", response_model=PredictHistoryItem)
def get_run(run_id: int, db: Session = Depends(get_db)) -> PredictHistoryItem:
    run = db.get(PredictionRun, run_id)
    if run is None:
        raise HTTPException(404, "记录不存在")
    return PredictHistoryItem(**serialize_run(run))
