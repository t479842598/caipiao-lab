"""清理脏奖级：删除「整期所有奖级都是 0 注 0 元」的记录。

背景：早期官方源对 3D 返回 7 个空壳奖级（typenum / typemoney 都是空串），
`_to_int("")` 返回 None，写进 `Numeric` 列后变成 0，导致期次详情页
显示一堆「0 注 / —」的假奖级。解析层已修复（空奖级不再入库），
本脚本负责把历史脏数据清掉。

**关键区分**：单个奖级为 0 是真实情况，不能删——
  - 双色球一等奖空缺时 `type_num=0, type_money=0`（奖金滚入下期）
  - 快乐8「选十中十」无人中时 `x10z10 / 0 / 0`
  - 七乐彩同样存在头奖空缺
只有**一整期的所有奖级都是 0** 才说明该期数据整体缺失，属于脏数据。

用法：
    python -m app.scripts.clean_zero_prizes              # 只统计，不改数据（dry-run）
    python -m app.scripts.clean_zero_prizes --apply      # 真正删除
    python -m app.scripts.clean_zero_prizes --apply --game 3d   # 只清某个彩种
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import delete, func, select

from ..db import init_db, session_scope
from ..models import Draw, PrizeGrade


def _find_dirty_draw_ids(session, game: str | None) -> list[int]:
    """找出「整期奖级全为 0/0」的 draw.id。

    用 GROUP BY + HAVING 一次算完，避免逐期查询。
    """
    stmt = (
        select(Draw.id)
        .join(PrizeGrade, PrizeGrade.draw_id == Draw.id)
        .group_by(Draw.id)
        .having(func.sum(func.coalesce(PrizeGrade.type_num, 0)) == 0)
        .having(func.sum(func.coalesce(PrizeGrade.type_money, 0)) == 0)
    )
    if game:
        stmt = stmt.where(Draw.game_code == game)
    return list(session.execute(stmt).scalars().all())


def main() -> int:
    parser = argparse.ArgumentParser(description="清理整期全为 0 的脏奖级")
    parser.add_argument("--apply", action="store_true", help="真正执行删除（默认只统计）")
    parser.add_argument("--game", default=None, help="只处理指定彩种 ssq/3d/qlc/kl8")
    args = parser.parse_args()

    init_db()

    with session_scope() as session:
        dirty_ids = _find_dirty_draw_ids(session, args.game)

        if not dirty_ids:
            print("[clean] 没有「整期奖级全为 0」的脏数据")
            return 0

        # 按彩种统计
        rows = session.execute(
            select(Draw.game_code, func.count(Draw.id))
            .where(Draw.id.in_(dirty_ids))
            .group_by(Draw.game_code)
        ).all()

        print("[clean] 整期奖级全为 0 的期数（数据缺失，非头奖空缺）：")
        total_draws = 0
        for game, n in sorted(rows, key=lambda r: -r[1]):
            print(f"  {game:>4}: {n:>5} 期")
            total_draws += n
        print(f"  合计: {total_draws} 期")

        prize_count = session.execute(
            select(func.count(PrizeGrade.id)).where(PrizeGrade.draw_id.in_(dirty_ids))
        ).scalar_one()
        print(f"  涉及奖级记录: {prize_count} 条")

        if not args.apply:
            print("\n[clean] dry-run，未改动数据。加 --apply 执行删除。")
            print("        注意：单个奖级为 0 是正常情况（头奖空缺），本脚本只删整期全 0 的。")
            return 0

        # 分批删除，避免 SQLite 变量上限（默认 999）
        deleted = 0
        batch = 500
        for i in range(0, len(dirty_ids), batch):
            chunk = dirty_ids[i : i + batch]
            result = session.execute(delete(PrizeGrade).where(PrizeGrade.draw_id.in_(chunk)))
            deleted += result.rowcount or 0
        session.commit()
        print(f"\n[clean] 已删除 {deleted} 条脏奖级记录（涉及 {len(dirty_ids)} 期）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
