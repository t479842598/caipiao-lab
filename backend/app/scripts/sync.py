"""命令行同步入口：python -m app.scripts.sync [--game all|ssq] [--mode full|incremental]"""

from __future__ import annotations

import argparse
import asyncio
import sys

from ..db import init_db, session_scope
from ..engine.settle import settle_pending
from ..games import GAME_ORDER
from ..jobs.sync_job import sync_service


async def main() -> int:
    parser = argparse.ArgumentParser(description="同步福彩开奖数据")
    parser.add_argument("--game", default="all", help="all 或具体彩种 ssq/3d/qlc/kl8")
    parser.add_argument("--mode", default="incremental", choices=["incremental", "full", "backfill"])
    args = parser.parse_args()

    init_db()
    games = list(GAME_ORDER) if args.game == "all" else [args.game]
    failed = 0
    for game in games:
        print(f"[sync] {game} mode={args.mode} ...", flush=True)
        result = await sync_service.sync_game(game, mode=args.mode)
        print(f"  -> {result}", flush=True)
        if result.get("status") != "success":
            failed += 1
    with session_scope() as session:
        print("[settle]", settle_pending(session), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
