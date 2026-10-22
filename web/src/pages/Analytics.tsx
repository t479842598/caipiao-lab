import { useMemo, useState } from "react";
import { api } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { useGame } from "../lib/store";
import { EChart, axisStyle, baseGrid, tooltipStyle, useChartColors } from "../components/EChart";
import { Badge, Button, Card, CardTitle, Empty, ErrorNote, NumberField, Spinner } from "../components/ui";
import { gameName, pct } from "../lib/format";
import type { EChartsCoreOption } from "echarts/core";

type Tab = "frequency" | "omission" | "trend" | "distribution" | "randomness";

const TABS: { key: Tab; label: string }[] = [
  { key: "frequency", label: "号码频率" },
  { key: "omission", label: "遗漏分析" },
  { key: "trend", label: "走势图" },
  { key: "distribution", label: "形态分布" },
  { key: "randomness", label: "随机性检验" },
];

export default function Analytics() {
  const { game } = useGame();
  const [tab, setTab] = useState<Tab>("frequency");
  const [window, setWindow] = useState(100);
  const [periods, setPeriods] = useState(40);
  const [omissionLimit, setOmissionLimit] = useState(0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="-mx-1 flex max-w-full gap-1 overflow-x-auto rounded-xl border border-ink-700 bg-ink-900/60 p-0.5 md:mx-0">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={
                "shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs transition-colors " +
                (tab === t.key ? "bg-ink-600 text-fog-100" : "text-fog-400 hover:text-fog-200")
              }
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-fog-400">彩种</span>
          <Badge tone="info">{gameName(game)}</Badge>
        </div>
      </div>

      {tab === "frequency" && (
        <FrequencyPanel game={game} window={window} setWindow={setWindow} />
      )}
      {tab === "omission" && (
        <OmissionPanel game={game} limit={omissionLimit} setLimit={setOmissionLimit} />
      )}
      {tab === "trend" && <TrendPanel game={game} periods={periods} setPeriods={setPeriods} />}
      {tab === "distribution" && <DistributionPanel game={game} window={window} setWindow={setWindow} />}
      {tab === "randomness" && <RandomnessPanel game={game} />}
    </div>
  );
}

