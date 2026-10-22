import { useMemo, useState } from "react";
import { api, type Backtest as BacktestData, type Engine } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { useGame } from "../lib/store";
import { EChart, axisStyle, baseGrid, tooltipStyle, useChartColors } from "../components/EChart";
import { Badge, Button, Card, CardTitle, Empty, ErrorNote, NumberField, Select, Spinner, Stat } from "../components/ui";
import { ENGINE_LABELS, gameName } from "../lib/format";
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
          title={gameName(game) + " 滚动回测"}
          sub="每期只用当期之前的数据训练，再用该期真实开奖核对命中——这是检验模型是否有效的唯一诚实方式"
        />
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-wider text-fog-400">模型</span>
            <Select value={engine} onChange={setEngine} options={ENGINE_OPTS} />
          </label>
          <NumberField label="回测期数" value={periods} onChange={setPeriods} min={50} max={2000} width="w-24" />
          <NumberField label="回看窗口" value={window} onChange={setWindow} min={20} max={1000} width="w-20" />
          <NumberField label="每期取前" value={topk} onChange={setTopk} min={1} max={20} width="w-16" />
          <NumberField label="重训间隔" value={stride} onChange={setStride} min={1} max={20} width="w-16" />
          <Button variant="primary" onClick={run} disabled={loading}>
            {loading ? "回测中…" : "开始回测"}
          </Button>
          <span className="text-[11px] text-fog-400">树模型每 {stride} 期重训一次，可显著缩短耗时</span>
        </div>
        {error && <div className="mt-3"><ErrorNote message={error} /></div>}
      </Card>

      {loading && (
        <Card>
          <Spinner label={"正在滚动回测 " + periods + " 期（树模型较慢，请稍候）"} />
        </Card>
      )}

      {data && !loading && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6 2xl:gap-4">
            <Stat label="模型平均命中" value={data.model.avg_hits} hint={"基线 " + data.baseline.avg_hits} />
            <Stat label="命中提升" value={data.lift_avg_hits + "×"} tone={liftTone as "good" | "warn" | "bad"} hint="相对均匀基线" />
            <Stat label="Top-K 命中率" value={(data.model.hit_rate_at_topk * 100).toFixed(1) + "%"} hint={"前 " + data.topk + " 号"} />
            <Stat label="对数损失" value={data.model.log_loss} hint={"基线 " + data.baseline.log_loss} />
            <Stat label="Brier 分数" value={data.model.brier} hint="越小越准" />
            <Stat label="实回测" value={data.per_issue.length + " 期"} hint={"stride " + data.stride} />
          </div>

          <div className={"rounded-xl border px-4 py-3 text-xs leading-relaxed " + (data.lift_avg_hits > 1.05 ? "border-jade/30 bg-jade/8 text-jade" : data.lift_avg_hits < 0.95 ? "border-ball-red/30 bg-ball-red/8 text-ball-red" : "border-amber-glow/30 bg-amber-glow/8 text-amber-glow")}>
            {data.verdict}
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px] 2xl:grid-cols-[minmax(0,1fr)_380px]">
            <Card>
              <CardTitle title="逐期命中曲线" sub="绿线为模型，灰虚线为均匀基线" right={<Badge tone="info">{ENGINE_LABELS[data.engine] ?? data.engine}</Badge>} />
              <EChart option={curveOption} height={300} />
            </Card>
            <Card>
              <CardTitle title="命中分布" sub="每期命中几个号码的次数统计" />
              <EChart option={histOption} height={300} />
            </Card>
          </div>

          <Card>
            <CardTitle title="指标对照" />
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
                    { label: "平均命中", m: data.model.avg_hits, b: data.baseline.avg_hits },
                    { label: "Top-K 命中率", m: data.model.hit_rate_at_topk, b: data.baseline.hit_rate_at_topk },
                    { label: "对数损失", m: data.model.log_loss, b: data.baseline.log_loss },
                    { label: "Brier 分数", m: data.model.brier, b: data.baseline.brier },
                    { label: "单注平均命中", m: data.model.avg_ticket_hits, b: data.baseline.avg_ticket_hits },
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
          <CardTitle title="为什么必须做回测" />
          <div className="flex flex-col gap-2 text-[11px] leading-relaxed text-fog-400">
            <p>彩票开奖在设计上是独立同分布事件，理论上任何模型都无法提高中奖概率。本页的意义在于用真实历史数据把这个结论量化出来。</p>
            <p>如果某个模型在回测中稳定跑赢均匀基线，多半是小样本波动、过拟合，或者训练时不小心看到了未来数据。历史上真正稳健的优势从未出现过。</p>
            <p>回测流程：从第 N 期开始，逐期用「该期之前」的全部数据训练，预测下一期，再与该期实际开奖比对。全程严格禁止使用未来信息，代码里有对应测试覆盖。</p>
          </div>
        </Card>
      )}
      {history.error && <ErrorNote message={history.error} />}
    </div>
  );
}
