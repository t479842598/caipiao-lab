import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type Draw, type Game } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { useGame } from "../lib/store";
import { Balls } from "../components/Balls";
import { Badge, Button, Card, CardTitle, Empty, ErrorNote, NumberField, Spinner, TextField, cx } from "../components/ui";
import { dateShort, gameName, money } from "../lib/format";

export default function History({ games }: { games: Game[] }) {
  const { game } = useGame();
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(30);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [issueQuery, setIssueQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(params.get("issue"));

  const meta = games.find((g) => g.code === game);

  const list = useAsync(
    () =>
      api.draws(game, {
        page,
        page_size: pageSize,
        start_date: start || undefined,
        end_date: end || undefined,
        issue: issueQuery.trim() || undefined,
      }),
    [game, page, pageSize, start, end, issueQuery],
  );

  useEffect(() => {
    setPage(1);
    setSelected(params.get("issue"));
  }, [game, start, end, issueQuery, pageSize]);

  const detail = useAsync(
    () => (selected ? api.draw(game, selected) : Promise.resolve(null)),
    [game, selected],
    !!selected,
  );

  const totalPages = useMemo(() => {
    if (!list.data) return 1;
    return Math.max(1, Math.ceil(list.data.total / list.data.page_size));
  }, [list.data]);

  const jump = (issue: string) => {
    setSelected(issue);
    setParams({ issue });
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_420px]">
      <Card>
        <CardTitle
          title={gameName(game) + " 历史开奖"}
          sub={meta ? "共 " + meta.draw_count + " 期，最早 " + meta.first_issue : undefined}
          right={
            list.data ? (
              <Badge tone="neutral">{"共 " + list.data.total + " 条"}</Badge>
            ) : null
          }
        />

        <div className="mb-3 flex flex-wrap items-center gap-2">
          <TextField label="期号" value={issueQuery} onChange={setIssueQuery} placeholder="121" width="w-24" />
          <TextField label="起" value={start} onChange={setStart} placeholder="2003-02-23" width="w-28" />
          <TextField label="止" value={end} onChange={setEnd} placeholder="2026-10-20" width="w-28" />
          <NumberField label="每页" value={pageSize} onChange={setPageSize} min={10} max={200} width="w-16" />
          <Button variant="subtle" onClick={() => { setIssueQuery(""); setStart(""); setEnd(""); setPage(1); }}>
            清空筛选
          </Button>
          <a
            href={api.exportUrl(game, { start_date: start || undefined, end_date: end || undefined })}
            className="rounded-lg border border-ink-700 px-3 py-1.5 text-xs text-fog-300 transition hover:border-jade/60 hover:text-jade"
            download
          >
            导出 CSV
          </a>
          {issueQuery.trim() && (
            <span className="text-[11px] text-fog-400">
              正在按期号「{issueQuery.trim()}」筛选
            </span>
          )}
        </div>

        {list.loading ? (
          <Spinner />
        ) : list.error ? (
          <ErrorNote message={list.error} onRetry={list.reload} />
        ) : !list.data || list.data.items.length === 0 ? (
          <Empty>没有匹配的开奖记录</Empty>
        ) : (
          <>
            <div className="flex flex-col gap-2 md:hidden">
              {list.data.items.map((d) => (
                <button
                  key={d.id}
                  onClick={() => jump(d.issue)}
                  className={
                    "rounded-xl border px-3 py-2 text-left transition-colors " +
                    (d.issue === selected
                      ? "border-jade/50 bg-jade/5"
                      : "border-ink-700/70 bg-ink-900/40 hover:border-jade/30")
                  }
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="num text-xs text-fog-200">{d.issue}</span>
                    <span className="num text-[11px] text-fog-400">
                      {dateShort(d.draw_date) + (d.week ? " 周" + d.week : "")}
                    </span>
                  </div>
                  <div className="mt-1.5">
                    <Balls red={d.numbers.red} blue={d.numbers.blue} ordered={d.ordered} size="sm" max={8} />
                  </div>
                  <div className="mt-1 flex justify-between text-[10px] text-ink-500">
                    <span className="num">销量 {money(d.sales)}</span>
                    <span className="num">奖池 {money(d.pool_money)}</span>
                  </div>
                </button>
              ))}
            </div>
            <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-fog-400">
                  <th className="py-2 pr-3 font-normal">期号</th>
                  <th className="py-2 pr-3 font-normal">开奖日</th>
                  <th className="py-2 pr-3 font-normal">号码</th>
                  <th className="py-2 pr-3 text-right font-normal">销量</th>
                  <th className="py-2 text-right font-normal">奖池</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((d) => (
                  <tr
                    key={d.id}
                    onClick={() => jump(d.issue)}
                    className={cx(
                      "cursor-pointer border-t border-ink-700/60 hover:bg-ink-800/50",
                      d.issue === selected && "bg-ink-800/70",
                    )}
                  >
                    <td className="num py-2 pr-3 text-fog-200">{d.issue}</td>
                    <td className="py-2 pr-3 text-fog-400">{dateShort(d.draw_date) + (d.week ? " 周" + d.week : "")}</td>
                    <td className="py-2 pr-3">
                      <Balls red={d.numbers.red} blue={d.numbers.blue} ordered={d.ordered} size="sm" max={8} />
                    </td>
                    <td className="num py-2 pr-3 text-right text-fog-400">{money(d.sales)}</td>
                    <td className="num py-2 text-right text-fog-400">{money(d.pool_money)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </>
        )}

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-fog-400">
          <span className="num">第 {page} / {totalPages} 页</span>
          <div className="flex flex-wrap gap-2">
            <Button disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>上一页</Button>
            <Button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>下一页</Button>
            <Button onClick={() => setPage(1)}>首页</Button>
            <Button onClick={() => setPage(totalPages)}>末页</Button>
          </div>
        </div>
      </Card>

      <Card className="h-fit">
        <CardTitle title="期次详情" sub={selected ? "期号 " + selected : "点击左侧任意一行查看"} />
        {!selected ? (
          <Empty>未选择期次</Empty>
        ) : detail.loading ? (
          <Spinner />
        ) : detail.error ? (
          <ErrorNote message={detail.error} onRetry={detail.reload} />
        ) : !detail.data ? (
          <Empty>无数据</Empty>
        ) : (
          <DrawDetail draw={detail.data} />
        )}
      </Card>
    </div>
  );
}

function DrawDetail({ draw }: { draw: Draw }) {
  return (
    <div className="flex flex-col gap-3 text-xs">
      <div>
        <div className="num text-lg font-semibold text-fog-200">{draw.issue}</div>
        <div className="text-[11px] text-fog-400">
          {draw.draw_date + (draw.week ? " 周" + draw.week : "") + " · 来源 " + (draw.source || "—")}
        </div>
      </div>
      <div className="rounded-xl border border-ink-700/70 bg-ink-900/40 p-3">
        <Balls red={draw.numbers.red} blue={draw.numbers.blue} ordered={draw.ordered} max={20} />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-ink-700/70 px-2.5 py-2">
          <div className="text-[10px] uppercase tracking-wider text-fog-400">销量</div>
          <div className="num text-fog-200">{money(draw.sales)}</div>
        </div>
        <div className="rounded-lg border border-ink-700/70 px-2.5 py-2">
          <div className="text-[10px] uppercase tracking-wider text-fog-400">奖池</div>
          <div className="num text-fog-200">{money(draw.pool_money)}</div>
        </div>
      </div>
      {draw.prizes.length > 0 ? (
        <div>
          <div className="mb-1 text-[11px] uppercase tracking-wider text-fog-400">奖级明细</div>
          <table className="w-full text-[11px]">
            <tbody>
              {draw.prizes.map((p, i) => (
                <tr key={i} className="border-t border-ink-700/60">
                  <td className="py-1.5 pr-2 text-fog-300">{p.type}</td>
                  <td className="num py-1.5 pr-2 text-right text-fog-400">{p.type_num ?? "—"} 注</td>
                  <td className="num py-1.5 text-right text-fog-200">{p.type_money ? money(p.type_money) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-[11px] text-fog-400">{draw.content || "该彩种官方未公布奖级明细"}</div>
      )}
    </div>
  );
}
