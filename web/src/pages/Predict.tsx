import { useMemo, useState } from "react";
import { api, type Engine, type PredictResponse, type Strategy } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { useGame } from "../lib/store";
import { Balls } from "../components/Balls";
import { EChart, axisStyle, baseGrid, tooltipStyle, useChartColors } from "../components/EChart";
import { Badge, Button, Card, CardTitle, Empty, ErrorNote, NumberField, Select, Spinner, cx } from "../components/ui";
import { ENGINE_LABELS, STRATEGY_LABELS, gameName, timeShort } from "../lib/format";
import type { EChartsCoreOption } from "echarts/core";

const ENGINE_OPTS = (Object.keys(ENGINE_LABELS) as Engine[]).map((k) => ({ value: k, label: ENGINE_LABELS[k] }));
const STRATEGY_OPTS = (Object.keys(STRATEGY_LABELS) as Strategy[]).map((k) => ({ value: k, label: STRATEGY_LABELS[k] }));

export default function Predict() {
  const { game } = useGame();
  const [engine, setEngine] = useState<Engine>("ensemble");
  const [strategy, setStrategy] = useState<Strategy>("balanced");
  const [count, setCount] = useState(5);
  const [window, setWindow] = useState(100);
  const [pick, setPick] = useState(10);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingIdx, setSavingIdx] = useState<number | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const history = useAsync(() => api.predictHistory(game, 15), [game]);
  const c = useChartColors();

  async function run() {
    setLoading(true);
    setError(null);
    setSavedMsg(null);
    try {
      const body: Parameters<typeof api.predict>[0] = {
        game, count, engine, strategy, window,
      };
      if (game === "kl8") body.pick = pick;
      const res = await api.predict(body);
      setResult(res);
      history.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function save(idx: number) {
    if (!result) return;
    const t = result.tickets.find((x) => x.index === idx);
    if (!t) return;
    setSavingIdx(idx);
    try {
      await api.createTicket({
        game_code: game,
        issue: result.target_issue,
        numbers: t.numbers,
        cost: game === "kl8" ? 2 : 2,
        note: "预测生成 · " + ENGINE_LABELS[result.engine] + " / " + STRATEGY_LABELS[result.strategy],
      });
      setSavedMsg("第 " + idx + " 注已存入票夹");
    } catch (e) {
      setSavedMsg("保存失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSavingIdx(null);
    }
  }

  const marginalOption = useMemo<EChartsCoreOption>(() => {
    const ball = result?.marginals.find((m) => m.ball === "red");
    if (!ball) return {};
    const items = [...ball.items].sort((a, b) => b.p - a.p).slice(0, 20);
    return {
      grid: baseGrid({ bottom: 24 }),
      tooltip: {
        trigger: "axis",
        ...tooltipStyle(c),
        formatter: (p: unknown) => {
          const arr = p as { dataIndex: number }[];
          const it = items[arr[0]?.dataIndex ?? 0];
          return it ? "号码 " + it.n + "<br/>概率 " + (it.p * 100).toFixed(2) + "%" : "";
        },
      },
      xAxis: { type: "category", data: items.map((i) => String(i.n)), ...axisStyle(c) },
      yAxis: { type: "value", name: "概率", nameTextStyle: { color: c.label, fontSize: 10 }, ...axisStyle(c) },
      series: [
        {
          type: "bar",
          data: items.map((i) => Number((i.p * 100).toFixed(3))),
          itemStyle: { color: c.jade, borderRadius: [3, 3, 0, 0] },
        },
      ],
    };
  }, [result, c]);

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_420px]">
      <div className="flex flex-col gap-4">
        <Card>
          <CardTitle
            title={gameName(game) + " 下期预测"}
            sub="基于历史数据训练概率模型，按指定数量产出多注号码"
            right={result ? <Badge tone="good">{"目标期 " + result.target_issue}</Badge> : null}
          />
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-wider text-fog-400">模型</span>
              <Select value={engine} onChange={setEngine} options={ENGINE_OPTS} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-wider text-fog-400">策略</span>
              <Select value={strategy} onChange={setStrategy} options={STRATEGY_OPTS} />
            </label>
            <NumberField label="返回注数" value={count} onChange={setCount} min={1} max={100} width="w-20" />
            <NumberField label="回看期数" value={window} onChange={setWindow} min={10} max={2000} width="w-24" />
            {game === "kl8" && <NumberField label="选几" value={pick} onChange={setPick} min={1} max={20} width="w-16" />}
            <Button variant="primary" onClick={run} disabled={loading}>
              {loading ? "计算中…" : "生成预测"}
            </Button>
            {result && (
              <Button variant="subtle" onClick={() => setResult(null)}>
                清空结果
              </Button>
            )}
          </div>
          {error && <div className="mt-3"><ErrorNote message={error} /></div>}
          {savedMsg && <div className="mt-3 rounded-lg border border-jade/30 bg-jade/10 px-3 py-2 text-xs text-jade">{savedMsg}</div>}
        </Card>

        {loading && <Card><Spinner label="模型正在计算概率分布" /></Card>}

        {result && !loading && (
          <>
            <Card>
              <CardTitle
                title="预测号码"
                sub={"基于 " + result.based_on + " 及之前全部数据 · 用时 " + result.elapsed_ms + "ms · 随机种子 " + result.seed}
                right={
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge tone="info">{ENGINE_LABELS[result.engine] ?? result.engine}</Badge>
                    <Badge tone="neutral">{STRATEGY_LABELS[result.strategy] ?? result.strategy}</Badge>
                  </div>
                }
              />
              <div className="flex flex-col gap-2">
                {result.tickets.map((t) => (
                  <div
                    key={t.index}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2.5"
                  >
                    <div className="flex items-center gap-3">
                      <span className="num text-[11px] text-fog-400">#{t.index}</span>
                      <Balls red={t.numbers.red} blue={t.numbers.blue} ordered={t.numbers.ordered ?? null} size="sm" max={20} />
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-fog-400">
                      <span>奇偶 {t.structure.odd_even}</span>
                      <span>大小 {t.structure.big_small}</span>
                      <span className="num">和值 {t.structure.sum}</span>
                      <span className="num">跨度 {t.structure.span}</span>
                      <span className="num">评分 {t.score.toFixed(3)}</span>
                      <Button variant="subtle" onClick={() => save(t.index)} disabled={savingIdx === t.index}>
                        {savingIdx === t.index ? "…" : "存票夹"}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
              {Object.keys(result.weights).length > 0 && (
                <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-ink-700/60 pt-3 text-[11px] text-fog-400">
                  <span>集成权重</span>
                  {Object.entries(result.weights).map(([k, v]) => (
                    <span key={k} className="rounded-md border border-ink-700 px-1.5 py-0.5">
                      {ENGINE_LABELS[k] ?? k} <span className="num text-fog-200">{(v * 100).toFixed(0)}%</span>
                    </span>
                  ))}
                </div>
              )}
              <div className="mt-3 text-[11px] leading-relaxed text-fog-400">{result.note}</div>
            </Card>

            {result.marginals.length > 0 && (
              <Card>
                <CardTitle title="概率分布前十" sub="模型给出的红球边际概率（排序后取前 20）" />
                <EChart option={marginalOption} height={260} />
              </Card>
            )}
          </>
        )}

        {!result && !loading && (
          <Card>
            <CardTitle title="模型说明" />
            <div className="grid gap-2 text-[11px] leading-relaxed text-fog-400 md:grid-cols-2 2xl:grid-cols-3">
              <div><span className="text-fog-200">均匀基线</span>：所有号码等概率，作为检验模型的对照。</div>
              <div><span className="text-fog-200">频率热号</span>：近期出现越频繁概率越高，指数衰减加权。</div>
              <div><span className="text-fog-200">遗漏回补</span>：长期未出的号码给予概率补偿。</div>
              <div><span className="text-fog-200">马尔可夫</span>：用上一期开出情况做一阶条件概率。</div>
              <div><span className="text-fog-200">贝叶斯</span>：Beta-Binomial 后验平滑，抗小样本噪声。</div>
              <div><span className="text-fog-200">梯度提升树</span>：多特征非线性组合（频率、遗漏、期序等）。</div>
              <div><span className="text-fog-200">多模型集成</span>：上述模型加权融合，默认推荐。</div>
              <div><span className="text-fog-200">策略</span>：在概率基础上做温度调节，追热 / 守冷 / 均衡 / 混合。</div>
            </div>
          </Card>
        )}
      </div>

      <Card className="h-fit">
        <CardTitle
          title="预测历史"
          sub="每次预测都会落库，开奖后自动核对命中注数"
          right={<Button variant="subtle" onClick={history.reload}>刷新</Button>}
        />
        {history.loading ? (
          <Spinner />
        ) : history.error ? (
          <ErrorNote message={history.error} onRetry={history.reload} />
        ) : !history.data || history.data.length === 0 ? (
          <Empty>还没有预测记录</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {history.data.map((h) => {
              const hs = h.hit_summary as { max_hit?: number; avg_hit?: number; any_prize?: boolean } | null;
              return (
                <div key={h.id} className={cx("rounded-xl border px-3 py-2", h.checked ? "border-jade/25 bg-jade/5" : "border-ink-700/70 bg-ink-900/40")}>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="num text-fog-200">{"期 " + h.target_issue}</span>
                    {h.checked ? (
                      <Badge tone={hs?.any_prize ? "good" : "neutral"}>
                        {"最高 " + (hs?.max_hit ?? 0) + " 中"}
                      </Badge>
                    ) : (
                      <Badge tone="warn">待开奖</Badge>
                    )}
                  </div>
                  <div className="mt-1 text-[11px] text-fog-400">
                    {ENGINE_LABELS[h.engine] ?? h.engine} · {h.count} 注 · {timeShort(h.created_at)}
                  </div>
                  <div className="mt-1.5">
                    <Balls
                      red={h.tickets[0]?.numbers?.red}
                      blue={h.tickets[0]?.numbers?.blue}
                      size="sm"
                      max={7}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
