import { useState } from "react";
import { Navigate } from "react-router-dom";
import { api, ApiError, type AiProviderRow } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { useAuth } from "../lib/auth";
import {
  Badge,
  Button,
  Card,
  CardTitle,
  Empty,
  ErrorNote,
  Select,
  Spinner,
  TextField,
} from "../components/ui";
import { gameName, timeShort } from "../lib/format";

type Tab = "overview" | "users" | "audit" | "sessions" | "ai";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "运行状态" },
  { key: "users", label: "账号" },
  { key: "audit", label: "审计日志" },
  { key: "sessions", label: "会话" },
  { key: "ai", label: "AI 供应商审核" },
];

export default function Admin() {
  const { user, isAdmin, loading } = useAuth();
  const [tab, setTab] = useState<Tab>("overview");
  const [toast, setToast] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (loading) return <Spinner label="检查登录状态" />;
  if (!isAdmin) return <Navigate to="/login" replace />;

  function report(e: unknown, okText?: string) {
    if (e instanceof ApiError) setErr(e.message);
    else if (e) setErr(e instanceof Error ? e.message : String(e));
    else {
      setErr(null);
      setToast(okText ?? "已完成");
      setTimeout(() => setToast(null), 2600);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-base font-semibold text-fog-200">管理后台</h1>
          <p className="mt-0.5 text-[11px] text-fog-400">
            当前账号 {user?.username}（{user?.role}）· 所有写操作都会记入审计日志
          </p>
        </div>
        <div className="flex flex-wrap gap-1 rounded-xl border border-ink-700 bg-ink-900/60 p-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={
                "rounded-lg px-2.5 py-1.5 text-[11px] transition-colors " +
                (tab === t.key ? "bg-ink-600 text-fog-100" : "text-fog-400 hover:text-fog-200")
              }
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {err && <ErrorNote message={err} onRetry={() => setErr(null)} />}
      {toast && (
        <div className="rounded-lg border border-jade/30 bg-jade/10 px-3 py-2 text-[11px] text-jade">{toast}</div>
      )}

      {tab === "overview" && <Overview report={report} />}
      {tab === "users" && <Users report={report} selfId={user?.id ?? 0} />}
      {tab === "audit" && <Audit />}
      {tab === "sessions" && <Sessions report={report} />}
      {tab === "ai" && <AiReview report={report} />}
    </div>
  );
}

