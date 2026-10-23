import { useMemo, useState } from "react";
import { api, type Backtest as BacktestData, type Engine } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { useGame } from "../lib/store";
import { EChart, axisStyle, baseGrid, tooltipStyle, useChartColors } from "../components/EChart";
import { Badge, Button, Card, CardTitle, Empty, ErrorNote, NumberField, Select, Spinner, Stat } from "../components/ui";
import { ENGINE_LABELS, gameName } from "../lib/format";
import { TermHint, Glossary } from "../components/Term";
import type { EChartsCoreOption } from "echarts/core";

const ENGINE_OPTS = (Object.keys(ENGINE_LABELS) as Engine[]).map((k) => ({ value: k, label: ENGINE_LABELS[k] }));

export default function Backtest() {
  const { game } = useGame();
  const [engine, setEngine] = useState<Engine>("ensemble");
  const [periods, setPeriods] = useState(100);
  const [window, setWindow] = useState(60);
  const [topk, setTopk] = useState(6);
  const [stride, setStride] = useState(5);
  const [data, setData] = useState<BacktestData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const history = useAsync(() => api.syncStatus(), []);
  const c = useChartColors();

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.backtest({ game, periods, engine, window, topk, stride });
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const liftTone = data ? (data.lift_avg_hits > 1.05 ? "good" : data.lift_avg_hits < 0.95 ? "bad" : "warn") : "neutral";

  const curveOption = useMemo<EChartsCoreOption>(() => {
    if (!data) return {};
    const issues = data.per_issue.map((p) => p.issue);
    return {
      grid: baseGrid({ bottom: 28 }),
      tooltip: { trigger: "axis", ...tooltipStyle(c) },
      legend: { textStyle: { color: c.label, fontSize: 10 }, right: 0, top: 0 },
      xAxis: { type: "category", data: issues, ...axisStyle(c), axisLabel: { color: c.label, fontSize: 9, interval: Math.floor(issues.length / 8) } },
      yAxis: { type: "value", name: "命中个数", nameTextStyle: { color: c.label, fontSize: 10 }, ...axisStyle(c) },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 14, bottom: 0, borderColor: c.axis, textStyle: { color: c.label, fontSize: 9 } }],
      series: [
        {
          type: "line", name: "模型命中", data: data.per_issue.map((p) => p.model_hits),
          symbol: "none", lineStyle: { color: c.jade, width: 1.4 }, areaStyle: { color: c.jade + "1a" },
        },
        {
          type: "line", name: "基线命中", data: data.per_issue.map((p) => p.baseline_hits),
          symbol: "none", lineStyle: { color: c.axis, width: 1, type: "dashed" },
        },
      ],
    };
  }, [data, c]);

  const histOption = useMemo<EChartsCoreOption>(() => {
    if (!data) return {};
    const keys = Object.keys(data.hit_histogram).sort((a, b) => Number(a) - Number(b));
    return {
      grid: baseGrid(),
      tooltip: { trigger: "axis", ...tooltipStyle(c) },
      xAxis: { type: "category", data: keys.map((k) => k + " 中"), ...axisStyle(c) },
      yAxis: { type: "value", name: "期数", nameTextStyle: { color: c.label, fontSize: 10 }, ...axisStyle(c) },
      series: [{ type: "bar", data: keys.map((k) => data.hit_histogram[k]), itemStyle: { color: c.amber, borderRadius: [3, 3, 0, 0] } }],
    };
  }, [data, c]);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardTitle
          title={gameName(game) + " 算法实测验证"}
          sub="模拟「在过去每一期开奖前，只用那之前的数据猜，然后和真实结果对答案」。这是检验算法有没有真本事的唯一诚实办法"
        />
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-wider text-fog-400">模型</span>
            <Select value={engine} onChange={setEngine} options={ENGINE_OPTS} />
          </label>
          <NumberField label="检验多少期" value={periods} onChange={setPeriods} min={50} max={2000} width="w-24" />
          <NumberField label="每期参考最近" value={window} onChange={setWindow} min={20} max={1000} width="w-20" />
          <NumberField label="取最看好的前" value={topk} onChange={setTopk} min={1} max={20} width="w-16" />
          <NumberField label="每几期重算一次" value={stride} onChange={setStride} min={1} max={20} width="w-16" />
          <Button variant="primary" onClick={run} disabled={loading}>
            {loading ? "检验中…" : "开始检验"}
          </Button>
          <span className="text-[11px] text-fog-400">每 {stride} 期才重新算一次模型（只为提速，略降精度）</span>
        </div>
        {error && <div className="mt-3"><ErrorNote message={error} /></div>}
      </Card>

      {loading && (
        <Card>
          <Spinner label={"正在逐期检验 " + periods + " 期（机器学习算法较慢，请稍候）"} />
        </Card>
      )}

      {data && !loading && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6 2xl:gap-4">
            <Stat label="平均猜中几个号" value={data.model.avg_hits} hint={"瞎猜是 " + data.baseline.avg_hits + " 个"} />
            <Stat label="比瞎猜强多少" value={data.lift_avg_hits + "×"} tone={liftTone as "good" | "warn" | "bad"} hint="1.0× = 和瞎猜一样" />
            <Stat label="最看好的号猜中率" value={(data.model.hit_rate_at_topk * 100).toFixed(1) + "%"} hint={"前 " + data.topk + " 个号里"} />
            <Stat label="概率估计误差" value={data.model.log_loss} hint={"瞎猜是 " + data.baseline.log_loss + "（越小越好）"} />
            <Stat label="概率准确度" value={data.model.brier} hint="0 = 完美，越小越好" />
            <Stat label="实际检验" value={data.per_issue.length + " 期"} hint={"每组 " + data.stride + " 期"} />
          </div>

          <div className={"rounded-xl border px-4 py-3 text-xs leading-relaxed " + (data.lift_avg_hits > 1.05 ? "border-jade/30 bg-jade/8 text-jade" : data.lift_avg_hits < 0.95 ? "border-ball-red/30 bg-ball-red/8 text-ball-red" : "border-amber-glow/30 bg-amber-glow/8 text-amber-glow")}>
            {data.verdict}
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px] 2xl:grid-cols-[minmax(0,1fr)_380px]">
            <Card>
              <CardTitle title="每期猜中几个号" sub="绿线是算法，灰虚线是「完全瞎猜」的水平。两条线贴在一起就说明算法没用" right={<Badge tone="info">{ENGINE_LABELS[data.engine] ?? data.engine}</Badge>} />
              <EChart option={curveOption} height={300} />
            </Card>
            <Card>
              <CardTitle title="猜中个数的分布" sub="横轴是猜中几个，纵轴是出现了多少期" />
              <EChart option={histOption} height={300} />
            </Card>
          </div>

          <Card>
            <CardTitle title="各项指标对比" sub="「提升」大于 1 才算比瞎猜强" />
            <div className="overflow-x-auto">
              <table className="w-full min-w-[460px] text-xs">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-fog-400">
                    <th className="py-2 pr-3 font-normal">指标</th>
                    <th className="py-2 pr-3 text-right font-normal">模型</th>
                    <th className="py-2 pr-3 text-right font-normal">均匀基线</th>
                    <th className="py-2 text-right font-normal">提升</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { label: "平均猜中号数", m: data.model.avg_hits, b: data.baseline.avg_hits },
                    { label: "最看好的号猜中率", m: data.model.hit_rate_at_topk, b: data.baseline.hit_rate_at_topk },
                    { label: "概率估计误差（越小越好）", m: data.model.log_loss, b: data.baseline.log_loss },
                    { label: "概率准确度（越小越好）", m: data.model.brier, b: data.baseline.brier },
                    { label: "每组号码平均猜中", m: data.model.avg_ticket_hits, b: data.baseline.avg_ticket_hits },
                  ].map((row) => {
                    const ratio = row.b ? row.m / row.b : 0;
                    return (
                      <tr key={row.label} className="border-t border-ink-700/60">
                        <td className="py-2 pr-3 text-fog-300">{row.label}</td>
                        <td className="num py-2 pr-3 text-right text-fog-200">{row.m}</td>
                        <td className="num py-2 pr-3 text-right text-fog-400">{row.b}</td>
                        <td className={"num py-2 text-right " + (ratio > 1.02 ? "text-jade" : ratio < 0.98 ? "text-ball-red" : "text-fog-400")}>
                          {ratio ? ratio.toFixed(3) + "×" : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {!data && !loading && (
        <Card>
          <CardTitle title="为什么必须做这个检验" sub="这一页其实是在诚实地告诉你：预测到底有多大用" />
          <div className="flex flex-col gap-2.5 text-[11px] leading-relaxed text-fog-400">
            <p>
              <span className="text-fog-200">彩票每期都是独立的。</span>
              摇奖机不会记住上一期开了什么，也不会因为某个号「冷了 30 期」就补偿它。
              所以从数学上说，<span className="text-fog-200">任何算法都无法真正提高中奖概率</span>。
            </p>
            <p>
              <span className="text-fog-200">那为什么还要做这个页面？</span>
              因为「无法提高」是个结论，需要用你自己的数据验证一遍才算数。
              这一页就是拿真实历史逐期检验，把「算法到底有没有用」量化出来。
            </p>
            <p>
              <span className="text-fog-200">如果某个算法看起来赢了怎么办？</span>
              多半是三种情况：样本太小、算法把噪声当规律记住了（过拟合）、
              或者实现时不小心用到了「当时还不知道」的数据。
              所以在彩票上，稳定跑赢「瞎猜」的算法，现实中从未出现过。
            </p>
            <p>
              <span className="text-fog-200">检验流程：</span>
              从第 N 期开始，每一期都只用「这一期之前」的数据算一遍，猜这期，再和真实开奖对答案。
              全程禁止偷看未来，代码里有专门的测试守住这条线。
            </p>
          </div>
        </Card>
      )}
      {history.error && <ErrorNote message={history.error} />}

      <Glossary />
    </div>
  );
}
