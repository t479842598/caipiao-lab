import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { useAuth } from "../lib/auth";
import { Badge, Button, Card, CardTitle, Empty, ErrorNote, Spinner } from "../components/ui";
import { gameName } from "../lib/format";

const STATUS_TONE: Record<string, "good" | "warn" | "bad" | "neutral"> = {
  success: "good",
  running: "warn",
  failed: "bad",
};

export default function Sync() {
  const { isAdmin, loading } = useAuth();
  const status = useAsync(() => api.syncStatus(), []);
  const providers = useAsync(() => api.providers(), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function guard(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    setErr(null);
    setMsg(null);
    try {
      const res = await fn();
      setMsg(typeof res === "object" && res ? JSON.stringify(res) : String(res));
      status.reload();
      providers.reload();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setErr("需要管理员登录后才能操作数据源");
      } else if (e instanceof ApiError && e.status === 403) {
        setErr(e.message || "当前操作被拒绝（只读模式或缺少 CSRF 头）");
      } else {
        setErr(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <Spinner label="检查登录状态" />;

  return (
    <div className="flex flex-col gap-4">
      {!isAdmin && (
        <Card className="border-amber-glow/40 bg-amber-glow/5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-amber-glow">当前为只读浏览</div>
              <div className="mt-1 text-[11px] text-fog-400">
                同步、补录、供应商启停属于后台操作，需要管理员登录。前台数据无需登录即可查看。
              </div>
            </div>
            <Link to="/login">
              <Button variant="primary">管理员登录</Button>
            </Link>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 2xl:gap-4">
        {(Object.entries(status.data?.counts ?? {}) as [string, number][]).map(([code, n]) => (
          <div key={code} className="card p-3 md:p-4">
            <div className="flex items-center justify-between gap-1">
              <span className="truncate text-xs text-fog-300">{gameName(code)}</span>
              {status.data?.running?.[code] ? <Badge tone="warn">同步中</Badge> : <Badge tone="good">就绪</Badge>}
            </div>
            <div className="num mt-1.5 text-xl font-semibold text-fog-200 md:text-2xl">
              {n.toLocaleString("zh-CN")}
            </div>
            <div className="text-[11px] text-fog-400">已收录期数</div>
          </div>
        ))}
      </div>

      <Card>
        <CardTitle
          title="同步控制"
          sub="增量同步只拉最新页；全量同步重新翻完官方源所有页面；深历史补录从 500.com 抓 2003 年起的早期期次（只补缺，不覆盖）"
          right={
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" disabled={!isAdmin || busy !== null} onClick={() => guard("inc", () => api.syncAll())}>
                增量同步全部
              </Button>
              <Button disabled={!isAdmin || busy !== null} onClick={() => guard("settle", () => api.settle())}>
                核对兑奖
              </Button>
            </div>
          }
        />
        <div className="flex flex-wrap gap-2">
          {["ssq", "3d", "qlc", "kl8"].map((g) => (
            <Button
              key={g}
              disabled={!isAdmin || busy !== null}
              onClick={() => guard(g, () => api.syncGame(g, "incremental"))}
            >
              同步 {gameName(g)}
            </Button>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-ink-700/60 pt-3">
          <span className="text-[11px] text-fog-500">深历史补录（2003 年起，官方源没有的部分）：</span>
          {["ssq", "3d", "qlc"].map((g) => (
            <Button
              key={g}
              disabled={!isAdmin || busy !== null}
              onClick={() => guard("bf-" + g, () => api.syncGame(g, "backfill"))}
            >
              补录 {gameName(g)}
            </Button>
          ))}
          <Button
            variant="subtle"
            disabled={!isAdmin || busy !== null}
            onClick={() => guard("bf-all", () => api.syncGame("all", "backfill"))}
          >
            全部补录
          </Button>
        </div>
        {busy && (
          <div className="mt-3">
            <Spinner label="请求已提交，后台执行中" />
          </div>
        )}
        {err && (
          <div className="mt-3">
            <ErrorNote message={err} />
          </div>
        )}
        {msg && (
          <div className="mt-3 break-all rounded-lg border border-jade/30 bg-jade/10 px-3 py-2 text-[11px] text-jade">
            {msg}
          </div>
        )}
      </Card>

      <Card>
        <CardTitle title="数据源供应商" sub="按优先级依次尝试，前一个失败自动切到下一个" />
        {providers.loading ? (
          <Spinner />
        ) : providers.error ? (
          <ErrorNote message={providers.error} onRetry={providers.reload} />
        ) : !providers.data || providers.data.length === 0 ? (
          <Empty />
        ) : (
          <div className="flex flex-col gap-2">
            {providers.data.map((p) => (
              <div key={p.code} className="rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-fog-200">{p.name}</span>
                    <Badge tone="neutral">{p.code}</Badge>
                    <Badge tone={p.enabled ? "good" : "bad"}>{p.enabled ? "已启用" : "已停用"}</Badge>
                    {p.healthy ? <Badge tone="info">健康</Badge> : <Badge tone="warn">异常</Badge>}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[11px] text-fog-400">
                      优先级 {p.priority} · 限速 {p.rate_limit}/s
                    </span>
                    <Button disabled={!isAdmin || busy !== null} onClick={() => guard(p.code, () => api.testProvider(p.code))}>
                      连通测试
                    </Button>
                    <Button
                      variant={p.enabled ? "danger" : "primary"}
                      disabled={!isAdmin || busy !== null}
                      onClick={() => guard(p.code + "-t", () => api.patchProvider(p.code, { enabled: !p.enabled }))}
                    >
                      {p.enabled ? "停用" : "启用"}
                    </Button>
                  </div>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-fog-400">
                  <span>支持：{p.supported_games.map(gameName).join("、")}</span>
                  <span>上次成功：{p.last_ok_at ?? "—"}</span>
                  {p.last_error && <span className="text-ball-red">错误：{p.last_error}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <CardTitle
          title="同步记录"
          sub="最近 12 次同步运行"
          right={
            <Button variant="subtle" onClick={status.reload}>
              刷新
            </Button>
          }
        />
        {status.loading ? (
          <Spinner />
        ) : status.error ? (
          <ErrorNote message={status.error} onRetry={status.reload} />
        ) : !status.data || status.data.last_runs.length === 0 ? (
          <Empty>还没有同步记录</Empty>
        ) : (
          <>
            {/* 移动端卡片 */}
            <div className="flex flex-col gap-2 md:hidden">
              {status.data.last_runs.map((r) => (
                <div key={r.id} className="rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-fog-200">{gameName(r.game_code)}</span>
                    <Badge tone={STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Badge>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-fog-400">
                    <span>{r.provider}</span>
                    <span>{r.mode}</span>
                    <span className="num">抓取 {r.fetched}</span>
                    <span className="num text-jade">新增 {r.inserted}</span>
                  </div>
                  <div className="num mt-0.5 text-[10px] text-ink-500">{r.started_at ?? "—"}</div>
                </div>
              ))}
            </div>
            {/* 桌面表格 */}
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-fog-400">
                    <th className="py-2 pr-3 font-normal">彩种</th>
                    <th className="py-2 pr-3 font-normal">源</th>
                    <th className="py-2 pr-3 font-normal">模式</th>
                    <th className="py-2 pr-3 font-normal">状态</th>
                    <th className="py-2 pr-3 text-right font-normal">抓取</th>
                    <th className="py-2 pr-3 text-right font-normal">新增</th>
                    <th className="py-2 text-right font-normal">开始时间</th>
                  </tr>
                </thead>
                <tbody>
                  {status.data.last_runs.map((r) => (
                    <tr key={r.id} className="border-t border-ink-700/60">
                      <td className="py-1.5 pr-3 text-fog-200">{gameName(r.game_code)}</td>
                      <td className="py-1.5 pr-3 text-fog-400">{r.provider}</td>
                      <td className="py-1.5 pr-3 text-fog-400">{r.mode}</td>
                      <td className="py-1.5 pr-3">
                        <Badge tone={STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Badge>
                      </td>
                      <td className="num py-1.5 pr-3 text-right text-fog-300">{r.fetched}</td>
                      <td className="num py-1.5 pr-3 text-right text-jade">{r.inserted}</td>
                      <td className="num py-1.5 text-right text-fog-400">{r.started_at ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <Card>
        <CardTitle title="定时任务" sub="按开奖日历自动触发的计划" />
        {!status.data || status.data.next_jobs.length === 0 ? (
          <Empty>调度器未启动（SYNC_ENABLED=false 或进程未加载）</Empty>
        ) : (
          <div className="flex flex-wrap gap-2">
            {status.data.next_jobs.map((j) => (
              <div key={j.id} className="rounded-lg border border-ink-700/70 px-2.5 py-1.5 text-[11px] text-fog-400">
                {j.id} <span className="num text-fog-200">{j.next_run ?? "—"}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