function FrequencyPanel({ game, window, setWindow }: { game: string; window: number; setWindow: (v: number) => void }) {
  const data = useAsync(() => api.frequency(game, window), [game, window]);
  const c = useChartColors();

  const option = useMemo<EChartsCoreOption>(() => {
    const items = data.data?.items ?? [];
    const maxDev = Math.max(0.5, ...items.map((i) => Math.abs(i.deviation)));
    return {
      grid: baseGrid({ right: 34, bottom: 4, top: 28 }),
      legend: { textStyle: { color: c.label, fontSize: 10 }, right: 0, top: 0, itemWidth: 10, itemHeight: 8 },
      tooltip: {
        trigger: "axis",
        ...tooltipStyle(c),
        formatter: (p: unknown) => {
          const arr = p as { dataIndex: number }[];
          const it = items[arr[0]?.dataIndex ?? 0];
          if (!it) return "";
          return "号码 " + it.n + "<br/>出现 " + it.count + " 次（" + pct(it.rate, 2) + "）<br/>期望 " + it.expected + " 次，偏差 " + it.deviation;
        },
      },
      xAxis: {
        type: "category",
        data: items.map((i) => String(i.n)),
        ...axisStyle(c),
      },
      yAxis: [
        { type: "value", ...axisStyle(c) },
        { type: "value", ...axisStyle(c), splitLine: { show: false } },
      ],
      series: [
        {
          type: "bar",
          name: "出现次数",
          data: items.map((i) => i.count),
          itemStyle: { color: c.jade, borderRadius: [3, 3, 0, 0] },
        },
        {
          type: "line",
          name: "偏差",
          yAxisIndex: 1,
          data: items.map((i) => i.deviation),
          symbol: "none",
          lineStyle: { color: c.amber, width: 1.2 },
          markLine: {
            silent: true,
            symbol: "none",
            data: [
              { yAxis: maxDev, lineStyle: { color: c.axis, type: "dashed" }, label: { show: false } },
              { yAxis: -maxDev, lineStyle: { color: c.axis, type: "dashed" }, label: { show: false } },
              { yAxis: 0, lineStyle: { color: c.red, opacity: 0.4 }, label: { show: false } },
            ],
          },
        },
      ],
    };
  }, [data.data, c]);

  return (
    <Card>
      <CardTitle
        title="号码频率"
        sub={data.data ? "样本 " + data.data.total_draws + " 期，理论期望 " + (data.data.total_draws * 6 / 33).toFixed(2) + " 次/号" : "红球出现次数与理论值偏差"}
        right={<NumberField label="统计期数" value={window} onChange={setWindow} min={10} max={2000} width="w-24" />}
      />
      {data.loading ? <Spinner /> : data.error ? <ErrorNote message={data.error} onRetry={data.reload} /> : (
        <>
          <EChart option={option} height={300} />
          <div className="mt-3 grid grid-cols-2 gap-1.5 sm:grid-cols-3 md:hidden">
            {(data.data?.items ?? []).map((i) => (
              <div key={i.n} className="rounded-md bg-ink-800/60 px-2 py-1.5 text-[11px]">
                <div className="num flex items-baseline justify-between">
                  <span className="text-xs text-fog-200">{i.n}</span>
                  <span className={"num " + (i.deviation > 0 ? "text-ball-red" : "text-ball-blue")}>
                    {i.deviation > 0 ? "+" : ""}{i.deviation.toFixed(1)}
                  </span>
                </div>
                <div className="num mt-0.5 flex justify-between text-fog-400">
                  <span>{i.count} 次</span>
                  <span>{pct(i.rate)}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 hidden overflow-x-auto md:block">
            <table className="w-full min-w-[500px] text-xs">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-fog-400">
                  <th className="py-1.5 pr-3 font-normal">号码</th>
                  <th className="py-1.5 pr-3 text-right font-normal">出现</th>
                  <th className="py-1.5 pr-3 text-right font-normal">频率</th>
                  <th className="py-1.5 pr-3 text-right font-normal">期望</th>
                  <th className="py-1.5 text-right font-normal">偏差</th>
                </tr>
              </thead>
              <tbody>
                {(data.data?.items ?? []).map((i) => (
                  <tr key={i.n} className="border-t border-ink-700/60">
                    <td className="num py-1.5 pr-3 text-fog-200">{i.n}</td>
                    <td className="num py-1.5 pr-3 text-right text-fog-300">{i.count}</td>
                    <td className="num py-1.5 pr-3 text-right text-fog-400">{pct(i.rate)}</td>
                    <td className="num py-1.5 pr-3 text-right text-fog-400">{i.expected.toFixed(1)}</td>
                    <td className={"num py-1.5 text-right " + (i.deviation > 0 ? "text-ball-red" : "text-ball-blue")}>
                      {i.deviation > 0 ? "+" : ""}{i.deviation.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}

function OmissionPanel({ game, limit, setLimit }: { game: string; limit: number; setLimit: (v: number) => void }) {
  const data = useAsync(() => api.omission(game, limit), [game, limit]);
  const c = useChartColors();

  const option = useMemo<EChartsCoreOption>(() => {
    const items = (data.data?.items ?? []).slice(0, 40);
    return {
      grid: baseGrid({ bottom: 24 }),
      tooltip: { trigger: "axis", ...tooltipStyle(c) },
      legend: { textStyle: { color: c.label, fontSize: 10 }, right: 0, top: 0 },
      xAxis: { type: "category", data: items.map((i) => String(i.n)), ...axisStyle(c) },
      yAxis: { type: "value", name: "期数", nameTextStyle: { color: c.label, fontSize: 10 }, ...axisStyle(c) },
      series: [
        { type: "bar", name: "当前遗漏", data: items.map((i) => i.current), itemStyle: { color: c.amber, borderRadius: [3, 3, 0, 0] } },
        { type: "bar", name: "历史最大", data: items.map((i) => i.max), itemStyle: { color: c.axis, borderRadius: [3, 3, 0, 0] } },
      ],
    };
  }, [data.data, c]);

  return (
    <Card>
      <CardTitle
        title="遗漏分析"
        sub="当前遗漏期数 vs 历史最大遗漏，遗漏越久不代表越容易开出"
        right={<NumberField label="只看前 N" value={limit} onChange={setLimit} min={0} max={80} width="w-16" />}
      />
      {data.loading ? <Spinner /> : data.error ? <ErrorNote message={data.error} onRetry={data.reload} /> : (
        <>
          <EChart option={option} height={280} />
          <div className="mt-3 grid grid-cols-2 gap-1.5 sm:grid-cols-3 md:hidden">
            {(data.data?.items ?? []).map((i) => (
              <div key={i.n} className="rounded-md bg-ink-800/60 px-2 py-1.5 text-[11px]">
                <div className="num flex items-baseline justify-between">
                  <span className="text-xs text-fog-200">{i.n}</span>
                  <span className="num text-amber-glow">当前 {i.current}</span>
                </div>
                <div className="num mt-0.5 flex justify-between text-fog-400">
                  <span>最大 {i.max}</span>
                  <span>均 {i.avg}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 hidden overflow-x-auto md:block">
            <table className="w-full min-w-[460px] text-xs">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-fog-400">
                  <th className="py-1.5 pr-3 font-normal">号码</th>
                  <th className="py-1.5 pr-3 text-right font-normal">当前遗漏</th>
                  <th className="py-1.5 pr-3 text-right font-normal">历史最大</th>
                  <th className="py-1.5 pr-3 text-right font-normal">平均遗漏</th>
                  <th className="py-1.5 text-right font-normal">上次开出</th>
                </tr>
              </thead>
              <tbody>
                {(data.data?.items ?? []).map((i) => (
                  <tr key={i.n} className="border-t border-ink-700/60">
                    <td className="num py-1.5 pr-3 text-fog-200">{i.n}</td>
                    <td className="num py-1.5 pr-3 text-right text-amber-glow">{i.current}</td>
                    <td className="num py-1.5 pr-3 text-right text-fog-400">{i.max}</td>
                    <td className="num py-1.5 pr-3 text-right text-fog-400">{i.avg}</td>
                    <td className="num py-1.5 text-right text-fog-400">{i.last_issue ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}

function TrendPanel({ game, periods, setPeriods }: { game: string; periods: number; setPeriods: (v: number) => void }) {
  const data = useAsync(() => api.trend(game, periods), [game, periods]);
  const c = useChartColors();

  const option = useMemo<EChartsCoreOption>(() => {
    if (!data.data) return {};
    const { issues, domain, matrix } = data.data;
    const cells: [number, number, number][] = [];
    matrix.forEach((row, y) => row.forEach((v, x) => { if (v) cells.push([x, y, 1]); }));
    return {
      grid: baseGrid({ bottom: 40, left: 8 }),
      tooltip: {
        ...tooltipStyle(c),
        formatter: (p: unknown) => {
          const q = p as { value: [number, number, number] };
          return "号码 " + domain[q.value[0]] + "<br/>期号 " + issues[q.value[1]] + "<br/>已开出";
        },
      },
      xAxis: { type: "category", data: domain.map(String), ...axisStyle(c), splitArea: { show: false } },
      yAxis: { type: "category", data: issues, ...axisStyle(c), splitLine: { show: false } },
      visualMap: { show: false, min: 0, max: 1, inRange: { color: [c.fade, c.jade] } },
      series: [
        {
          type: "scatter",
          symbolSize: 11,
          data: cells.map((cl) => ({ value: cl, itemStyle: { color: c.jade, borderRadius: 3 } })),
        },
      ],
    };
  }, [data.data, c]);

  const omissionOption = useMemo<EChartsCoreOption>(() => {
    if (!data.data) return {};
    const { issues, domain, omission } = data.data;
    const cells: [number, number, number][] = [];
    omission.forEach((row, y) => row.forEach((v, x) => { if (v > 0) cells.push([x, y, v]); }));
    const maxV = Math.max(1, ...omission.flat());
    return {
      grid: baseGrid({ bottom: 40 }),
      tooltip: {
        ...tooltipStyle(c),
        formatter: (p: unknown) => {
          const q = p as { value: [number, number, number] };
          return "号码 " + domain[q.value[0]] + "<br/>期号 " + issues[q.value[1]] + "<br/>遗漏 " + q.value[2] + " 期";
        },
      },
      xAxis: { type: "category", data: domain.map(String), ...axisStyle(c) },
      yAxis: { type: "category", data: issues, ...axisStyle(c), splitLine: { show: false } },
      visualMap: { show: false, min: 0, max: maxV, inRange: { color: [c.fade, c.jade, c.amber] } },
      series: [{ type: "heatmap", data: cells }],
    };
  }, [data.data, c]);

  const chartH = Math.max(240, Math.min(periods * 11, 620));

  return (
    <Card>
      <CardTitle
        title="号码走势"
        sub="上方为每期开出位置，下方为逐期遗漏热力图"
        right={<NumberField label="期数" value={periods} onChange={setPeriods} min={10} max={200} width="w-20" />}
      />
      {data.loading ? <Spinner /> : data.error ? <ErrorNote message={data.error} onRetry={data.reload} /> : !data.data ? <Empty /> : (
        <>
          <div className="mb-1 text-[11px] text-fog-400">开出走势</div>
          <EChart option={option} height={chartH} />
          <div className="mb-1 mt-3 text-[11px] text-fog-400">遗漏热力</div>
          <EChart option={omissionOption} height={chartH} />
        </>
      )}
    </Card>
  );
}

function DistributionPanel({ game, window, setWindow }: { game: string; window: number; setWindow: (v: number) => void }) {
  const data = useAsync(() => api.distribution(game, window), [game, window]);
  const c = useChartColors();

  const histOption = (bins: { bin: string; count: number }[], color: string): EChartsCoreOption => ({
    grid: baseGrid({ top: 24 }),
    tooltip: { trigger: "axis", ...tooltipStyle(c) },
    xAxis: { type: "category", data: bins.map((b) => b.bin), ...axisStyle(c) },
    yAxis: { type: "value", ...axisStyle(c) },
    series: [{ type: "bar", data: bins.map((b) => b.count), itemStyle: { color, borderRadius: [3, 3, 0, 0] } }],
  });

  const s = data.data?.stats;

  return (
    <Card>
      <CardTitle
        title="形态分布"
        sub="和值、跨度、奇偶比、大小比等组合形态的历史分布"
        right={<NumberField label="统计期数" value={window} onChange={setWindow} min={20} max={2000} width="w-24" />}
      />
      {data.loading ? <Spinner /> : data.error ? <ErrorNote message={data.error} onRetry={data.reload} /> : !data.data ? <Empty /> : (
        <>
          {s && (
            <div className="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4">
              {[
                { label: "和值均值", v: s.sum.mean, hint: "标准差 " + s.sum.std },
                { label: "跨度均值", v: s.span.mean, hint: "标准差 " + s.span.std },
                { label: "奇数均值", v: s.odd.mean, hint: "满分 6" },
                { label: "大号均值", v: s.big.mean, hint: "满分 6" },
              ].map((it) => (
                <div key={it.label} className="rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-wider text-fog-400">{it.label}</div>
                  <div className="num text-base font-semibold text-fog-200">{it.v}</div>
                  <div className="text-[10px] text-fog-400">{it.hint}</div>
                </div>
              ))}
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
            <div>
              <div className="mb-1 text-[11px] text-fog-400">和值分布</div>
              <EChart option={histOption(data.data.sum_hist, c.jade)} height={200} />
            </div>
            <div>
              <div className="mb-1 text-[11px] text-fog-400">跨度分布</div>
              <EChart option={histOption(data.data.span_hist, c.blue)} height={200} />
            </div>
            <div>
              <div className="mb-1 text-[11px] text-fog-400">奇偶比</div>
              <EChart option={histOption(data.data.odd_even_hist, c.amber)} height={200} />
            </div>
            <div>
              <div className="mb-1 text-[11px] text-fog-400">大小比</div>
              <EChart option={histOption(data.data.big_small_hist, c.red)} height={200} />
            </div>
            <div>
              <div className="mb-1 text-[11px] text-fog-400">三区比</div>
              <EChart option={histOption(data.data.zone_hist, c.jade)} height={200} />
            </div>
            <div>
              <div className="mb-1 text-[11px] text-fog-400">连号个数</div>
              <EChart option={histOption(data.data.consecutive_hist, c.blue)} height={200} />
            </div>
          </div>
        </>
      )}
    </Card>
  );
}

function RandomnessPanel({ game }: { game: string }) {
  const data = useAsync(() => api.randomness(game), [game]);
  const d = data.data;

  return (
    <Card>
      <CardTitle title="随机性检验" sub="用卡方、游程、自相关检验历史号码是否符合独立均匀分布" />
      {data.loading ? <Spinner /> : data.error ? <ErrorNote message={data.error} onRetry={data.reload} /> : !d ? <Empty /> : (
        <div className="flex flex-col gap-3">
          <div className="rounded-xl border border-jade/25 bg-jade/8 px-3 py-2.5 text-xs text-jade">{d.verdict}</div>
          <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
            <div className="rounded-xl border border-ink-700/70 bg-ink-900/40 p-3 text-xs">
              <div className="mb-1.5 text-[11px] uppercase tracking-wider text-fog-400">卡方拟合检验</div>
              <div className="num text-fog-200">χ² = {d.chi_square.statistic}（自由度 {d.chi_square.dof}）</div>
              <div className="num mt-1 text-fog-400">p 值 = {String(d.chi_square.p_value)}</div>
              <div className="num mt-1 text-fog-400">理论期望 {d.chi_square.uniform_expected} 次/号 · 样本 {d.draws} 期</div>
            </div>
            <div className="rounded-xl border border-ink-700/70 bg-ink-900/40 p-3 text-xs">
              <div className="mb-1.5 text-[11px] uppercase tracking-wider text-fog-400">游程检验</div>
              <div className="num text-fog-200">z = {d.runs_test.z}</div>
              <div className="num mt-1 text-fog-400">p 值 = {String(d.runs_test.p_value)}</div>
              <div className="mt-1 text-fog-400">序列是否存在连续偏倚</div>
            </div>
          </div>
          <div>
            <div className="mb-1.5 text-[11px] uppercase tracking-wider text-fog-400">滞后自相关</div>
            <div className="flex flex-wrap gap-2">
              {d.autocorrelation.map((a) => (
                <div key={String(a.lag)} className="rounded-lg border border-ink-700/70 px-2.5 py-1.5 text-[11px] text-fog-400">
                  lag {String(a.lag)} <span className="num text-fog-200">{String(a.corr)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="flex justify-end">
            <Button onClick={data.reload}>重新计算</Button>
          </div>
        </div>
      )}
    </Card>
  );
}
