import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, type Game, type TicketRow } from "../lib/api";
import { useAsync } from "../lib/hooks";
import { useAuth } from "../lib/auth";
import { Balls } from "../components/Balls";
import { Badge, Button, Card, CardTitle, Empty, ErrorNote, NumberField, Select, Spinner, Stat, TextField, Skeleton} from "../components/ui";
import { gameName, money, timeShort } from "../lib/format";
import { TermHint, Glossary } from "../components/Term";

export default function Tickets({ games }: { games: Game[] }) {
  const { isAuthed, user } = useAuth();
  const list = useAsync(() => api.tickets(), [isAuthed]);
  const stats = useAsync(() => api.ticketStats(), [isAuthed]);
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [claimMsg, setClaimMsg] = useState<string | null>(null);

  const [game, setGame] = useState("ssq");
  const [issue, setIssue] = useState("");
  const [red, setRed] = useState("");
  const [blue, setBlue] = useState("");
  const [cost, setCost] = useState(2);
  const [note, setNote] = useState("");

  const rows = (list.data ?? []).filter((t) => filter === "all" || t.game_code === filter);

  async function refresh() {
    list.reload();
    stats.reload();
  }

  async function add() {
    setErr(null);
    const redArr = red.split(/[\s,，]+/).filter(Boolean);
    const blueArr = blue.split(/[\s,，]+/).filter(Boolean);
    if (redArr.length === 0) {
      setErr("请填写红球号码");
      return;
    }
    try {
      await api.createTicket({ game_code: game, issue, numbers: { red: redArr, blue: blueArr }, cost, note });
      setRed("");
      setBlue("");
      setNote("");
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function del(id: number) {
    setBusy(id);
    setErr(null);
    try {
      await api.deleteTicket(id);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {!isAuthed && (
        <Card className="border-amber-glow/40 bg-amber-glow/5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-amber-glow">当前为游客模式</div>
              <div className="mt-1 text-[11px] text-fog-400">
                票存在这台浏览器里，换设备或清缓存就没了。注册登录后票夹跨设备同步，已有的游客票会自动迁移。
              </div>
            </div>
            <Link to="/login">
              <Button variant="primary">注册 / 登录</Button>
            </Link>
          </div>
        </Card>
      )}

      {isAuthed && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-ink-700/70 bg-ink-900/40 px-3 py-2 text-[11px] text-fog-400">
          <span>
            已登录 <span className="text-fog-200">{user?.display_name || user?.username}</span>，票夹跟随账号同步
          </span>
          <Button
            variant="subtle"
            onClick={async () => {
              try {
                const r = await api.claimTickets();
                setClaimMsg(r.moved > 0 ? `已迁移 ${r.moved} 张本设备票` : "本设备没有待迁移的票");
                if (r.moved > 0) { list.reload(); stats.reload(); }
              } catch (e) {
                setClaimMsg("迁移失败：" + (e instanceof Error ? e.message : String(e)));
              }
            }}
          >
            迁移本设备票
          </Button>
        </div>
      )}
      {claimMsg && (
        <div className="rounded-lg border border-jade/30 bg-jade/10 px-3 py-2 text-[11px] text-jade">{claimMsg}</div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5 2xl:gap-4">
        <Stat label="总注数" value={stats.data?.total_tickets ?? 0} />
        <Stat label="总投入" value={money(stats.data?.total_cost ?? 0)} />
        <Stat label="总奖金" value={money(stats.data?.total_prize ?? 0)} tone={(stats.data?.total_prize ?? 0) > 0 ? "good" : undefined} />
        <Stat label="回报率" value={((stats.data?.roi ?? 0) * 100).toFixed(1) + "%"} tone={(stats.data?.roi ?? 0) >= 1 ? "good" : "bad"} />
        <Stat label="待开奖" value={stats.data?.pending ?? 0} hint={"已结算 " + (stats.data?.settled ?? 0)} />
      </div>

      <Card>
        <CardTitle title="手动记一注" sub="开奖后点「核对兑奖」，系统会自动算中了几注、奖金多少" />
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-wider text-fog-400">彩种</span>
            <Select
              value={game}
              onChange={setGame}
              options={games.map((g) => ({ value: g.code, label: gameName(g.code) }))}
            />
          </label>
          <TextField label="期号" value={issue} onChange={setIssue} placeholder="2026121" width="w-28" />
          <TextField label="红球号码" value={red} onChange={setRed} placeholder="01 05 12 18 23 30" width="w-56" />
          <TextField label="蓝球号码" value={blue} onChange={setBlue} placeholder="07" width="w-20" />
          <NumberField label="花费(元)" value={cost} onChange={setCost} min={1} max={10000} width="w-20" />
          <TextField label="备注" value={note} onChange={setNote} placeholder="可选" width="w-40" />
          <Button variant="primary" onClick={add}>保存</Button>
        </div>
        {err && <div className="mt-3"><ErrorNote message={err} /></div>}
      </Card>

      <Card>
        <CardTitle
          title="我的彩票本"
          sub="记录你自己买的号码，开奖后自动算中奖情况。只是记账，不是真的购彩"
          right={
            <div className="flex items-center gap-2">
              <Select
                value={filter}
                onChange={setFilter}
                options={[{ value: "all", label: "全部彩种" }, ...games.map((g) => ({ value: g.code, label: gameName(g.code) }))]}
              />
              <Button variant="subtle" onClick={refresh}>刷新</Button>
            </div>
          }
        />
        {list.loading ? (
          <Skeleton rows={5} />
        ) : list.error ? (
          <ErrorNote message={list.error} onRetry={list.reload} />
        ) : rows.length === 0 ? (
          <Empty>还没有记录。可以在上面手动记一注，或在「生成下期号码」页点「存票夹」</Empty>
        ) : (
          <>
            {/* 移动端卡片 */}
            <div className="flex flex-col gap-2 md:hidden">
              {rows.map((t: TicketRow) => (
                <div key={t.id} className="rounded-xl border border-ink-700/70 bg-ink-900/40 px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-fog-200">{gameName(t.game_code)}</span>
                      <span className="num text-[11px] text-fog-400">{t.issue || "—"}</span>
                    </div>
                    {t.settled ? (
                      <Badge tone={t.prize > 0 ? "good" : "neutral"}>{t.prize > 0 ? "中奖" : "未中"}</Badge>
                    ) : (
                      <Badge tone="warn">待开奖</Badge>
                    )}
                  </div>
                  <div className="mt-1.5">
                    <Balls red={t.numbers.red} blue={t.numbers.blue} ordered={t.numbers.ordered ?? null} size="sm" max={20} />
                  </div>
                  <div className="mt-1.5 flex items-center justify-between text-[11px] text-fog-400">
                    <span className="num">投入 {t.cost}</span>
                    <span className="num text-jade">{t.prize ? money(t.prize) : "—"}</span>
                    <span className="num text-ink-500">{timeShort(t.created_at)}</span>
                    <button
                      className="text-ball-red disabled:opacity-40"
                      disabled={busy === t.id}
                      onClick={() => del(t.id)}
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
            {/* 桌面表格 */}
            <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-fog-400">
                  <th className="py-2 pr-3 font-normal">彩种</th>
                  <th className="py-2 pr-3 font-normal"><TermHint k="issue">期号</TermHint></th>
                  <th className="py-2 pr-3 font-normal">号码</th>
                  <th className="py-2 pr-3 text-right font-normal">花费</th>
                  <th className="py-2 pr-3 font-normal">状态</th>
                  <th className="py-2 pr-3 text-right font-normal">奖金</th>
                  <th className="py-2 pr-3 font-normal">时间</th>
                  <th className="py-2 font-normal" />
                </tr>
              </thead>
              <tbody>
                {rows.map((t: TicketRow) => (
                  <tr key={t.id} className="border-t border-ink-700/60">
                    <td className="py-2 pr-3 text-fog-200">{gameName(t.game_code)}</td>
                    <td className="num py-2 pr-3 text-fog-400">{t.issue || "—"}</td>
                    <td className="py-2 pr-3">
                      <Balls red={t.numbers.red} blue={t.numbers.blue} ordered={t.numbers.ordered ?? null} size="sm" max={20} />
                    </td>
                    <td className="num py-2 pr-3 text-right text-fog-400">{t.cost}</td>
                    <td className="py-2 pr-3">
                      {t.settled ? <Badge tone={t.prize > 0 ? "good" : "neutral"}>{t.prize > 0 ? "中奖" : "未中"}</Badge> : <Badge tone="warn">待开奖</Badge>}
                    </td>
                    <td className="num py-2 pr-3 text-right text-jade">{t.prize ? money(t.prize) : "—"}</td>
                    <td className="num py-2 pr-3 text-fog-400">{timeShort(t.created_at)}</td>
                    <td className="py-2 text-right">
                      <Button variant="danger" disabled={busy === t.id} onClick={() => del(t.id)}>
                        删除
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </>
        )}
      </Card>

      <Glossary />
    </div>
  );
}