function Overview({ report }: { report: (e: unknown, ok?: string) => void }) {
  const ov = useAsync(() => api.adminOverview(), []);
  const { user, logout } = useAuth();
  const [pw, setPw] = useState({ old: "", next: "", confirm: "" });
  const [busy, setBusy] = useState(false);

  if (ov.loading) return <Spinner />;
  if (ov.error) return <ErrorNote message={ov.error} onRetry={ov.reload} />;
  const d = ov.data;
  if (!d) return <Empty />;

  const cells: [string, string][] = [
    ["历史开奖", d.draws.toLocaleString("zh-CN")],
    ["同步运行", String(d.sync_runs)],
    ["预测记录", String(d.predictions)],
    ["票夹记录", String(d.tickets)],
    ["AI 供应商", String(d.ai_providers) + (d.ai_pending ? "（待审 " + d.ai_pending + "）" : "")],
    ["AI 分析", String(d.ai_analyses)],
    ["账号", String(d.users)],
    ["活跃会话", String(d.sessions)],
    ["审计日志", String(d.audit_logs)],
  ];

  async function changePw() {
    if (pw.next !== pw.confirm) {
      report(new Error("两次输入的新密码不一致"));
      return;
    }
    setBusy(true);
    try {
      await api.changePassword({ old_password: pw.old, new_password: pw.next });
      report(null, "密码已更新，所有会话已失效，请重新登录");
      setPw({ old: "", next: "", confirm: "" });
      setTimeout(() => void logout(), 1500);
    } catch (e) {
      report(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-5 2xl:grid-cols-6">
        {cells.map(([k, v]) => (
          <div key={k} className="card p-3">
            <div className="text-[11px] text-fog-400">{k}</div>
            <div className="num mt-1 text-lg font-semibold text-fog-200">{v}</div>
          </div>
        ))}
      </div>

      <Card>
        <CardTitle title="运行开关" sub="来自服务端环境变量，修改需编辑 deploy/.env 后重启" />
        <div className="flex flex-wrap gap-2 text-[11px]">
          <Badge tone={d.read_only ? "warn" : "good"}>只读模式 {d.read_only ? "开" : "关"}</Badge>
          <Badge tone={d.sync_enabled ? "good" : "neutral"}>定时同步 {d.sync_enabled ? "开" : "关"}</Badge>
          <Badge tone={d.ai_enabled ? "good" : "neutral"}>AI 分析 {d.ai_enabled ? "开" : "关"}</Badge>
          <Badge tone={d.docs_enabled ? "info" : "neutral"}>API 文档 {d.docs_enabled ? "开" : "关"}</Badge>
          <Badge tone={d.cookie_secure ? "good" : "warn"}>Cookie Secure {d.cookie_secure ? "开" : "关"}</Badge>
          <Badge tone={d.admin_token_set ? "warn" : "neutral"}>
            静态令牌 {d.admin_token_set ? "已设置" : "未设置"}
          </Badge>
        </div>
      </Card>

      <Card>
        <CardTitle title="修改我的密码" sub="修改后全部会话立即失效，需要重新登录" />
        <div className="flex flex-wrap items-end gap-3">
          <TextField value={pw.old} onChange={(v) => setPw({ ...pw, old: v })} label="原密码" type="password" stack width="w-44" />
          <TextField value={pw.next} onChange={(v) => setPw({ ...pw, next: v })} label="新密码" type="password" stack width="w-44" />
          <TextField
            value={pw.confirm}
            onChange={(v) => setPw({ ...pw, confirm: v })}
            label="确认新密码"
            type="password"
            stack
            width="w-44"
          />
          <Button variant="primary" onClick={changePw} disabled={busy || !pw.old || !pw.next}>
            更新密码
          </Button>
        </div>
        <p className="mt-2 text-[11px] text-fog-500">当前登录：{user?.username}</p>
      </Card>
    </div>
  );
}

function Users({ report, selfId }: { report: (e: unknown, ok?: string) => void; selfId: number }) {
  const list = useAsync(() => api.adminUsers(), []);
  const [form, setForm] = useState({ username: "", password: "", role: "viewer" });

  async function create() {
    try {
      await api.adminCreateUser(form);
      setForm({ username: "", password: "", role: "viewer" });
      report(null, "账号已创建");
      list.reload();
    } catch (e) {
      report(e);
    }
  }

  async function patch(id: number, body: Record<string, unknown>) {
    try {
      await api.adminPatchUser(id, body);
      report(null, "已更新");
      list.reload();
    } catch (e) {
      report(e);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardTitle title="新建账号" sub="viewer 只能查看，admin 可操作后台；密码至少 10 位且需大小写数字" />
        <div className="flex flex-wrap items-end gap-3">
          <TextField
            value={form.username}
            onChange={(v) => setForm({ ...form, username: v })}
            label="账号"
            stack
            width="w-44"
          />
          <TextField
            value={form.password}
            onChange={(v) => setForm({ ...form, password: v })}
            label="初始密码"
            type="password"
            stack
            width="w-52"
          />
          <Select
            value={form.role}
            onChange={(v) => setForm({ ...form, role: v })}
            options={[
              { value: "viewer", label: "viewer（只读）" },
              { value: "admin", label: "admin（管理）" },
            ]}
            label="角色"
          />
          <Button variant="primary" onClick={create} disabled={!form.username || form.password.length < 8}>
            创建
          </Button>
        </div>
      </Card>

      <Card>
        <CardTitle title="账号列表" />
        {list.loading ? (
          <Spinner />
        ) : list.error ? (
          <ErrorNote message={list.error} onRetry={list.reload} />
        ) : !list.data || list.data.length === 0 ? (
          <Empty />
        ) : (
          <div className="flex flex-col gap-2">
            {list.data.map((u) => (
              <div key={u.id} className="rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-fog-200">{u.username}</span>
                    <Badge tone={u.role === "admin" ? "info" : "neutral"}>{u.role}</Badge>
                    <Badge tone={u.enabled ? "good" : "bad"}>{u.enabled ? "启用" : "停用"}</Badge>
                    {u.id === selfId && <Badge tone="warn">当前账号</Badge>}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="num text-[11px] text-fog-500">
                      上次登录 {u.last_login_at ? timeShort(u.last_login_at) : "—"}
                    </span>
                    {u.id !== selfId && (
                      <>
                        <Select
                          value={u.role}
                          onChange={(v) => patch(u.id, { role: v })}
                          options={[
                            { value: "viewer", label: "viewer" },
                            { value: "admin", label: "admin" },
                          ]}
                        />
                        <Button
                          variant={u.enabled ? "danger" : "primary"}
                          onClick={() => patch(u.id, { enabled: !u.enabled })}
                        >
                          {u.enabled ? "停用" : "启用"}
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function Audit() {
  const [action, setAction] = useState("");
  const [status, setStatus] = useState("");
  const actions = useAsync(() => api.adminAuditActions(), []);
  const rows = useAsync(
    () => api.adminAudit({ action: action || undefined, status: status || undefined, limit: 100 }),
    [action, status],
  );

  return (
    <Card>
      <CardTitle
        title="审计日志"
        sub="登录、同步、供应商变更、账号操作全部留痕，最近 100 条"
        right={
          <div className="flex flex-wrap items-end gap-2">
            <Select
              value={action}
              onChange={setAction}
              options={[{ value: "", label: "全部动作" }, ...(actions.data ?? []).map((a) => ({ value: a.action, label: a.action + " (" + a.count + ")" }))]}
            />
            <Select
              value={status}
              onChange={setStatus}
              options={[
                { value: "", label: "全部结果" },
                { value: "ok", label: "成功" },
                { value: "fail", label: "失败" },
              ]}
            />
            <Button variant="subtle" onClick={rows.reload}>
              刷新
            </Button>
          </div>
        }
      />
      {rows.loading ? (
        <Spinner />
      ) : rows.error ? (
        <ErrorNote message={rows.error} onRetry={rows.reload} />
      ) : !rows.data || rows.data.length === 0 ? (
        <Empty>暂无日志</Empty>
      ) : (
        <div className="flex flex-col gap-1.5">
          {rows.data.map((r) => (
            <div key={r.id} className="rounded-lg border border-ink-700/60 bg-ink-900/30 px-2.5 py-1.5">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
                <Badge tone={r.status === "ok" ? "good" : "bad"}>{r.status}</Badge>
                <span className="text-fog-200">{r.action}</span>
                <span className="text-fog-500">·</span>
                <span className="text-fog-400">{r.actor || "anonymous"}</span>
                {r.target && <span className="num text-fog-500">{r.target}</span>}
                <span className="num ml-auto text-[10px] text-ink-500">{timeShort(r.at)}</span>
              </div>
              {r.ip && <div className="num mt-0.5 text-[10px] text-ink-500">{r.ip}</div>}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function Sessions({ report }: { report: (e: unknown, ok?: string) => void }) {
  const list = useAsync(() => api.adminSessions(), []);

  async function kill(id: number) {
    try {
      await api.adminKillSession(id);
      report(null, "会话已吊销");
      list.reload();
    } catch (e) {
      report(e);
    }
  }

  return (
    <Card>
      <CardTitle title="登录会话" sub="吊销后该会话立即失效" right={<Button variant="subtle" onClick={list.reload}>刷新</Button>} />
      {list.loading ? (
        <Spinner />
      ) : list.error ? (
        <ErrorNote message={list.error} onRetry={list.reload} />
      ) : !list.data || list.data.length === 0 ? (
        <Empty>暂无会话</Empty>
      ) : (
        <div className="flex flex-col gap-2">
          {list.data.map((s) => (
            <div key={s.id} className="rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  <Badge tone={s.current ? "good" : "neutral"}>{s.current ? "当前" : "会话 #" + s.id}</Badge>
                  <span className="num text-fog-400">{s.ip || "—"}</span>
                  <span className="num text-fog-500">建立 {timeShort(s.created_at)}</span>
                  <span className="num text-fog-500">到期 {timeShort(s.expires_at)}</span>
                </div>
                {!s.current && (
                  <Button variant="danger" onClick={() => kill(s.id)}>
                    吊销
                  </Button>
                )}
              </div>
              {s.user_agent && <div className="mt-1 truncate text-[10px] text-ink-500">{s.user_agent}</div>}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function AiReview({ report }: { report: (e: unknown, ok?: string) => void }) {
  const list = useAsync(() => api.aiAllProviders(), []);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function act(id: number, body: Record<string, unknown>, okText: string) {
    setBusyId(id);
    try {
      await api.aiPatchProvider(id, body);
      report(null, okText);
      list.reload();
    } catch (e) {
      report(e);
    } finally {
      setBusyId(null);
    }
  }

  async function test(id: number) {
    setBusyId(id);
    try {
      const res = await api.aiTestProvider(id);
      report(null, (res.ok ? "连通正常 · " : "连通失败 · ") + (res.message || "") + (res.latency_ms ? " · " + res.latency_ms + "ms" : ""));
      list.reload();
    } catch (e) {
      report(e);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card>
      <CardTitle
        title="AI 供应商审核"
        sub="用户在前台提交的供应商进入待审队列；通过后前台才能选用。Key 加密存储，仅显示掩码。"
        right={<Button variant="subtle" onClick={list.reload}>刷新</Button>}
      />
      {list.loading ? (
        <Spinner />
      ) : list.error ? (
        <ErrorNote message={list.error} onRetry={list.reload} />
      ) : !list.data || list.data.length === 0 ? (
        <Empty>还没有供应商提交</Empty>
      ) : (
        <div className="flex flex-col gap-2">
          {list.data.map((p: AiProviderRow) => (
            <div key={p.id} className="rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-fog-200">{p.name}</span>
                  <Badge tone="neutral">{p.vendor}</Badge>
                  <span className="num text-[11px] text-fog-400">{p.model}</span>
                  <Badge
                    tone={p.status === "approved" ? "good" : p.status === "rejected" ? "bad" : "warn"}
                  >
                    {p.status}
                  </Badge>
                  <Badge tone={p.enabled ? "good" : "neutral"}>{p.enabled ? "启用" : "停用"}</Badge>
                  <Badge tone={p.api_key_set ? "info" : "neutral"}>{p.api_key_set ? p.api_key_hint : "无 Key"}</Badge>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button disabled={busyId === p.id} onClick={() => test(p.id)}>
                    测试
                  </Button>
                  {p.status !== "approved" && (
                    <Button variant="primary" disabled={busyId === p.id} onClick={() => act(p.id, { status: "approved", enabled: true }, "已通过")}>
                      通过
                    </Button>
                  )}
                  {p.status !== "rejected" && (
                    <Button variant="danger" disabled={busyId === p.id} onClick={() => act(p.id, { status: "rejected", enabled: false }, "已拒绝")}>
                      拒绝
                    </Button>
                  )}
                </div>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-fog-400">
                <span className="num truncate">{p.base_url}</span>
                <span>提交人：{p.submitter_name || "—"}</span>
                <span>联系：{p.submitter_contact || "—"}</span>
                <span className="num">调用 {p.calls}</span>
                <span className="num">提交 {timeShort(p.created_at)}</span>
              </div>
              {p.note && <div className="mt-1 text-[11px] text-fog-500">备注：{p.note}</div>}
              {p.last_error && <div className="mt-1 text-[11px] text-ball-red">错误：{p.last_error}</div>}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
