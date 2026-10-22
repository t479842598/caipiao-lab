import { useNavigate } from "react-router-dom";
import { api, type Game } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { useGame } from "../lib/store";
import { Balls } from "../components/Balls";
import { Badge, Button, Card, CardTitle, Empty, ErrorNote, Spinner } from "../components/ui";
import { dateShort, gameName, money, weekdayLabel } from "../lib/format";

export default function Overview({ games }: { games: Game[] }) {
  const { game, setGame } = useGame();
  const nav = useNavigate();
  const recent = useAsync(() => api.draws(game, { page: 1, page_size: 8 }), [game]);

  const totalDraws = games.reduce((sum, g) => sum + g.draw_count, 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 2xl:gap-4">
        <div className="card p-4">
          <div className="text-[11px] uppercase tracking-wider text-fog-400">收录期数</div>
          <div className="num mt-1 text-2xl font-semibold text-fog-200">{totalDraws.toLocaleString("zh-CN")}</div>
          <div className="mt-0.5 text-[11px] text-fog-400">四大彩种全量历史</div>
        </div>
        <div className="card p-4">
          <div className="text-[11px] uppercase tracking-wider text-fog-400">彩种数</div>
          <div className="num mt-1 text-2xl font-semibold text-fog-200">{games.length}</div>
          <div className="mt-0.5 text-[11px] text-fog-400">双色球 / 3D / 七乐彩 / 快乐8</div>
        </div>
        <div className="card p-4">
          <div className="text-[11px] uppercase tracking-wider text-fog-400">数据源</div>
          <div className="mt-1 text-2xl font-semibold text-jade">官方</div>
          <div className="mt-0.5 text-[11px] text-fog-400">中彩网公开接口 + 备用源</div>
        </div>
        <div className="card p-4">
          <div className="text-[11px] uppercase tracking-wider text-fog-400">自动同步</div>
          <div className="mt-1 text-2xl font-semibold text-fog-200">开奖后 12 分钟</div>
          <div className="mt-0.5 text-[11px] text-fog-400">按各彩种开奖日历定时拉取</div>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 2xl:gap-4">
        {games.map((g) => {
          const nums = g.latest_numbers ?? {};
          const active = g.code === game;
          return (
            <button
              key={g.code}
              onClick={() => {
                setGame(g.code);
                nav("/history");
              }}
              className={
                "card p-4 text-left transition-colors hover:border-jade/40 " + (active ? "border-jade/50" : "")
              }
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-fog-200">{gameName(g.code)}</span>
                <Badge tone={active ? "good" : "neutral"}>{"共 " + g.draw_count + " 期"}</Badge>
              </div>
              <div className="mt-2 flex items-center gap-2 text-[11px] text-fog-400">
                <span className="num">{g.latest_issue ?? "—"}</span>
                <span>{g.latest_date ?? ""}</span>
              </div>
              <div className="mt-2 min-h-[28px]">
                {nums.red || nums.blue ? (
                  <Balls red={nums.red} blue={nums.blue} ordered={null} size="sm" max={8} />
                ) : (
                  <span className="text-xs text-fog-400">暂无开奖</span>
                )}
              </div>
              <div className="mt-2 flex items-center justify-between text-[11px] text-fog-400">
                <span>{weekdayLabel(g.draw_weekdays) + " " + g.draw_time}</span>
                <span className="num">下期 {g.next_issue ?? "—"}</span>
              </div>
            </button>
          );
        })}
      </div>

      <Card>
        <CardTitle
          title={gameName(game) + " 最近开奖"}
          sub="点击行进入历史开奖页查看完整期次与奖级明细"
          right={
            <Button variant="primary" onClick={() => nav("/predict")}>
              预测下一期
            </Button>
          }
        />
        {recent.loading ? (
          <Spinner />
        ) : recent.error ? (
          <ErrorNote message={recent.error} onRetry={recent.reload} />
        ) : !recent.data || recent.data.items.length === 0 ? (
          <Empty>还没有数据，去「数据源 / 同步」跑一次同步</Empty>
        ) : (
          <>
            <div className="flex flex-col gap-2 md:hidden">
              {recent.data.items.map((d) => (
                <button
                  key={d.id}
                  onClick={() => nav("/history?issue=" + d.issue)}
                  className="rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2 text-left"
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
                {recent.data.items.map((d) => (
                  <tr
                    key={d.id}
                    onClick={() => nav("/history?issue=" + d.issue)}
                    className="cursor-pointer border-t border-ink-700/60 hover:bg-ink-800/50"
                  >
                    <td className="num py-2 pr-3 text-fog-200">{d.issue}</td>
                    <td className="py-2 pr-3 text-fog-400">
                      {dateShort(d.draw_date) + " " + (d.week ? "周" + d.week : "")}
                    </td>
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
      </Card>

      <div className="grid gap-3 md:grid-cols-3 2xl:gap-4">
        {[
          { title: "历史开奖", desc: "按期号 / 日期检索，含奖级明细与销量奖池", to: "/history" },
          { title: "走势统计", desc: "频率、遗漏、号码走势热力图、和值跨度分布", to: "/analytics" },
          { title: "回测验证", desc: "滚动回测，用真实历史检验模型是否真的更强", to: "/backtest" },
        ].map((item) => (
          <button key={item.to} onClick={() => nav(item.to)} className="card p-4 text-left hover:border-jade/40">
            <div className="text-sm font-semibold text-fog-200">{item.title}</div>
            <div className="mt-1 text-[11px] leading-relaxed text-fog-400">{item.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
