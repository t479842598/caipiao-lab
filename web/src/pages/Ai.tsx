import { useEffect, useState } from "react";
import { api, ApiError, type AiProviderRow, type AiVendor, type Engine, type Insight, type Strategy } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { useGame } from "../lib/store";
import { gameName, ENGINE_LABELS, STRATEGY_LABELS } from "../lib/format";
import {
  Badge,
  Button,
  Card,
  CardTitle,
  Empty,
  ErrorNote,
  NumberField,
  Select,
  Spinner,
  TextField,
} from "../components/ui";

const ENGINE_OPTIONS: { value: Engine; label: string }[] = [
  { value: "ensemble", label: ENGINE_LABELS.ensemble },
  { value: "frequency", label: ENGINE_LABELS.frequency },
  { value: "omission", label: ENGINE_LABELS.omission },
  { value: "markov", label: ENGINE_LABELS.markov },
  { value: "bayes", label: ENGINE_LABELS.bayes },
  { value: "gbdt", label: ENGINE_LABELS.gbdt },
  { value: "uniform", label: ENGINE_LABELS.uniform },
];

const STRATEGY_OPTIONS: { value: Strategy; label: string }[] = [
  { value: "balanced", label: STRATEGY_LABELS.balanced },
  { value: "hot", label: STRATEGY_LABELS.hot },
  { value: "cold", label: STRATEGY_LABELS.cold },
  { value: "mixed", label: STRATEGY_LABELS.mixed },
  { value: "random", label: STRATEGY_LABELS.random },
];

