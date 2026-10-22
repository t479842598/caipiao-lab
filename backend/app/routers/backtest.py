from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..engine.backtest import run_backtest
from ..games import GAMES
from ..schemas import BacktestRequest, BacktestResponse, RandomnessOut

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("", response_model=BacktestResponse)
def backtest(req: BacktestRequest, db: Session = Depends(get_db)) -> BacktestResponse:
    if req.game not in GAMES:
        raise HTTPException(404, f"未知彩种 {req.game}")
    try:
        result = run_backtest(db, game=req.game, periods=req.periods, engine=req.engine,
                              window=req.window, topk=req.topk, stride=req.stride)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return BacktestResponse(**result)