const VENDOR_FALLBACK: AiVendor[] = [
  { code: "openai", label: "OpenAI", base_url: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  { code: "deepseek", label: "DeepSeek", base_url: "https://api.deepseek.com/v1", model: "deepseek-chat" },
  { code: "moonshot", label: "Moonshot", base_url: "https://api.moonshot.cn/v1", model: "moonshot-v1-8k" },
  { code: "zhipu", label: "智谱 GLM", base_url: "https://open.bigmodel.cn/api/paas/v4", model: "glm-4-flash" },
  { code: "qwen", label: "通义千问", base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" },
  { code: "ollama", label: "本地 Ollama", base_url: "http://127.0.0.1:11434/v1", model: "qwen2.5:7b" },
  { code: "custom", label: "自定义（OpenAI 兼容）", base_url: "", model: "" },
];

export default function Ai() {
  const { game } = useGame();
  const vendors = useAsync(() => api.aiVendors(), []);
  const approved = useAsync(() => api.aiProviders(), []);
  const insight = useAsync(() => api.aiInsight(game), [game]);

  const [engine, setEngine] = useState<Engine>("ensemble");
  const [strategy, setStrategy] = useState<Strategy>("balanced");
  const [count, setCount] = useState(5);
  const [window, setWindow] = useState(100);
  const [question, setQuestion] = useState("");
  const [providerId, setProviderId] = useState<string>("");

  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<{ text: string; provider: string; model: string; latency: number } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "",
    vendor: "deepseek",
    base_url: "",
    model: "",
    api_key: "",
    submitter_name: "",
    submitter_contact: "",
    note: "",
  });
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [submitErr, setSubmitErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const vendorList = vendors.data && vendors.data.length > 0 ? vendors.data : VENDOR_FALLBACK;
  const vendorMeta = vendorList.find((v) => v.code === form.vendor);

  useEffect(() => {
    if (!vendorMeta) return;
    setForm((f) => ({
      ...f,
      base_url: f.base_url || vendorMeta.base_url,
      model: f.model || vendorMeta.model,
    }));
  }, [form.vendor]);

  async function analyze() {
    setBusy(true);
    setErr(null);
    try {
      const res = await api.aiAnalyze({
        game,
        count,
        engine,
        strategy,
        window,
        provider_id: providerId ? Number(providerId) : null,
        question: question.trim() || undefined,
      });
      setAnswer({
        text: res.answer || res.error || "（模型没有返回内容）",
        provider: res.provider_name || "local",
        model: res.model || "—",
        latency: res.latency_ms,
      });
    } catch (e) {
      if (e instanceof ApiError) setErr(e.message);
      else setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function submitProvider() {
    setSubmitting(true);
    setSubmitErr(null);
    setSubmitMsg(null);
    try {
      const res = await api.aiSubmitProvider({
        name: form.name.trim() || form.vendor,
        vendor: form.vendor,
        base_url: form.base_url.trim(),
        model: form.model.trim(),
        api_key: form.api_key.trim(),
        submitter_name: form.submitter_name.trim(),
        submitter_contact: form.submitter_contact.trim(),
        note: form.note.trim(),
      });
      setSubmitMsg(
        res.status === "approved"
          ? "已提交并自动通过（管理员直通），现在可以在上方选择它分析。"
          : "已提交，等待管理员审核。审核通过后它会出现在可用供应商列表里。",
      );
      setForm((f) => ({ ...f, api_key: "", note: "" }));
      approved.reload();
    } catch (e) {
      if (e instanceof ApiError) setSubmitErr(e.message);
      else setSubmitErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardTitle
          title="AI 号码分析"
          sub="用统计模型产出候选号码与结构画像，再交给大语言模型解读。模型只做解读，不改变概率。"
          right={<Badge tone="info">{gameName(game)}</Badge>}
        />
        <div className="flex flex-wrap items-end gap-3">
          <Select value={engine} onChange={setEngine} options={ENGINE_OPTIONS} label="引擎" />
          <Select value={strategy} onChange={setStrategy} options={STRATEGY_OPTIONS} label="策略" />
          <NumberField value={count} onChange={setCount} min={1} max={20} label="注数" />
          <NumberField value={window} onChange={setWindow} min={10} max={2000} step={10} label="窗口" width="w-24" />
          <Select
            value={providerId}
            onChange={setProviderId}
            options={[
              { value: "", label: "自动选择（第一个可用）" },
              ...(approved.data ?? []).map((p: AiProviderRow) => ({
                value: String(p.id),
                label: p.name + " · " + p.model,
              })),
            ]}
            label="AI 供应商"
          />
        </div>
        <div className="mt-3">
          <TextField
            value={question}
            onChange={setQuestion}
            label="想问的问题（可选）"
            placeholder="例如：这组号码的奇偶和大小结构是否均衡？"
            width="w-full" stack
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button variant="primary" onClick={analyze} disabled={busy}>
            {busy ? "分析中…" : "生成分析"}
          </Button>
          <span className="text-[11px] text-fog-500">
            可用供应商 {(approved.data ?? []).length} 个；无可用供应商时返回本地规则解读。
          </span>
        </div>
        {busy && (
          <div className="mt-3">
            <Spinner label="正在跑统计模型并请求大模型" />
          </div>
        )}
        {err && (
          <div className="mt-3">
            <ErrorNote message={err} />
          </div>
        )}
        {answer && (
          <div className="mt-3 rounded-xl border border-jade/25 bg-jade/5 p-3">
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-fog-400">
              <Badge tone="good">{answer.provider}</Badge>
              <span className="num">{answer.model}</span>
              <span className="num">{answer.latency} ms</span>
            </div>
            <div className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-fog-200">{answer.text}</div>
          </div>
        )}
      </Card>

      <Card>
        <CardTitle title="本彩种画像" sub="冷热号、遗漏、结构与随机性检验，作为 AI 解读的输入" />
        {insight.loading ? (
          <Spinner />
        ) : insight.error ? (
          <ErrorNote message={insight.error} onRetry={insight.reload} />
        ) : !insight.data ? (
          <Empty />
        ) : (
          <InsightBody data={insight.data} />
        )}
      </Card>

      <Card>
        <CardTitle
          title="提交我的 AI 供应商"
          sub="你填的信息会进入待审核队列，管理员在后台决定是否启用。API Key 加密存储、只显示掩码。"
        />
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
          <TextField
            value={form.name}
            onChange={(v) => setForm({ ...form, name: v })}
            label="显示名称"
            placeholder="例如：我的 DeepSeek"
            width="w-full" stack
          />
          <Select
            value={form.vendor}
            onChange={(v) => setForm({ ...form, vendor: v })}
            options={vendorList.map((v) => ({ value: v.code, label: v.label }))}
            label="厂商协议"
          />
          <TextField
            value={form.base_url}
            onChange={(v) => setForm({ ...form, base_url: v })}
            label="Base URL"
            placeholder="https://api.deepseek.com/v1"
            width="w-full" stack
          />
          <TextField
            value={form.model}
            onChange={(v) => setForm({ ...form, model: v })}
            label="模型名"
            placeholder="deepseek-chat"
            width="w-full" stack
          />
          <TextField
            value={form.api_key}
            onChange={(v) => setForm({ ...form, api_key: v })}
            label="API Key"
            placeholder="sk-..."
            width="w-full" stack
          />
          <TextField
            value={form.submitter_name}
            onChange={(v) => setForm({ ...form, submitter_name: v })}
            label="你的称呼"
            width="w-full" stack
          />
          <TextField
            value={form.submitter_contact}
            onChange={(v) => setForm({ ...form, submitter_contact: v })}
            label="联系方式"
            placeholder="邮箱 / TG，便于审核反馈"
            width="w-full" stack
          />
          <TextField
            value={form.note}
            onChange={(v) => setForm({ ...form, note: v })}
            label="备注"
            placeholder="额度、限速等"
            width="w-full" stack
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button variant="primary" onClick={submitProvider} disabled={submitting || !form.base_url || !form.model}>
            {submitting ? "提交中…" : "提交审核"}
          </Button>
          <span className="text-[11px] text-fog-500">
            Key 只用于调用该供应商，不会回显；管理员也只能看到前后各 4 位。
          </span>
        </div>
        {submitErr && (
          <div className="mt-3">
            <ErrorNote message={submitErr} />
          </div>
        )}
        {submitMsg && (
          <div className="mt-3 rounded-lg border border-jade/30 bg-jade/10 px-3 py-2 text-[11px] text-jade">
            {submitMsg}
          </div>
        )}
      </Card>

      <Card>
        <CardTitle title="已启用的供应商" sub="只有审核通过且启用的供应商会被调用" />
        {approved.loading ? (
          <Spinner />
        ) : !approved.data || approved.data.length === 0 ? (
          <Empty>暂无审核通过的供应商，分析会返回本地规则解读</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {approved.data.map((p) => (
              <div key={p.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-fog-200">{p.name}</span>
                  <Badge tone="neutral">{p.vendor}</Badge>
                  <span className="num text-[11px] text-fog-400">{p.model}</span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-fog-400">
                  <span className="num">调用 {p.calls}</span>
                  {p.healthy ? <Badge tone="good">正常</Badge> : <Badge tone="warn">异常</Badge>}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function InsightBody({ data }: { data: Insight }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="text-xs leading-relaxed text-fog-300">{data.summary}</div>
      <div className="grid gap-3 md:grid-cols-3 2xl:grid-cols-4">
        <MiniList title="热号" rows={data.hot.slice(0, 6).map((r) => ({ k: String(r.n), v: r.count + " 次" }))} tone="text-ball-red" />
        <MiniList title="冷号" rows={data.cold.slice(0, 6).map((r) => ({ k: String(r.n), v: r.count + " 次" }))} tone="text-ball-blue" />
        <MiniList
          title="遗漏前列"
          rows={data.omission_top.slice(0, 6).map((r) => ({ k: String(r.n), v: "当前 " + r.current + " 期" }))}
          tone="text-amber-glow"
        />
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-fog-400">
        <span className="num">目标期号 {data.target_issue || "—"}</span>
        <span className="num">基于 {data.based_on || "—"}</span>
        <span className="num">样本 {data.draws} 期</span>
        <span>随机性：{data.randomness}</span>
      </div>
      <div className="rounded-lg border border-ink-700/60 px-3 py-2 text-[11px] text-fog-500">{data.caveat}</div>
    </div>
  );
}

function MiniList({ title, rows, tone }: { title: string; rows: { k: string; v: string }[]; tone: string }) {
  return (
    <div className="rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2">
      <div className="text-[11px] text-fog-400">{title}</div>
      <div className="mt-1 flex flex-wrap gap-1.5">
        {rows.length === 0 ? (
          <span className="text-[11px] text-ink-500">—</span>
        ) : (
          rows.map((r) => (
            <span key={r.k} className={"rounded-md bg-ink-800 px-1.5 py-0.5 text-[11px] " + tone}>
              <span className="num">{r.k}</span>
              <span className="ml-1 text-[10px] text-fog-500">{r.v}</span>
            </span>
          ))
        )}
      </div>
    </div>
  );
}